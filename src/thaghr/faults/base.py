import random
from abc import ABC, abstractmethod


class Fault(ABC):
    """Base class for all fault primitives.

    Subclasses implement `apply()`, which draws from should_fire() and
    either applies the fault's effect or returns None/False depending on
    the primitive's return shape (HTTPErrorFault returns a FaultResponse
    or None, LatencyFault returns a bool, MalformedResponseFault returns
    a corrupted payload or None).
    """

    def __init__(self, rate: float, seed: int):
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"rate must be in [0, 1], got {rate}")
        self.rate = rate
        self.seed = seed
        self._rng = random.Random(seed)

    def should_fire(self) -> bool:
        """Draw once from the private RNG and compare to the configured rate.

        Every call consumes exactly one draw, fired or not, so the
        sequence of outcomes is fully determined by (seed, rate, call count).
        """
        return self._rng.random() < self.rate

    @abstractmethod
    def apply(self):
        raise NotImplementedError

    def reset(self) -> None:
        """Reset the private RNG to the configured seed, for re-running a campaign."""
        self._rng = random.Random(self.seed)
