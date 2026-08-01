from __future__ import annotations

import httpx
import pytest

from thaghr.cassette import Cassette, CassetteMissError


def _req(method: str = "POST", url: str = "https://api.example.com/v1", body: bytes = b"") -> httpx.Request:
    return httpx.Request(method, url, content=body)


def _resp(request: httpx.Request, status: int = 200, body: bytes = b'{"ok": true}') -> httpx.Response:
    return httpx.Response(status_code=status, content=body, request=request, headers={"x-request-id": "abc"})


class TestRecordAndReplay:
    def test_replay_returns_recorded_status_and_body(self, tmp_path):
        cassette = Cassette(tmp_path / "cassette.json")
        request = _req(body=b'{"n": 1}')
        cassette.record(request, _resp(request, status=200, body=b'{"result": 1}'))

        replayed = cassette.replay(_req(body=b'{"n": 1}'))

        assert replayed.status_code == 200
        assert replayed.json() == {"result": 1}

    def test_replay_recomputes_content_length_rather_than_reusing_a_stale_value(self, tmp_path):
        cassette = Cassette(tmp_path / "cassette.json")
        request = _req()
        cassette.record(request, _resp(request, body=b'{"ok": true}'))

        replayed = cassette.replay(_req())

        assert replayed.headers["x-request-id"] == "abc"
        # httpx recomputes content-length from the actual bytes on construction;
        # this checks it matches the replayed body, not a stale recorded value.
        assert replayed.headers["content-length"] == str(len(replayed.content))

    def test_miss_raises_when_no_recorded_interaction_matches(self, tmp_path):
        cassette = Cassette(tmp_path / "cassette.json")

        with pytest.raises(CassetteMissError):
            cassette.replay(_req(url="https://api.example.com/v1/unrecorded"))


class TestOrderingWithRepeatedKeys:
    def test_identical_requests_replay_in_recorded_order(self, tmp_path):
        cassette = Cassette(tmp_path / "cassette.json")
        request = _req(body=b'{"n": 1}')
        cassette.record(request, _resp(request, body=b'{"attempt": 1}'))
        cassette.record(request, _resp(request, body=b'{"attempt": 2}'))

        first = cassette.replay(_req(body=b'{"n": 1}'))
        second = cassette.replay(_req(body=b'{"n": 1}'))

        assert first.json() == {"attempt": 1}
        assert second.json() == {"attempt": 2}

    def test_third_identical_request_misses_when_only_two_recorded(self, tmp_path):
        cassette = Cassette(tmp_path / "cassette.json")
        request = _req(body=b'{"n": 1}')
        cassette.record(request, _resp(request))
        cassette.record(request, _resp(request))
        cassette.replay(_req(body=b'{"n": 1}'))
        cassette.replay(_req(body=b'{"n": 1}'))

        with pytest.raises(CassetteMissError):
            cassette.replay(_req(body=b'{"n": 1}'))

    def test_reset_replay_position_allows_replaying_from_the_start_again(self, tmp_path):
        cassette = Cassette(tmp_path / "cassette.json")
        request = _req(body=b'{"n": 1}')
        cassette.record(request, _resp(request, body=b'{"attempt": 1}'))
        cassette.replay(_req(body=b'{"n": 1}'))

        cassette.reset_replay_position()
        replayed_again = cassette.replay(_req(body=b'{"n": 1}'))

        assert replayed_again.json() == {"attempt": 1}


class TestPersistence:
    def test_save_and_reload_round_trips_interactions(self, tmp_path):
        path = tmp_path / "cassette.json"
        cassette = Cassette(path)
        request = _req(body=b'{"n": 1}')
        cassette.record(request, _resp(request, body=b'{"result": 42}'))
        cassette.save()

        reloaded = Cassette(path)
        replayed = reloaded.replay(_req(body=b'{"n": 1}'))

        assert replayed.json() == {"result": 42}
