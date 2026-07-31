from .base import Fault


class FaultResponse:
    """Minimal stand-in for an HTTP response, used until Phase 2 wires in a real transport."""

    def __init__(self, status_code: int, body: dict):
        self.status_code = status_code
        self.body = body

    def __repr__(self):
        return f"FaultResponse(status_code={self.status_code}, body={self.body})"


class HTTPErrorFault(Fault):
    def __init__(self, rate: float, seed: int, status_code: int = 429, body: dict | None = None):
        super().__init__(rate, seed)
        self.status_code = status_code
        self.body = body or {"error": {"type": "rate_limit_error", "message": "injected by thaghr"}}

    def apply(self) -> FaultResponse | None:
        if self.should_fire():
            return FaultResponse(self.status_code, self.body)
        return None
