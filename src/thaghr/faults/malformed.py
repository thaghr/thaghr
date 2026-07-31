import json
import random

from .base import Fault


class MalformedResponseFault(Fault):
    def __init__(self, rate: float, seed: int, strategy: str = "truncate", drop_key: str | None = None):
        super().__init__(rate, seed)
        if strategy not in ("truncate", "drop_key"):
            raise ValueError(f"unknown strategy: {strategy}")
        if strategy == "drop_key" and drop_key is None:
            raise ValueError("drop_key strategy requires drop_key to be set")
        self.strategy = strategy
        self.drop_key = drop_key
        # separate RNG stream for the corruption itself, so should_fire() sequence
        # stays identical regardless of strategy (needed for cross-strategy determinism tests)
        self._corrupt_rng = random.Random(seed + 1)

    def apply(self, payload: dict) -> str | dict | None:
        if not self.should_fire():
            return None

        if self.strategy == "truncate":
            serialized = json.dumps(payload)
            cutoff = self._corrupt_rng.randint(1, max(1, len(serialized) - 1))
            return serialized[:cutoff]

        # drop_key
        corrupted = dict(payload)
        corrupted.pop(self.drop_key, None)
        return corrupted
