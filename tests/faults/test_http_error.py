from thaghr.faults.http_error import HTTPErrorFault


def test_fires_at_configured_rate():
    f = HTTPErrorFault(rate=0.3, seed=42)
    fires = sum(1 for _ in range(10_000) if f.apply() is not None)
    assert 2700 < fires < 3300


def test_same_seed_same_sequence():
    a = HTTPErrorFault(rate=0.3, seed=42)
    b = HTTPErrorFault(rate=0.3, seed=42)
    seq_a = [a.apply() is not None for _ in range(100)]
    seq_b = [b.apply() is not None for _ in range(100)]
    assert seq_a == seq_b


def test_returns_configured_status_and_body():
    f = HTTPErrorFault(rate=1.0, seed=1, status_code=503, body={"error": "unavailable"})
    resp = f.apply()
    assert resp.status_code == 503
    assert resp.body == {"error": "unavailable"}


def test_returns_none_when_not_fired():
    f = HTTPErrorFault(rate=0.0, seed=1)
    assert f.apply() is None
