from __future__ import annotations

from collections import deque
from typing import Literal

import httpx

from thaghr.cassette import Cassette
from thaghr.faults.base import Fault
from thaghr.telemetry import repeat_loop_detected_total

Mode = Literal["live", "record", "replay"]


class ThaghrTransport(httpx.BaseTransport):
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
        self._tool_call_window: deque[tuple[str, str]] = deque(maxlen=6)

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

        self._track_tool_calls(response)

        self.request_log.append(
            {"method": request.method, "url": str(request.url), "injected_status": None}
        )
        return response

    def _track_tool_calls(self, response: httpx.Response) -> None:
        """Feed any tool_calls in this response into a 6-step sliding
        window. The moment a (tool, args) pair hits its 3rd occurrence
        in that window, increment repeat_loop_detected_total once for
        that occurrence, not on every subsequent match, so a stuck
        agent doesn't runaway-increment the counter every step after
        crossing the threshold."""
        try:
            body = response.json()
        except Exception:
            return

        try:
            tool_calls = body["choices"][0]["message"].get("tool_calls") or []
        except (KeyError, IndexError, TypeError):
            return

        for call in tool_calls:
            fn = call.get("function", {})
            key = (fn.get("name", ""), fn.get("arguments", ""))
            self._tool_call_window.append(key)
            if list(self._tool_call_window).count(key) == 3:
                repeat_loop_detected_total.labels(tool=key[0]).inc()

    def reset(self) -> None:
        """Reset every fault's RNG, clear the request log, rewind the
        cassette (if any), and clear the tool-call window, for
        re-running a campaign from the beginning."""
        for fault in self.faults:
            fault.reset()
        self.request_log = []
        self._tool_call_window.clear()
        if self.cassette is not None:
            self.cassette.reset_replay_position()
