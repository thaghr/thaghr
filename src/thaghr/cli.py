"""thaghr CLI entry point."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from thaghr.faults.http_error import HTTPErrorFault
from thaghr.runner import CostBudgetExceeded, run_campaign


def _load_agent(example_dir: Path):
    agent_path = example_dir / "agent.py"
    if not agent_path.exists():
        raise FileNotFoundError(f"no agent.py found in {example_dir}")
    spec = importlib.util.spec_from_file_location("thaghr_target_agent", agent_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    if not hasattr(module, "run"):
        raise AttributeError(f"{agent_path} has no run() function")
    return module.run


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thaghr")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run a fault-injection campaign")
    run_parser.add_argument(
        "example", type=Path, help="path to an examples/ directory containing agent.py"
    )
    run_parser.add_argument("--trials", type=int, default=10)
    run_parser.add_argument("--max-cost", type=float, default=1.0)
    run_parser.add_argument(
        "--fault-rate",
        type=float,
        default=0.0,
        help="probability an HTTP 429 fires per call, 0 disables fault injection",
    )
    run_parser.add_argument("--seed", type=int, default=0)
    run_parser.add_argument("--output", type=Path, default=Path("thaghr-results.csv"))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command != "run":
        parser.print_help()
        return 1

    agent_fn = _load_agent(args.example)
    faults = (
        [HTTPErrorFault(rate=args.fault_rate, seed=args.seed)] if args.fault_rate > 0 else []
    )

    try:
        results = run_campaign(
            agent_fn=agent_fn,
            trials=args.trials,
            faults=faults,
            max_cost=args.max_cost,
            output_path=args.output,
        )
    except CostBudgetExceeded as exc:
        print(f"thaghr: campaign stopped, {exc}", file=sys.stderr)
        return 1

    successes = sum(1 for r in results if r.status == "success")
    print(f"thaghr: {len(results)} trials complete ({successes} succeeded), wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
