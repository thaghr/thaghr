"""Phase 7 telemetry driver.

Not a CLI subcommand. Starts the Prometheus metrics server once, then loops
run_campaign() against an example agent indefinitely, so thaghr_episode_results_total
and thaghr_faults_injected_total are live series a ServiceMonitor can actually scrape.

--fault-rate is read from the THAGHR_FAULT_RATE env var so we can crank it from
0.2 to something like 0.95 without rebuilding the image, that's how the
ThaghrErrorBudgetBlown alert gets deliberately triggered for the Phase 7 DoD.

THAGHR_SIMULATE_REPEAT_LOOP (default "true"): every loop iteration, deliberately
trigger repeat_loop_detected_total by running a stub ThaghrTransport that
returns an identical tool_call three times, the exact pattern from
tests/test_repeat_loop.py, run in-process here so the SAME Prometheus
registry Grafana/Alertmanager scrape actually sees it. Runs on every
iteration, not once at startup: a single one-time jump at process boot can
land before Prometheus's first scrape, meaning increase() never observes
a rise, since Prometheus only sees the metric already sitting at its new
value with no 0 baseline captured. Periodic retriggering guarantees
increase() sees real deltas within any evaluation window regardless of
scrape timing. No real agent naturally does this against a working
example, so this is a deliberate proof, not fabricated traffic disguised
as real. Set to "false" once the repeat-loop alert has been confirmed
firing, no need to keep re-triggering it indefinitely.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx

from thaghr.cli import _load_agent
from thaghr.faults.http_error import HTTPErrorFault
from thaghr.runner import run_campaign, CostBudgetExceeded
from thaghr.telemetry import start_metrics_server
from thaghr.transport import ThaghrTransport


class _StuckToolStub(httpx.BaseTransport):
    """Returns the same tool_call response every time, standing in for an
    agent stuck calling the same tool with the same args. Never touches the
    network. Same shape as the stub in tests/test_repeat_loop.py."""

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
                                {"function": {"name": self.tool_name, "arguments": self.arguments}}
                            ]
                        }
                    }
                ]
            },
            request=request,
        )


def _simulate_repeat_loop() -> None:
    stub = _StuckToolStub(tool_name="demo_stuck_tool", arguments='{"reason": "phase7-proof"}')
    transport = ThaghrTransport(faults=[], wrapped=stub)
    client = httpx.Client(transport=transport)
    for _ in range(3):
        client.get("https://api.openai.com/v1/chat/completions")
    print("thaghr telemetry driver: simulated repeat-loop trigger fired", file=sys.stderr)


def main() -> int:
    metrics_port = int(os.environ.get("THAGHR_METRICS_PORT", "9090"))
    fault_rate = float(os.environ.get("THAGHR_FAULT_RATE", "0.2"))
    example_dir = Path(os.environ.get("THAGHR_EXAMPLE", "examples/01-hello-agent"))
    trials_per_batch = int(os.environ.get("THAGHR_TRIALS_PER_BATCH", "5"))
    sleep_seconds = float(os.environ.get("THAGHR_LOOP_SLEEP", "10"))
    simulate_repeat_loop = os.environ.get("THAGHR_SIMULATE_REPEAT_LOOP", "true").lower() == "true"

    start_metrics_server(metrics_port)
    print(f"thaghr telemetry driver: metrics on :{metrics_port}, "
          f"fault_rate={fault_rate}, example={example_dir}", file=sys.stderr)

    agent_fn = _load_agent(example_dir)
    seed = 0

    while True:
        if simulate_repeat_loop:
            _simulate_repeat_loop()
        faults = [HTTPErrorFault(rate=fault_rate, seed=seed)] if fault_rate > 0 else []
        try:
            run_campaign(
                agent_fn=agent_fn,
                trials=trials_per_batch,
                faults=faults,
                max_cost=float(os.environ.get("THAGHR_MAX_COST", "5.0")),
                output_path=Path("/tmp/thaghr-loop-results.csv"),
            )
        except CostBudgetExceeded as exc:
            print(f"thaghr telemetry driver: cost budget hit, resetting: {exc}", file=sys.stderr)
        seed += 1
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    raise SystemExit(main())