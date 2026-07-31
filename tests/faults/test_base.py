from thaghr.faults.base import Fault


class DummyFault(Fault):
    def apply(self):
        return self.should_fire()


def test_fires_at_configured_rate():
    f = DummyFault(rate=0.3, seed=42)
    fires = sum(f.should_fire() for _ in range(10_000))
    assert 2700 < fires < 3300


def test_same_seed_same_sequence():
    a = DummyFault(rate=0.3, seed=42)
    b = DummyFault(rate=0.3, seed=42)
    assert [a.should_fire() for _ in range(100)] == [b.should_fire() for _ in range(100)]
