"""thaghr CLI entry point."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from thaghr.faults.http_error import HTTPErrorFault
from thaghr.report import (
    render_compare_report_card,
    render_compare_report_card_rich,
    render_report_card,
    render_report_card_rich,
)
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
    run_parser.add_argument(
        "--k", type=int, default=1, help="k for the pass^k headline metric on the report card"
    )
    run_parser.add_argument(
        "--pretty", action="store_true", help="colorized report card via rich (pip install thaghr[pretty])"
    )

    compare_parser = subparsers.add_parser(
        "compare", help="run a baseline and a faulted campaign, report robustness and survival"
    )
    compare_parser.add_argument(
        "example", type=Path, help="path to an examples/ directory containing agent.py"
    )
    compare_parser.add_argument("--baseline-trials", type=int, default=10)
    compare_parser.add_argument("--fault-trials", type=int, default=10)
    compare_parser.add_argument(
        "--max-cost", type=float, default=1.0, help="cap applied to each campaign separately, not combined"
    )
    compare_parser.add_argument(
        "--fault-rate",
        type=float,
        default=0.2,
        help="probability an HTTP 429 fires per call in the faulted campaign",
    )
    compare_parser.add_argument("--seed", type=int, default=0)
    compare_parser.add_argument("--output-dir", type=Path, default=Path("."))
    compare_parser.add_argument(
        "--k", type=int, default=1, help="k for the pass^k headline metric on the report card"
    )
    compare_parser.add_argument(
        "--pretty", action="store_true", help="colorized report card via rich (pip install thaghr[pretty])"
    )

    proxy_parser = subparsers.add_parser(
        "proxy", help="run thaghr as an HTTP proxy in front of an OpenAI-compatible endpoint"
    )
    proxy_parser.add_argument(
        "--upstream", required=True, help="upstream OpenAI-compatible base URL, e.g. https://api.openai.com"
    )
    proxy_parser.add_argument(
        "--fault-rate",
        type=float,
        default=0.2,
        help="probability an HTTP 429 fires per call, 0 disables fault injection",
    )
    proxy_parser.add_argument("--seed", type=int, default=0)
    proxy_parser.add_argument("--host", default="127.0.0.1")
    proxy_parser.add_argument("--port", type=int, default=8135)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        return _run(args)
    if args.command == "compare":
        return _compare(args)
    if args.command == "proxy":
        return _proxy(args)

    parser.print_help()
    return 1


def _run(args: argparse.Namespace) -> int:
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

    print(f"thaghr: {len(results)} trials complete, wrote {args.output}\n")
    if args.pretty:
        render_report_card_rich(results, args.k, example_name=args.example.name)
    else:
        print(render_report_card(results, args.k, example_name=args.example.name))
    return 0


def _compare(args: argparse.Namespace) -> int:
    agent_fn = _load_agent(args.example)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        baseline = run_campaign(
            agent_fn=agent_fn,
            trials=args.baseline_trials,
            faults=[],
            max_cost=args.max_cost,
            output_path=args.output_dir / "baseline.csv",
        )
        faulted = run_campaign(
            agent_fn=agent_fn,
            trials=args.fault_trials,
            faults=[HTTPErrorFault(rate=args.fault_rate, seed=args.seed)],
            max_cost=args.max_cost,
            output_path=args.output_dir / "faulted.csv",
        )
    except CostBudgetExceeded as exc:
        print(f"thaghr: campaign stopped, {exc}", file=sys.stderr)
        return 1

    print(f"thaghr: wrote {args.output_dir / 'baseline.csv'} and {args.output_dir / 'faulted.csv'}\n")
    if args.pretty:
        render_compare_report_card_rich(faulted, baseline, args.k, example_name=args.example.name)
    else:
        print(render_compare_report_card(faulted, baseline, args.k, example_name=args.example.name))
    return 0


def _proxy(args: argparse.Namespace) -> int:
    from thaghr.proxy import run_proxy

    run_proxy(
        upstream_base_url=args.upstream,
        fault_rate=args.fault_rate,
        seed=args.seed,
        host=args.host,
        port=args.port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
