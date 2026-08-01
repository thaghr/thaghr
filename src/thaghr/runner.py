"""Campaign runner. Runs a target agent function N times, giving each
trial a fresh ThaghrTransport carrying the configured fault stack, and
writes one CSV row per trial.

Cost enforcement: real API cost is only known after a trial completes
(token counts come back in the response), so the guardrail is checked
*before* each trial starts, against the running total from prior trials.
If the budget is already spent, the next trial is refused rather than
started. This means the campaign can land exactly at or slightly under
--max-cost, but will never knowingly start a trial once the prior
trials have already spent the budget.
"""
from __future__ import annotations

import csv
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import httpx

from thaghr.faults.http_error import HTTPErrorFault
from thaghr.transport import ThaghrTransport

# Rough per-1k-token pricing, gpt-4o-mini as of this writing. Used only
# for the --max-cost guardrail, not meant to be exact billing.
PRICE_PER_1K_PROMPT = 0.00015
PRICE_PER_1K_COMPLETION = 0.0006


class CostBudgetExceeded(Exception):
    """Raised when starting the next trial would exceed --max-cost."""


@dataclass
class TrialResult:
    trial: int
    status: str  # "success" | "error"
    error_type: str | None
    latency_seconds: float
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


def _estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (
        prompt_tokens / 1000 * PRICE_PER_1K_PROMPT
        + completion_tokens / 1000 * PRICE_PER_1K_COMPLETION
    )


def run_campaign(
    agent_fn: Callable[[httpx.Client], dict],
    trials: int,
    faults: list[HTTPErrorFault],
    max_cost: float,
    output_path: Path,
) -> list[TrialResult]:
    results: list[TrialResult] = []
    total_cost = 0.0

    for i in range(trials):
        if total_cost >= max_cost:
            _write_csv(results, output_path)
            raise CostBudgetExceeded(
                f"refusing to start trial {i}: ${total_cost:.4f} already spent, "
                f"--max-cost is ${max_cost:.4f}"
            )

        transport = ThaghrTransport(faults=[f for f in faults])
        client = httpx.Client(transport=transport)
        start = time.monotonic()
        try:
            outcome = agent_fn(client)
            elapsed = time.monotonic() - start
            prompt_tokens = outcome.get("prompt_tokens", 0)
            completion_tokens = outcome.get("completion_tokens", 0)
            cost = _estimate_cost(prompt_tokens, completion_tokens)
            total_cost += cost
            results.append(
                TrialResult(
                    trial=i,
                    status="success",
                    error_type=None,
                    latency_seconds=elapsed,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=cost,
                )
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            results.append(
                TrialResult(
                    trial=i,
                    status="error",
                    error_type=type(exc).__name__,
                    latency_seconds=elapsed,
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_usd=0.0,
                )
            )
        finally:
            client.close()

    _write_csv(results, output_path)
    return results


def _write_csv(results: list[TrialResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "trial",
        "status",
        "error_type",
        "latency_seconds",
        "prompt_tokens",
        "completion_tokens",
        "cost_usd",
    ]
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))
