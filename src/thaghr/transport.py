from __future__ import annotations

from typing import Literal

import httpx

from thaghr.cassette import Cassette
from thaghr.faults.base import Fault

Mode = Literal["live", "record", "replay"]


class ThaghrTransport(httpx.BaseTransport):
    """An httpx transport that runs a stack of faults against every request.

    Point any SDK's httpx client at a ThaghrTransport (via `http_client=`
    on the OpenAI client, or the equivalent for any other httpx-based SDK)
    and every call it makes gets the same fault stack. No SDK-specific
    adapter is required; this is the provider-level interception locked
    in during naming/claiming.

    The first fault in `faults` whose `apply()` returns a non-None result
    short-circuits the request: `wrapped` is never called and no real
    network traffic occurs. If no fault fires, the request is handled
    according to `mode`:

      - "live" (default): forwarded to `wrapped` unchanged, nothing recorded.
      - "record": forwarded to `wrapped`, and the request/response pair is
        saved to `cassette`.
      - "replay": never touches `wrapped`; the response comes from
        `cassette` instead. This is what makes a mixed real+fault campaign
        byte-identical across re-runs under the same seed: faults replay
        deterministically via each Fault's own RNG, and the non-faulted
        calls replay deterministically via the cassette.
    """

    def __init__(
        self,
        faults: list[Fault],
        wrapped: httpx.BaseTransport | None = None,
        cassette: Cassette | None = None,
        mode: Mode = "live",
    ) -> None:
        if mode in ("record", "replay") and cassette is None:
            raise ValueError(f"mode={mode!r} requires a cassette")
        self.faults = faults
        self.wrapped = wrapped or httpx.HTTPTransport()
        self.cassette = cassette
        self.mode = mode
        self.request_log: list[dict] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        for fault in self.faults:
            result = fault.apply()
            if result is not None:
                self.request_log.append(
                    {
                        "method": request.method,
                        "url": str(request.url),
                        "injected_status": result.status_code,
                        "injected_body": result.body,
                    }
                )
                return httpx.Response(
                    status_code=result.status_code,
                    json=result.body,
                    request=request,
                    headers={"retry-after": "0"},
                )

        if self.mode == "replay":
            response = self.cassette.replay(request)
        else:
            response = self.wrapped.handle_request(request)
            if self.mode == "record":
                self.cassette.record(request, response)

        self.request_log.append(
            {"method": request.method, "url": str(request.url), "injected_status": None}
        )
        return response

    def reset(self) -> None:
        """Reset every fault's RNG, clear the request log, and rewind the
        cassette (if any) to its start, for re-running a campaign from
        the beginning."""
        for fault in self.faults:
            fault.reset()
        self.request_log = []
        if self.cassette is not None:
            self.cassette.reset_replay_position()
