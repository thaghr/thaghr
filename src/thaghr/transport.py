from __future__ import annotations

import httpx

from thaghr.faults.http_error import HTTPErrorFault


class ThaghrTransport(httpx.BaseTransport):
    """An httpx transport that runs a stack of faults against every request.

    Point any SDK's httpx client at a ThaghrTransport (via `http_client=`
    on the OpenAI client, or the equivalent for any other httpx-based SDK)
    and every call it makes gets the same fault stack. No SDK-specific
    adapter is required; this is the provider-level interception locked
    in during naming/claiming.

    The first fault in `faults` whose `apply()` returns a FaultResponse
    short-circuits the request: `wrapped` is never called and no real
    network traffic occurs. If no fault fires, the request is forwarded
    to `wrapped` unchanged.
    """

    def __init__(
        self,
        faults: list[HTTPErrorFault],
        wrapped: httpx.BaseTransport | None = None,
    ) -> None:
        self.faults = faults
        self.wrapped = wrapped or httpx.HTTPTransport()
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
        self.request_log.append(
            {"method": request.method, "url": str(request.url), "injected_status": None}
        )
        return self.wrapped.handle_request(request)

    def reset(self) -> None:
        """Reset every fault's RNG and clear the request log, for re-running a campaign."""
        for fault in self.faults:
            fault.reset()
        self.request_log = []
