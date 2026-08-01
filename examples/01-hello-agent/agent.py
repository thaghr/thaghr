"""thaghr's minimal example agent.

Not a demonstration of a real production agent, just enough surface
for the campaign runner to exercise: one call out to an LLM provider,
returning what happened. thaghr's runner calls `run()` once per trial,
handing it an httpx.Client whose transport may or may not be injecting
faults.
"""
from __future__ import annotations

import os

import httpx
import openai


def run(http_client: httpx.Client | None = None) -> dict:
    """Called once per trial. Returns a dict describing the outcome.

    Raises whatever the OpenAI SDK raises (RateLimitError, APIConnectionError,
    etc.) on failure; the campaign runner is responsible for catching that,
    not this function.
    """
    client = openai.OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY", "thaghr-demo-key"),
        http_client=http_client,
        max_retries=2,
    )
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Say hello in exactly three words."}],
    )
    usage = completion.usage.model_dump() if completion.usage else {}
    return {
        "content": completion.choices[0].message.content,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
    }
