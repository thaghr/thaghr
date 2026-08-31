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
import json
import time
from pathlib import Path
from typing import Callable

import httpx

from thaghr.faults.http_error import HTTPErrorFault
from thaghr.schema import EpisodeResult
from thaghr.transport import ThaghrTransport
from thaghr.telemetry import episode_results_total

# Rough per-1k-token pricing, gpt-4o-mini as of this writing. Used only
# for the --max-cost guardrail, not meant to be exact billing.
PRICE_PER_1K_PROMPT = 0.00015
PRICE_PER_1K_COMPLETION = 0.0006


class CostBudgetExceeded(Exception):
    """Raised when starting the next trial would exceed --max-cost."""


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
) -> list[EpisodeResult]:
    """Runs `trials` episodes against `agent_fn`. Every episode is recorded
    as an EpisodeResult using the single_check() fallback: one subtask
    named "pass", full weight, driven by whether the trial raised. Real
    subtask decomposition is a Phase 3-5 UX decision (see thaghr skill),
    not built here; examples/01-hello-agent stays on single_check() since
    decomposing a one-call hello-world agent would be overengineering for
    what it's meant to demonstrate."""
    results: list[EpisodeResult] = []
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
                EpisodeResult.from_single_check(
                    trial=i,
                    status="success",
                    error_type=None,
                    latency_seconds=elapsed,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=cost,
                    passed=True,
                    fault_fired=_any_fault_fired(transport),
                )
            )
            episode_results_total.labels(result="pass").inc()
        except Exception as exc:
            elapsed = time.monotonic() - start
            results.append(
                EpisodeResult.from_single_check(
                    trial=i,
                    status="error",
                    error_type=type(exc).__name__,
                    latency_seconds=elapsed,
                    prompt_tokens=0,
                    completion_tokens=0,
                    cost_usd=0.0,
                    passed=False,
                    fault_fired=_any_fault_fired(transport),
                )
            )
            episode_results_total.labels(result="fail").inc()
        finally:
            client.close()

    _write_csv(results, output_path)
    return results


def _any_fault_fired(transport: ThaghrTransport) -> bool:
    """True if any request in this trial had a fault injected. Backs
    fault_tolerance() in metrics.py, which needs to know which trials
    actually encountered a fault versus which ones didn't."""
    return any(entry["injected_status"] is not None for entry in transport.request_log)


def _write_csv(results: list[EpisodeResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "trial",
        "status",
        "error_type",
        "latency_seconds",
        "prompt_tokens",
        "completion_tokens",
        "cost_usd",
        "gds",
        "pass_1",
        "subtask_results",
        "fault_fired",
    ]
    with output_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "trial": r.trial,
                    "status": r.status,
                    "error_type": r.error_type,
                    "latency_seconds": r.latency_seconds,
                    "prompt_tokens": r.prompt_tokens,
                    "completion_tokens": r.completion_tokens,
                    "cost_usd": r.cost_usd,
                    "gds": r.gds(),
                    "pass_1": r.pass_1(),
                    "subtask_results": json.dumps(
                        {
                            name: {"passed": o.passed, "weight": o.weight}
                            for name, o in r.subtask_results.items()
                        }
                    ),
                    "fault_fired": r.fault_fired,
                }
            )
