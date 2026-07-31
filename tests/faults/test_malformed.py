import json

import pytest

from thaghr.faults.malformed import MalformedResponseFault

PAYLOAD = {"id": "resp_1", "status": "completed", "output": "hello"}


def test_fires_at_configured_rate():
    f = MalformedResponseFault(rate=0.3, seed=42)
    fires = sum(1 for _ in range(10_000) if f.apply(PAYLOAD) is not None)
    assert 2700 < fires < 3300


def test_same_seed_same_sequence():
    a = MalformedResponseFault(rate=0.3, seed=42)
    b = MalformedResponseFault(rate=0.3, seed=42)
    seq_a = [a.apply(PAYLOAD) is not None for _ in range(100)]
    seq_b = [b.apply(PAYLOAD) is not None for _ in range(100)]
    assert seq_a == seq_b


def test_truncate_produces_invalid_json():
    f = MalformedResponseFault(rate=1.0, seed=1, strategy="truncate")
    result = f.apply(PAYLOAD)
    assert isinstance(result, str)
    with pytest.raises(json.JSONDecodeError):
        json.loads(result)


def test_drop_key_removes_field():
    f = MalformedResponseFault(rate=1.0, seed=1, strategy="drop_key", drop_key="status")
    result = f.apply(PAYLOAD)
    assert "status" not in result
    assert "id" in result


def test_returns_none_when_not_fired():
    f = MalformedResponseFault(rate=0.0, seed=1)
    assert f.apply(PAYLOAD) is None
