"""Phase 5: the report card. Renders a terminal-friendly summary of a
campaign (or a baseline-vs-faulted comparison) that a stranger can
understand in under 20 seconds, screenshot-worthy unedited.

Plain text is the only real output format: box-drawing characters, no
dependencies, works in any terminal and in a screenshot. --pretty adds
a colorized rich rendering on top, entirely optional; nothing here
requires it.

Headline number is whatever primary_metric() returns: pass^k normally,
GDS when pass^k rounds to 0%. Both axes are not shown side by side by
default (Phase 5 DoD: cut GDS if two axes make the card harder to
parse), the fallback logic in primary_metric() already decides which
one the reader needs.
"""
from __future__ import annotations

from thaghr.metrics import fault_tolerance, primary_metric, robustness
from thaghr.schema import EpisodeResult

_MIN_WIDTH = 44


def _box(lines: list[str]) -> str:
    content_width = max(len(line) for line in lines if line != "---")
    width = max(_MIN_WIDTH, content_width + 2)
    top = "┌" + "─" * width + "┐"
    bottom = "└" + "─" * width + "┘"
    divider = "├" + "─" * width + "┤"
    body = []
    for line in lines:
        if line == "---":
            body.append(divider)
        else:
            body.append("│ " + line.ljust(width - 2) + " │")
    return "\n".join([top, *body, bottom])


def _headline(results: list[EpisodeResult], k: int) -> str:
    name, value = primary_metric(results, k)
    if name == "pass^k":
        return f"pass^{k}: {value:.0%}"
    return f"GDS: {value:.0%}  (pass^{k} rounds to 0%)"


def render_report_card(results: list[EpisodeResult], k: int, example_name: str) -> str:
    """Single-campaign report card: trial count, headline metric, and an
    error breakdown if anything failed with a raised exception."""
    n = len(results)
    passed = sum(1 for r in results if r.pass_1())
    errored = sum(1 for r in results if r.status == "error")

    lines = [
        "thaghr report card",
        example_name,
        "---",
        f"trials      {n}",
        f"passed      {passed}/{n}",
        _headline(results, k),
    ]
    if errored:
        top_error = _most_common_error(results)
        lines.append(f"errors      {errored}/{n} ({top_error})")
    return _box(lines)


def render_compare_report_card(
    faulted: list[EpisodeResult],
    baseline: list[EpisodeResult],
    k: int,
    example_name: str,
) -> str:
    """Baseline-vs-faulted report card: both headline numbers, plus
    robustness and fault_tolerance, which need this pairing to mean
    anything."""
    base_headline = _headline(baseline, k)
    fault_headline = _headline(faulted, k)

    rob = robustness(faulted, baseline, k)
    rob_line = f"robustness  {rob:.0%} of baseline retained" if rob is not None else "robustness  undefined (baseline itself unreliable)"

    tol = fault_tolerance(faulted)
    tol_line = f"survival    {tol:.0%} of fault-hit trials passed" if tol is not None else "survival    undefined (no trial hit a fault)"

    lines = [
        "thaghr compare report card",
        example_name,
        "---",
        f"baseline    {base_headline}  ({len(baseline)} trials)",
        f"faulted     {fault_headline}  ({len(faulted)} trials)",
        "---",
        rob_line,
        tol_line,
    ]
    return _box(lines)


def _most_common_error(results: list[EpisodeResult]) -> str:
    counts: dict[str, int] = {}
    for r in results:
        if r.error_type:
            counts[r.error_type] = counts.get(r.error_type, 0) + 1
    if not counts:
        return "unknown"
    return max(counts, key=counts.get)


def render_report_card_rich(results: list[EpisodeResult], k: int, example_name: str) -> None:
    """Colorized variant, printed directly to the console rather than
    returned as a string, since rich renders through its own Console.
    Raises ImportError with a clear message if rich isn't installed,
    --pretty is opt-in, not a hard dependency of thaghr itself."""
    try:
        from rich.console import Console
        from rich.panel import Panel
    except ImportError as exc:
        raise ImportError(
            "rich is not installed. Install it with `pip install thaghr[pretty]` "
            "or drop --pretty to use the plain-text report card."
        ) from exc

    n = len(results)
    passed = sum(1 for r in results if r.pass_1())
    name, value = primary_metric(results, k)
    headline = f"pass^{k}: {value:.0%}" if name == "pass^k" else f"GDS: {value:.0%} (pass^{k} rounds to 0%)"
    color = _severity_color(value)

    body = f"trials  {n}\npassed  {passed}/{n}\n[bold {color}]{headline}[/bold {color}]"
    Console().print(Panel(body, title="thaghr report card", subtitle=example_name))


def _severity_color(value: float) -> str:
    return "green" if value >= 0.7 else "yellow" if value >= 0.3 else "red"


def render_compare_report_card_rich(
    faulted: list[EpisodeResult],
    baseline: list[EpisodeResult],
    k: int,
    example_name: str,
) -> None:
    try:
        from rich.console import Console
        from rich.panel import Panel
    except ImportError as exc:
        raise ImportError(
            "rich is not installed. Install it with `pip install thaghr[pretty]` "
            "or drop --pretty to use the plain-text report card."
        ) from exc

    base_name, base_value = primary_metric(baseline, k)
    fault_name, fault_value = primary_metric(faulted, k)
    base_headline = f"pass^{k}: {base_value:.0%}" if base_name == "pass^k" else f"GDS: {base_value:.0%}"
    fault_headline = f"pass^{k}: {fault_value:.0%}" if fault_name == "pass^k" else f"GDS: {fault_value:.0%}"
    base_color = _severity_color(base_value)
    fault_color = _severity_color(fault_value)

    rob = robustness(faulted, baseline, k)
    if rob is not None:
        rob_line = f"[bold {_severity_color(rob)}]{rob:.0%}[/bold {_severity_color(rob)}] of baseline retained"
    else:
        rob_line = "[dim]undefined (baseline itself unreliable)[/dim]"

    tol = fault_tolerance(faulted)
    if tol is not None:
        tol_line = f"[bold {_severity_color(tol)}]{tol:.0%}[/bold {_severity_color(tol)}] of fault-hit trials passed"
    else:
        tol_line = "[dim]undefined (no trial hit a fault)[/dim]"

    body = (
        f"baseline    [bold {base_color}]{base_headline}[/bold {base_color}]  ({len(baseline)} trials)\n"
        f"faulted     [bold {fault_color}]{fault_headline}[/bold {fault_color}]  ({len(faulted)} trials)\n\n"
        f"robustness  {rob_line}\n"
        f"survival    {tol_line}"
    )
    Console().print(Panel(body, title="thaghr compare report card", subtitle=example_name))