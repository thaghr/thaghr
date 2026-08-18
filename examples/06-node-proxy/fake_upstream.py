"""Deterministic, zero-cost stand-in for an OpenAI-compatible endpoint.

Not part of thaghr itself, just a local target so this example runs
end-to-end without a real API key or real API cost. Point `thaghr proxy`
at this (--upstream http://127.0.0.1:8090) instead of a real provider to
try the fault injection without spending anything.

Usage:
    python examples/06-node-proxy/fake_upstream.py [port]
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_CANNED_COMPLETION = {
    "id": "chatcmpl-fake",
    "object": "chat.completion",
    "created": 0,
    "model": "gpt-4o-mini",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "hi there friend"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 9, "completion_tokens": 3, "total_tokens": 12},
}


class FakeOpenAIHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", 0) or 0)
        self.rfile.read(length)  # request body ignored, response is always the same
        body = json.dumps(_CANNED_COMPLETION).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8090
    server = ThreadingHTTPServer(("127.0.0.1", port), FakeOpenAIHandler)
    print(f"fake_upstream: listening on http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
