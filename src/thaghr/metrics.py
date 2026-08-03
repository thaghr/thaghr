"""Reliability surface. Phase 4.

pass^k is the one metric that must not drift: `pass^k`, never `pass@k`.
pass@k asks "did it succeed at least once in k tries" and rewards luck.
pass^k asks "did it succeed *every* time in k tries" and measures
reliability. Source: the tau-bench paper (Yao et al., 2024), eq. in
section on agent consistency:

    pass^k = E_task[ C(c, k) / C(n, k) ]

where n is the number of independent trials run for a task, c is how
many of them succeeded, and C is "n choose k". This is the unbiased
estimator for "probability that all k trials in a random k-subset of
the n trials succeeded", the same construction as the Codex pass@k
estimator (Chen et al., 2021) but for "all k" instead of "at least 1".

tau-bench's own language calls what pass^k measures "agent consistency"
(see Yao et al., section 4.3: "Agent consistency via pass^k"). There is
no separate consistency formula in the paper; pass^k *is* the
consistency metric. thaghr does not build a second one.

thaghr adds two metrics tau-bench doesn't define, both specific to
fault injection:

    robustness(faulted, baseline, k) = pass^k(faulted) / pass^k(baseline)

How much of the agent's baseline (fault-free) reliability survives
under chaos, as a fraction. Undefined (None) when the baseline itself
is 0: there's no reliability to retain a fraction of.

    fault_tolerance(results) = survival rate among trials a fault
    actually hit

Of the trials where `fault_fired` is True, the fraction that still
passed. Undefined (None) if no trial in the campaign ever hit a fault,
since there's nothing to measure survival against.
"""
from __future__ import annotations

from math import comb

from thaghr.schema import EpisodeResult


def pass_k(results: list[EpisodeResult], k: int) -> float:
    """pass^k for one task's campaign: C(c, k) / C(n, k), n = len(results),
    c = how many passed pass_1(). Raises ValueError if k > n or k < 1,
    since you can't sample a k-subset from fewer than k trials."""
    n = len(results)
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    if k > n:
        raise ValueError(f"k ({k}) cannot exceed the number of trials ({n})")
    c = sum(1 for r in results if r.pass_1())
    return comb(c, k) / comb(n, k)


def robustness(faulted: list[EpisodeResult], baseline: list[EpisodeResult], k: int) -> float | None:
    """Fraction of baseline reliability retained under fault injection.
    None if baseline pass^k is 0: the agent wasn't reliable to begin
    with, so there's nothing meaningful to express as a fraction of."""
    baseline_pass_k = pass_k(baseline, k)
    if baseline_pass_k == 0.0:
        return None
    return pass_k(faulted, k) / baseline_pass_k


def fault_tolerance(results: list[EpisodeResult]) -> float | None:
    """Survival rate among trials where a fault actually fired. None if
    no trial in `results` ever hit a fault (nothing to measure)."""
    hit = [r for r in results if r.fault_fired]
    if not hit:
        return None
    survived = sum(1 for r in hit if r.pass_1())
    return survived / len(hit)


def primary_metric(results: list[EpisodeResult], k: int) -> tuple[str, float]:
    """The headline number for the report card (Phase 5). Normally
    pass^k. But pass^k is brutal at low n: a single agent that's actually
    making partial progress can round to a flat 0%, which reads as
    "does nothing" when it isn't. When pass^k rounds to 0% (< 0.5%,
    i.e. what displays as "0%" at whole-percent rounding), fall back to
    mean GDS so the card shows the partial-credit signal instead of a
    misleadingly blank zero."""
    pk = pass_k(results, k)
    if round(pk * 100) == 0:
        mean_gds = sum(r.gds() for r in results) / len(results) if results else 0.0
        return ("GDS", mean_gds)
    return ("pass^k", pk)
