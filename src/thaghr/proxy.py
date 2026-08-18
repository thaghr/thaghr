"""Phase 6: proxy mode.

Runs thaghr as a standalone HTTP proxy so any HTTP-based SDK, in any
language, gets the same fault stack as the Python httpx-transport
integration (Phase 2), by changing nothing on the client side but its
base_url/baseURL.

Deliberately reuses ThaghrTransport unchanged rather than reimplementing
fault dispatch: every incoming request is translated into an httpx.Request,
run through the existing fault/cassette pipeline, and the resulting
httpx.Response is translated back into a raw HTTP response on the wire.
The fault stack, cassette matching key, and determinism guarantees are
identical to Phase 2. This module only adds the wire-level translation
layer, which is the one piece Phase 2's in-process transport hook cannot
give a non-Python client.
"""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

from thaghr.cassette import Cassette
from thaghr.faults.base import Fault
from thaghr.transport import Mode, ThaghrTransport

# Headers that describe the previous hop's framing, not the payload.
# httpx recomputes these when it builds the outgoing request, and
# http.server recomputes Content-Length from the actual body it writes;
# passing the originals through causes mismatched framing, not a
# meaningful proxy behaviour difference.
_HOP_BY_HOP_REQUEST_HEADERS = {"host", "content-length", "connection", "transfer-encoding"}
_HOP_BY_HOP_RESPONSE_HEADERS = {"content-length", "content-encoding", "transfer-encoding", "connection"}


def _make_handler(transport: ThaghrTransport, upstream_base_url: str) -> type[BaseHTTPRequestHandler]:
    upstream_base_url = upstream_base_url.rstrip("/")

    class ThaghrProxyHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _handle(self, method: str) -> None:
            length = int(self.headers.get("content-length", 0) or 0)
            body = self.rfile.read(length) if length else b""
            headers = {
                k: v for k, v in self.headers.items() if k.lower() not in _HOP_BY_HOP_REQUEST_HEADERS
            }
            # self.path is the full path plus query string exactly as the
            # client sent it (e.g. "/v1/chat/completions"); appending it
            # to the upstream base is the entire routing decision a proxy
            # needs to make, no path rewriting.
            url = f"{upstream_base_url}{self.path}"
            request = httpx.Request(method, url, headers=headers, content=body)

            response = transport.handle_request(request)
            # transport.handle_request() is the raw transport call, not a
            # httpx.Client.send(); real network responses come back
            # unread (streamed) and .content raises until .read() is
            # called. Injected-fault and cassette-replay responses are
            # already fully materialized, so .read() is a harmless no-op
            # on those.
            response.read()

            self.send_response(response.status_code)
            response_headers = {
                k: v for k, v in response.headers.items() if k.lower() not in _HOP_BY_HOP_RESPONSE_HEADERS
            }
            for k, v in response_headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(response.content)))
            self.end_headers()
            self.wfile.write(response.content)

        def do_GET(self) -> None:
            self._handle("GET")

        def do_POST(self) -> None:
            self._handle("POST")

        def do_PUT(self) -> None:
            self._handle("PUT")

        def do_DELETE(self) -> None:
            self._handle("DELETE")

        def log_message(self, format: str, *args) -> None:  # noqa: A002
            pass  # silence default stderr access log; the CLI prints its own summary

    return ThaghrProxyHandler


class ThaghrProxyServer:
    """Threaded HTTP server fronting `upstream_base_url` with a ThaghrTransport.

    Point any HTTP client's base_url/baseURL at this server's `.url` and
    it gets the same fault stack as the httpx-transport integration, with
    zero client-side change beyond the URL. Usable as a context manager
    for tests (starts on a background thread, shuts down on exit) or via
    `serve_forever()` for the CLI's blocking `thaghr proxy` command.
    """

    def __init__(
        self,
        upstream_base_url: str,
        faults: list[Fault],
        host: str = "127.0.0.1",
        port: int = 0,
        cassette: Cassette | None = None,
        mode: Mode = "live",
        wrapped_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.transport = ThaghrTransport(
            faults=faults,
            wrapped=wrapped_transport or httpx.HTTPTransport(),
            cassette=cassette,
            mode=mode,
        )
        handler_cls = _make_handler(self.transport, upstream_base_url)
        self._httpd = ThreadingHTTPServer((host, port), handler_cls)
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        host, port = self._httpd.server_address[:2]
        if host in ("0.0.0.0", "::"):
            host = "127.0.0.1"
        return f"http://{host}:{port}"

    @property
    def request_log(self) -> list[dict]:
        return self.transport.request_log

    def serve_forever(self) -> None:
        self._httpd.serve_forever()

    def shutdown(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def __enter__(self) -> "ThaghrProxyServer":
        self._thread = threading.Thread(target=self.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=2)


def run_proxy(
    upstream_base_url: str,
    fault_rate: float,
    seed: int,
    host: str = "127.0.0.1",
    port: int = 8135,
    status_code: int = 429,
) -> None:
    """Blocking entry point for `thaghr proxy`. Runs until Ctrl+C."""
    from thaghr.faults.http_error import HTTPErrorFault

    faults = [HTTPErrorFault(rate=fault_rate, seed=seed, status_code=status_code)] if fault_rate > 0 else []
    server = ThaghrProxyServer(upstream_base_url=upstream_base_url, faults=faults, host=host, port=port)
    print(f"thaghr proxy: listening on {server.url}, forwarding to {upstream_base_url}")
    print(f"thaghr proxy: fault rate {fault_rate} (seed {seed}); point base_url/baseURL at {server.url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
