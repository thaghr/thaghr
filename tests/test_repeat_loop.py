"""Proves ThaghrTransport._track_tool_calls fires repeat_loop_detected_total
on the 3rd repeat of an identical (tool, args) pair within a 6-step window.
No live API call, no cluster, no cost: fakes `wrapped` to return canned
tool_call responses directly.
"""
from __future__ import annotations

import httpx
import pytest

from thaghr.telemetry import repeat_loop_detected_total
from thaghr.transport import ThaghrTransport


class _StubTransport(httpx.BaseTransport):
    """Returns the same tool_call response every time, standing in for a
    stuck agent that keeps calling the same tool with the same args."""

    def __init__(self, tool_name: str, arguments: str):
        self.tool_name = tool_name
        self.arguments = arguments

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": self.tool_name,
                                        "arguments": self.arguments,
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
            request=request,
        )


def _counter_value(tool: str) -> float:
    for metric in repeat_loop_detected_total.collect():
        for sample in metric.samples:
            if sample.name.endswith("_total") and sample.labels.get("tool") == tool:
                return sample.value
    return 0.0


def test_repeat_loop_fires_on_third_identical_call():
    tool, args = "get_weather", '{"city": "Lagos"}'
    before = _counter_value(tool)

    stub = _StubTransport(tool_name=tool, arguments=args)
    transport = ThaghrTransport(faults=[], wrapped=stub)
    client = httpx.Client(transport=transport)

    for _ in range(3):
        client.get("https://api.openai.com/v1/chat/completions")

    after = _counter_value(tool)
    assert after == before + 1, (
        f"expected exactly one increment on the 3rd repeat, got {after - before}"
    )


def test_repeat_loop_does_not_fire_below_threshold():
    tool, args = "search_docs", '{"query": "onboarding"}'
    before = _counter_value(tool)

    stub = _StubTransport(tool_name=tool, arguments=args)
    transport = ThaghrTransport(faults=[], wrapped=stub)
    client = httpx.Client(transport=transport)

    for _ in range(2):
        client.get("https://api.openai.com/v1/chat/completions")

    after = _counter_value(tool)
    assert after == before, "should not fire before the 3rd repeat"


def test_repeat_loop_resets_between_episodes():
    tool, args = "flaky_tool", "{}"
    stub = _StubTransport(tool_name=tool, arguments=args)
    transport = ThaghrTransport(faults=[], wrapped=stub)
    client = httpx.Client(transport=transport)

    for _ in range(3):
        client.get("https://api.openai.com/v1/chat/completions")

    transport.reset()
    assert len(transport._tool_call_window) == 0