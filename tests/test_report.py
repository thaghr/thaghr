from __future__ import annotations

import pytest

from thaghr.report import render_compare_report_card, render_report_card
from thaghr.schema import EpisodeResult, SubtaskOutcome


def _episode(trial: int, passed: bool, fault_fired: bool = False, error_type: str | None = None) -> EpisodeResult:
    return EpisodeResult.from_single_check(
        trial=trial,
        status="success" if passed else "error",
        error_type=error_type if not passed else None,
        latency_seconds=0.1,
        prompt_tokens=10,
        completion_tokens=5,
        cost_usd=0.001,
        passed=passed,
        fault_fired=fault_fired,
    )


class TestRenderReportCard:
    def test_contains_trial_count_and_headline(self):
        results = [_episode(i, passed=i < 8) for i in range(10)]
        card = render_report_card(results, k=1, example_name="01-hello-agent")
        assert "trials      10" in card
        assert "passed      8/10" in card
        assert "pass^1: 80%" in card
        assert "01-hello-agent" in card

    def test_falls_back_to_gds_when_pass_k_is_zero(self):
        results = []
        for i in range(10):
            ep = _episode(i, passed=False, error_type="HTTPStatusError")
            ep.subtask_results = {
                "partial": SubtaskOutcome(passed=True, weight=0.4),
                "rest": SubtaskOutcome(passed=False, weight=0.6),
            }
            results.append(ep)
        card = render_report_card(results, k=1, example_name="01-hello-agent")
        assert "GDS: 40%" in card
        assert "rounds to 0%" in card

    def test_shows_error_breakdown_when_errors_present(self):
        results = [_episode(i, passed=False, error_type="RuntimeError") for i in range(5)]
        card = render_report_card(results, k=1, example_name="ex")
        assert "errors      5/5 (RuntimeError)" in card

    def test_no_error_line_when_all_pass(self):
        results = [_episode(i, passed=True) for i in range(5)]
        card = render_report_card(results, k=1, example_name="ex")
        assert "errors" not in card

    def test_is_bounded_box_drawing(self):
        results = [_episode(i, passed=True) for i in range(5)]
        card = render_report_card(results, k=1, example_name="ex")
        assert card.startswith("┌")
        assert card.rstrip().endswith("┘")


class TestRichReportCard:
    def test_render_report_card_rich_runs_without_error(self, capsys):
        from thaghr.report import render_report_card_rich

        results = [_episode(i, passed=i < 8) for i in range(10)]
        render_report_card_rich(results, k=1, example_name="ex")
        captured = capsys.readouterr()
        assert "thaghr report card" in captured.out
        assert "80%" in captured.out

    def test_render_compare_report_card_rich_runs_without_error(self, capsys):
        from thaghr.report import render_compare_report_card_rich

        baseline = [_episode(i, passed=i < 8) for i in range(10)]
        faulted = [_episode(i, passed=i < 3, fault_fired=True) for i in range(5)]
        render_compare_report_card_rich(faulted, baseline, k=1, example_name="ex")
        captured = capsys.readouterr()
        assert "thaghr compare report card" in captured.out


class TestRenderCompareReportCard:
    def test_hand_computed_robustness_and_survival(self):
        # baseline: 8/10 pass at k=1 -> 80%
        baseline = [_episode(i, passed=i < 8) for i in range(10)]
        # faulted: 5 trials, fault fires in all 5, 3 survive -> pass 60%, survival 60%
        faulted = [_episode(i, passed=i < 3, fault_fired=True) for i in range(5)]
        card = render_compare_report_card(faulted, baseline, k=1, example_name="ex")
        assert "pass^1: 80%" in card  # baseline headline
        assert "pass^1: 60%" in card  # faulted headline
        # robustness = 0.6 / 0.8 = 75%
        assert "75% of baseline retained" in card
        assert "60% of fault-hit trials passed" in card

    def test_robustness_undefined_when_baseline_zero(self):
        baseline = [_episode(i, passed=False) for i in range(5)]
        faulted = [_episode(i, passed=False, fault_fired=True) for i in range(5)]
        card = render_compare_report_card(faulted, baseline, k=1, example_name="ex")
        assert "undefined (baseline itself unreliable)" in card

    def test_survival_undefined_when_no_fault_fired(self):
        baseline = [_episode(i, passed=True) for i in range(5)]
        faulted = [_episode(i, passed=True, fault_fired=False) for i in range(5)]
        card = render_compare_report_card(faulted, baseline, k=1, example_name="ex")
        assert "undefined (no trial hit a fault)" in card
