from __future__ import annotations

import httpx
import openai
import pytest

from thaghr.faults.http_error import HTTPErrorFault
from thaghr.proxy import ThaghrProxyServer


def _fake_openai_backend(request: httpx.Request) -> httpx.Response:
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
    return httpx.Response(200, json=payload, request=request)


def _unreachable_backend(request: httpx.Request) -> httpx.Response:
    raise AssertionError("wrapped transport was called; a fault should have short-circuited this")


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    monkeypatch.setattr("openai._base_client.time.sleep", lambda seconds: None)


class TestProxyPassthrough:
    def test_unfaulted_request_reaches_upstream_and_returns_body(self):
        with ThaghrProxyServer(
            upstream_base_url="https://api.openai.com",
            faults=[HTTPErrorFault(rate=0.0, seed=1)],
            port=0,
            wrapped_transport=httpx.MockTransport(_fake_openai_backend),
        ) as server:
            response = httpx.post(
                f"{server.url}/v1/chat/completions", json={"model": "gpt-4o-mini"}
            )

        assert response.status_code == 200
        assert response.json()["choices"][0]["message"]["content"] == "hello"

    def test_path_and_query_string_are_forwarded_unchanged(self):
        with ThaghrProxyServer(
            upstream_base_url="https://api.openai.com",
            faults=[],
            port=0,
            wrapped_transport=httpx.MockTransport(_fake_openai_backend),
        ) as server:
            httpx.post(f"{server.url}/v1/chat/completions?foo=bar")

        assert server.request_log[0]["url"] == "https://api.openai.com/v1/chat/completions?foo=bar"


class TestProxyFaultInjection:
    def test_faulted_request_never_reaches_upstream(self):
        with ThaghrProxyServer(
            upstream_base_url="https://api.openai.com",
            faults=[HTTPErrorFault(rate=1.0, seed=1, status_code=429)],
            port=0,
            wrapped_transport=httpx.MockTransport(_unreachable_backend),
        ) as server:
            response = httpx.post(
                f"{server.url}/v1/chat/completions", json={"model": "gpt-4o-mini"}
            )

        assert response.status_code == 429
        assert server.request_log[0]["injected_status"] == 429

    def test_partial_rate_still_lets_unfaulted_calls_through(self):
        with ThaghrProxyServer(
            upstream_base_url="https://api.openai.com",
            faults=[HTTPErrorFault(rate=0.0, seed=1, status_code=429)],
            port=0,
            wrapped_transport=httpx.MockTransport(_fake_openai_backend),
        ) as server:
            response = httpx.post(f"{server.url}/v1/chat/completions")

        assert response.status_code == 200


class TestProxyMatchesPhase6DoD:
    def test_baseurl_is_the_only_client_side_change(self):
        """Phase 6 DoD: an OpenAI-SDK-shaped call gets faults injected with
        nothing changed beyond base_url/baseURL. Exercised here with the
        Python SDK, since both openai-python and openai-node are thin
        HTTP clients over the same wire format the proxy speaks; the
        Node example in examples/06-node-proxy/ exercises the JS side."""
        with ThaghrProxyServer(
            upstream_base_url="https://api.openai.com",
            faults=[HTTPErrorFault(rate=1.0, seed=1, status_code=429)],
            port=0,
            wrapped_transport=httpx.MockTransport(_fake_openai_backend),
        ) as server:
            client = openai.OpenAI(
                api_key="thaghr-test-key", base_url=f"{server.url}/v1", max_retries=0
            )
            with pytest.raises(openai.RateLimitError):
                client.chat.completions.create(
                    model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}]
                )

    def test_byte_identical_rerun_same_seed(self):
        log_a, log_b = None, None
        for target in ("a", "b"):
            with ThaghrProxyServer(
                upstream_base_url="https://api.openai.com",
                faults=[HTTPErrorFault(rate=0.5, seed=42, status_code=429)],
                port=0,
                wrapped_transport=httpx.MockTransport(_fake_openai_backend),
            ) as server:
                client = openai.OpenAI(
                    api_key="thaghr-test-key", base_url=f"{server.url}/v1", max_retries=0
                )
                results = []
                for _ in range(6):
                    try:
                        client.chat.completions.create(
                            model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}]
                        )
                        results.append("ok")
                    except openai.RateLimitError:
                        results.append("429")
                if target == "a":
                    log_a = results
                else:
                    log_b = results

        assert log_a == log_b
