import time

from .base import Fault


class LatencyFault(Fault):
    """Sleeps for `delay_ms` milliseconds when fired.

    apply() returns True if the fault fired (and slept), False otherwise,
    so callers can use it directly as a boolean signal.
    """

    def __init__(self, rate: float, seed: int, delay_ms: float = 1000):
        super().__init__(rate, seed)
        if delay_ms < 0:
            raise ValueError(f"delay_ms must be >= 0, got {delay_ms}")
        self.delay_ms = delay_ms

    def apply(self) -> bool:
        if self.should_fire():
            time.sleep(self.delay_ms / 1000)
            return True
        return False
