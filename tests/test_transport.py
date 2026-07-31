from __future__ import annotations

import httpx
import openai
import pytest

from thaghr.faults.http_error import HTTPErrorFault
from thaghr.transport import ThaghrTransport


def _unreachable_transport(request: httpx.Request) -> httpx.Response:
    raise AssertionError("wrapped transport was called; a fault should have short-circuited this")


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    # The OpenAI SDK sleeps between retries using time.sleep. Faults fire
    # in microseconds; the SDK's backoff should not make this test suite slow.
    monkeypatch.setattr("openai._base_client.time.sleep", lambda seconds: None)


def _make_client(rate: float, seed: int, max_retries: int = 2) -> tuple[openai.OpenAI, ThaghrTransport]:
    transport = ThaghrTransport(
        faults=[HTTPErrorFault(rate=rate, seed=seed, status_code=429)],
        wrapped=httpx.MockTransport(_unreachable_transport),
    )
    http_client = httpx.Client(transport=transport)
    client = openai.OpenAI(api_key="thaghr-test-key", http_client=http_client, max_retries=max_retries)
    return client, transport


class TestSDKRetryEngages:
    def test_injected_429_triggers_openais_own_retry(self):
        client, transport = _make_client(rate=1.0, seed=1, max_retries=2)

        with pytest.raises(openai.RateLimitError):
            client.chat.completions.create(
                model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}]
            )

        # max_retries=2 means 1 initial attempt + 2 retries = 3 total calls.
        # This count comes from openai's own retry loop, not from thaghr.
        assert len(transport.request_log) == 3
        assert all(r["injected_status"] == 429 for r in transport.request_log)

    def test_fault_never_touches_wrapped_transport(self):
        # rate=1.0 fires on every call, so `wrapped` should never be reached.
        # _unreachable_transport raises if it ever is; if a RateLimitError
        # doesn't come out clean, thaghr let a request past the fault stack.
        client, transport = _make_client(rate=1.0, seed=1, max_retries=0)

        with pytest.raises(openai.RateLimitError):
            client.chat.completions.create(
                model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}]
            )

        assert len(transport.request_log) == 1
        assert transport.request_log[0]["injected_status"] == 429

    def test_fault_forwards_to_wrapped_when_not_fired(self):
        # rate=0.0 never fires, so this proves the pass-through path itself
        # works, not just the injection path.
        payload = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "hello"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

        def fake_backend(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=payload, request=request)

        transport = ThaghrTransport(
            faults=[HTTPErrorFault(rate=0.0, seed=1, status_code=429)],
            wrapped=httpx.MockTransport(fake_backend),
        )
        client = openai.OpenAI(
            api_key="thaghr-test-key", http_client=httpx.Client(transport=transport), max_retries=0
        )

        completion = client.chat.completions.create(
            model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}]
        )

        assert completion.choices[0].message.content == "hello"
        assert transport.request_log == [
            {"method": "POST", "url": transport.request_log[0]["url"], "injected_status": None}
        ]

    def test_partial_rate_still_short_circuits_every_fired_call(self):
        # rate=1.0 keeps every retry firing, proving the fault re-evaluates
        # should_fire() on each individual request, not once per campaign.
        client, transport = _make_client(rate=1.0, seed=99, max_retries=1)

        with pytest.raises(openai.RateLimitError):
            client.chat.completions.create(
                model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}]
            )

        assert len(transport.request_log) == 2  # 1 initial + 1 retry


class TestDeterminism:
    def test_byte_identical_rerun_same_seed(self):
        client_a, transport_a = _make_client(rate=1.0, seed=7, max_retries=2)
        client_b, transport_b = _make_client(rate=1.0, seed=7, max_retries=2)

        with pytest.raises(openai.RateLimitError):
            client_a.chat.completions.create(
                model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}]
            )
        with pytest.raises(openai.RateLimitError):
            client_b.chat.completions.create(
                model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}]
            )

        assert transport_a.request_log == transport_b.request_log

    def test_reset_replays_identical_run(self):
        client, transport = _make_client(rate=1.0, seed=3, max_retries=2)

        with pytest.raises(openai.RateLimitError):
            client.chat.completions.create(
                model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}]
            )
        first_run = transport.request_log

        transport.reset()

        with pytest.raises(openai.RateLimitError):
            client.chat.completions.create(
                model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}]
            )
        second_run = transport.request_log

        assert first_run == second_run
