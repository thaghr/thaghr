from __future__ import annotations

import pytest

from thaghr.schema import EpisodeResult, SubtaskOutcome, TaskDefinition


class TestTaskDefinition:
    def test_single_check_is_one_full_weight_subtask(self):
        task = TaskDefinition.single_check()
        assert task.subtasks == [("pass", 1.0)]

    def test_weights_must_sum_to_one(self):
        with pytest.raises(ValueError):
            TaskDefinition(subtasks=[("a", 0.5), ("b", 0.4)])

    def test_valid_weights_construct_cleanly(self):
        task = TaskDefinition(subtasks=[("a", 0.3), ("b", 0.7)])
        assert task.subtasks == [("a", 0.3), ("b", 0.7)]


class TestEpisodeResultGDS:
    def _episode(self, **subtasks: tuple[bool, float]) -> EpisodeResult:
        return EpisodeResult(
            trial=0,
            status="success",
            error_type=None,
            latency_seconds=0.1,
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=0.0,
            subtask_results={
                name: SubtaskOutcome(passed=passed, weight=weight)
                for name, (passed, weight) in subtasks.items()
            },
        )

    def test_gds_is_zero_with_no_subtask_results(self):
        episode = self._episode()
        assert episode.gds() == 0.0

    def test_gds_is_full_weight_when_all_pass(self):
        episode = self._episode(a=(True, 0.6), b=(True, 0.4))
        assert episode.gds() == pytest.approx(1.0)

    def test_gds_is_partial_when_some_fail(self):
        episode = self._episode(a=(True, 0.6), b=(False, 0.4))
        assert episode.gds() == pytest.approx(0.6)

    def test_pass_1_false_with_no_subtask_results(self):
        episode = self._episode()
        assert episode.pass_1() is False

    def test_pass_1_true_only_if_every_subtask_passed(self):
        assert self._episode(a=(True, 0.5), b=(True, 0.5)).pass_1() is True
        assert self._episode(a=(True, 0.5), b=(False, 0.5)).pass_1() is False


class TestFromSingleCheck:
    def test_passed_true_yields_full_gds_and_pass_1(self):
        episode = EpisodeResult.from_single_check(
            trial=3,
            status="success",
            error_type=None,
            latency_seconds=0.2,
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=0.001,
            passed=True,
        )
        assert episode.subtask_results == {"pass": SubtaskOutcome(passed=True, weight=1.0)}
        assert episode.gds() == 1.0
        assert episode.pass_1() is True

    def test_passed_false_yields_zero_gds_and_failed_pass_1(self):
        episode = EpisodeResult.from_single_check(
            trial=4,
            status="error",
            error_type="RuntimeError",
            latency_seconds=0.05,
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=0.0,
            passed=False,
        )
        assert episode.gds() == 0.0
        assert episode.pass_1() is False
