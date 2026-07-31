import time

from thaghr.faults.latency import LatencyFault


def test_fires_at_configured_rate():
    f = LatencyFault(rate=0.3, seed=42, delay_ms=1)
    fires = sum(f.apply() for _ in range(10_000))
    assert 2700 < fires < 3300


def test_same_seed_same_sequence():
    a = LatencyFault(rate=0.3, seed=42, delay_ms=1)
    b = LatencyFault(rate=0.3, seed=42, delay_ms=1)
    assert [a.apply() for _ in range(100)] == [b.apply() for _ in range(100)]


def test_actually_sleeps_when_fired():
    f = LatencyFault(rate=1.0, seed=1, delay_ms=50)
    start = time.monotonic()
    f.apply()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.05
