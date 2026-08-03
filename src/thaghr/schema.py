"""GDS schema, locked pre-Phase 3, 01 Aug 2026. Do not re-litigate shape here.

TaskDefinition describes how a task decomposes into weighted subtasks.
EpisodeResult is the record of one trial's outcome, carrying per-subtask
pass/fail plus the weight each subtask was worth, so gds() and pass_1()
are self-contained and don't need the TaskDefinition to be replayed
alongside the result.

single_check() is the fallback for users who don't decompose tasks: one
subtask called "pass" at full weight. Real decomposition (registering
named checks against a TaskDefinition) is a Phase 3-5 UX decision, not
answered here.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TaskDefinition:
    """A task's subtasks and their weights. Weights must sum to 1.0."""

    subtasks: list[tuple[str, float]]

    def __post_init__(self) -> None:
        total = sum(weight for _, weight in self.subtasks)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"subtask weights must sum to 1.0, got {total}")

    @classmethod
    def single_check(cls) -> "TaskDefinition":
        """Fallback for tasks that aren't decomposed: one subtask, full weight."""
        return cls(subtasks=[("pass", 1.0)])


@dataclass
class SubtaskOutcome:
    passed: bool
    weight: float


@dataclass
class EpisodeResult:
    """One trial's outcome. Replaces TrialResult as of the Phase 3
    EpisodeResult swap (see thaghr skill, Phase 3 status)."""

    trial: int
    status: str  # "success" | "error"
    error_type: str | None
    latency_seconds: float
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    subtask_results: dict[str, SubtaskOutcome] = field(default_factory=dict)
    fault_fired: bool = False

    def gds(self) -> float:
        """Graded Degradation Score: weighted fraction of subtasks passed,
        0.0-1.0. 0.0 if there are no subtask results (episode errored
        before any subtask could be checked, or was never populated)."""
        if not self.subtask_results:
            return 0.0
        return sum(o.weight for o in self.subtask_results.values() if o.passed)

    def pass_1(self) -> bool:
        """Strict binary pass: True only if every subtask passed. This is
        the per-episode unit pass^k is built from; there is no partial
        credit here, that's what gds() is for."""
        if not self.subtask_results:
            return False
        return all(o.passed for o in self.subtask_results.values())

    @classmethod
    def from_single_check(
        cls,
        *,
        trial: int,
        status: str,
        error_type: str | None,
        latency_seconds: float,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
        passed: bool,
        fault_fired: bool = False,
    ) -> "EpisodeResult":
        """Convenience constructor for the single_check() fallback: one
        subtask called "pass" at full weight, driven by whether the trial
        succeeded overall."""
        return cls(
            trial=trial,
            status=status,
            error_type=error_type,
            latency_seconds=latency_seconds,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            subtask_results={"pass": SubtaskOutcome(passed=passed, weight=1.0)},
            fault_fired=fault_fired,
        )
