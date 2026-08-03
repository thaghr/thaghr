from __future__ import annotations

import pytest

from thaghr.metrics import fault_tolerance, pass_k, primary_metric, robustness
from thaghr.schema import EpisodeResult


def _episode(trial: int, passed: bool, fault_fired: bool = False, gds: float | None = None) -> EpisodeResult:
    """Build an EpisodeResult via single_check semantics. If gds is given,
    override with a two-subtask split so gds() lands on that value while
    pass_1() still reflects `passed` (used for the primary_metric tests,
    where we need partial credit distinct from pass/fail)."""
    ep = EpisodeResult.from_single_check(
        trial=trial,
        status="success" if passed else "error",
        error_type=None if passed else "SimulatedFailure",
        latency_seconds=0.1,
        prompt_tokens=10,
        completion_tokens=5,
        cost_usd=0.001,
        passed=passed,
        fault_fired=fault_fired,
    )
    if gds is not None:
        from thaghr.schema import SubtaskOutcome

        ep.subtask_results = {
            "partial": SubtaskOutcome(passed=True, weight=gds),
            "rest": SubtaskOutcome(passed=False, weight=1 - gds),
        }
    return ep


class TestPassK:
    def test_all_pass_k1_is_one(self):
        results = [_episode(i, passed=True) for i in range(5)]
        assert pass_k(results, 1) == pytest.approx(1.0)

    def test_hand_computed_n5_c3_k1(self):
        # C(3,1)/C(5,1) = 3/5 = 0.6
        results = [_episode(i, passed=i < 3) for i in range(5)]
        assert pass_k(results, 1) == pytest.approx(0.6)

    def test_hand_computed_n5_c3_k2(self):
        # C(3,2)/C(5,2) = 3/10 = 0.3
        results = [_episode(i, passed=i < 3) for i in range(5)]
        assert pass_k(results, 2) == pytest.approx(0.3)

    def test_hand_computed_n5_c3_k3(self):
        # C(3,3)/C(5,3) = 1/10 = 0.1
        results = [_episode(i, passed=i < 3) for i in range(5)]
        assert pass_k(results, 3) == pytest.approx(0.1)

    def test_hand_computed_n5_c2_k3_is_zero(self):
        # C(2,3) is 0 (can't choose 3 successes from only 2) -> 0/C(5,3) = 0.0
        results = [_episode(i, passed=i < 2) for i in range(5)]
        assert pass_k(results, 3) == pytest.approx(0.0)

    def test_hand_computed_n10_c6_k4(self):
        # C(6,4)/C(10,4) = 15/210 = 1/14
        results = [_episode(i, passed=i < 6) for i in range(10)]
        assert pass_k(results, 4) == pytest.approx(15 / 210)

    def test_all_fail_is_zero_at_any_k(self):
        results = [_episode(i, passed=False) for i in range(5)]
        assert pass_k(results, 1) == pytest.approx(0.0)
        assert pass_k(results, 3) == pytest.approx(0.0)

    def test_k_greater_than_n_raises(self):
        results = [_episode(i, passed=True) for i in range(3)]
        with pytest.raises(ValueError):
            pass_k(results, 4)

    def test_k_zero_raises(self):
        results = [_episode(i, passed=True) for i in range(3)]
        with pytest.raises(ValueError):
            pass_k(results, 0)


class TestRobustness:
    def test_hand_computed_ratio(self):
        # baseline: 8/10 pass at k=1 -> 0.8. faulted: 4/10 pass at k=1 -> 0.4.
        # robustness = 0.4 / 0.8 = 0.5
        baseline = [_episode(i, passed=i < 8) for i in range(10)]
        faulted = [_episode(i, passed=i < 4) for i in range(10)]
        assert robustness(faulted, baseline, 1) == pytest.approx(0.5)

    def test_full_retention_when_faults_dont_hurt(self):
        baseline = [_episode(i, passed=i < 8) for i in range(10)]
        faulted = [_episode(i, passed=i < 8) for i in range(10)]
        assert robustness(faulted, baseline, 1) == pytest.approx(1.0)

    def test_zero_baseline_is_undefined_not_zero(self):
        baseline = [_episode(i, passed=False) for i in range(10)]
        faulted = [_episode(i, passed=False) for i in range(10)]
        assert robustness(faulted, baseline, 1) is None


class TestFaultTolerance:
    def test_hand_computed_survival_rate(self):
        # 5 trials, fault fires in 3 of them, 2 of those 3 still pass.
        results = [
            _episode(0, passed=True, fault_fired=True),
            _episode(1, passed=True, fault_fired=True),
            _episode(2, passed=False, fault_fired=True),
            _episode(3, passed=True, fault_fired=False),
            _episode(4, passed=False, fault_fired=False),
        ]
        assert fault_tolerance(results) == pytest.approx(2 / 3)

    def test_no_faults_fired_is_undefined(self):
        results = [_episode(i, passed=True, fault_fired=False) for i in range(5)]
        assert fault_tolerance(results) is None

    def test_all_faulted_trials_survive(self):
        results = [_episode(i, passed=True, fault_fired=True) for i in range(5)]
        assert fault_tolerance(results) == pytest.approx(1.0)

    def test_all_faulted_trials_fail(self):
        results = [_episode(i, passed=False, fault_fired=True) for i in range(5)]
        assert fault_tolerance(results) == pytest.approx(0.0)


class TestPrimaryMetric:
    def test_reports_pass_k_when_nonzero(self):
        results = [_episode(i, passed=i < 8) for i in range(10)]
        name, value = primary_metric(results, 1)
        assert name == "pass^k"
        assert value == pytest.approx(0.8)

    def test_falls_back_to_gds_when_pass_k_rounds_to_zero(self):
        # All fail pass_1 (pass^k = 0) but each carries partial credit.
        results = [_episode(i, passed=False, gds=0.4) for i in range(10)]
        name, value = primary_metric(results, 1)
        assert name == "GDS"
        assert value == pytest.approx(0.4)

    def test_small_nonzero_pass_k_that_rounds_to_zero_still_falls_back(self):
        # 1 pass out of 200 trials at k=1: pass^k = 1/200 = 0.5% exactly
        # at the boundary; round(0.5) rounds to 0 with Python's banker's
        # rounding, so this should still fall back to GDS.
        results = [_episode(i, passed=(i == 0), gds=0.2 if i != 0 else 1.0) for i in range(200)]
        name, value = primary_metric(results, 1)
        assert name == "GDS"
