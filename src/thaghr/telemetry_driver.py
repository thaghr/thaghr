"""Phase 7 telemetry driver.

Not a CLI subcommand. Starts the Prometheus metrics server once, then loops
run_campaign() against an example agent indefinitely, so thaghr_episode_results_total
and thaghr_faults_injected_total are live series a ServiceMonitor can actually scrape.

--fault-rate is read from the THAGHR_FAULT_RATE env var so we can crank it from
0.2 to something like 0.95 without rebuilding the image, that's how the
ThaghrErrorBudgetBlown alert gets deliberately triggered for the Phase 7 DoD.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from thaghr.cli import _load_agent
from thaghr.faults.http_error import HTTPErrorFault
from thaghr.runner import run_campaign, CostBudgetExceeded
from thaghr.telemetry import start_metrics_server


def main() -> int:
    metrics_port = int(os.environ.get("THAGHR_METRICS_PORT", "9090"))
    fault_rate = float(os.environ.get("THAGHR_FAULT_RATE", "0.2"))
    example_dir = Path(os.environ.get("THAGHR_EXAMPLE", "examples/01-hello-agent"))
    trials_per_batch = int(os.environ.get("THAGHR_TRIALS_PER_BATCH", "5"))
    sleep_seconds = float(os.environ.get("THAGHR_LOOP_SLEEP", "10"))

    start_metrics_server(metrics_port)
    print(f"thaghr telemetry driver: metrics on :{metrics_port}, "
          f"fault_rate={fault_rate}, example={example_dir}", file=sys.stderr)

    agent_fn = _load_agent(example_dir)
    seed = 0

    while True:
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