"""thaghr's minimal example agent.

Not a demonstration of a real production agent, just enough surface
for the campaign runner to exercise: one call out to an LLM provider,
returning what happened. thaghr's runner calls `run()` once per trial,
handing it an httpx.Client whose transport may or may not be injecting
faults.

Defaults to OpenAI. Works against any OpenAI-compatible endpoint (Gemini,
for instance) by setting THAGHR_DEMO_BASE_URL and THAGHR_DEMO_MODEL, so
you don't need an OpenAI key just to run this example. For Gemini:
OPENAI_API_KEY=<your gemini key>
THAGHR_DEMO_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
THAGHR_DEMO_MODEL=gemini-3.6-flash (check ai.google.dev/gemini-api/docs/openai
for the current model name, Google updates these)
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
        base_url=os.environ.get("THAGHR_DEMO_BASE_URL"),
        http_client=http_client,
        max_retries=2,
    )
    model = os.environ.get("THAGHR_DEMO_MODEL", "gpt-4o-mini")
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say hello in exactly three words."}],
    )
    usage = completion.usage.model_dump() if completion.usage else {}
    return {
        "content": completion.choices[0].message.content,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
    }
