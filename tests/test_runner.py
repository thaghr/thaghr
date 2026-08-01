from __future__ import annotations

import csv

import httpx
import pytest

from thaghr.faults.http_error import HTTPErrorFault
from thaghr.runner import CostBudgetExceeded, run_campaign


def _stub_agent_success(client: httpx.Client) -> dict:
    return {"content": "hi", "prompt_tokens": 10, "completion_tokens": 5}


def _stub_agent_flaky(client: httpx.Client) -> dict:
    # Deliberately doesn't catch anything; a real trial failure looks
    # like this raising, and the runner is responsible for catching it.
    raise RuntimeError("simulated agent crash")


class TestRunCampaign:
    def test_writes_one_row_per_trial(self, tmp_path):
        output = tmp_path / "results.csv"
        results = run_campaign(
            agent_fn=_stub_agent_success,
            trials=50,
            faults=[],
            max_cost=100.0,
            output_path=output,
        )

        assert len(results) == 50
        with output.open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 50
        assert all(r["status"] == "success" for r in rows)

    def test_trial_numbers_are_sequential(self, tmp_path):
        output = tmp_path / "results.csv"
        results = run_campaign(
            agent_fn=_stub_agent_success, trials=10, faults=[], max_cost=100.0, output_path=output
        )
        assert [r.trial for r in results] == list(range(10))

    def test_agent_exception_recorded_as_error_row_not_a_crash(self, tmp_path):
        output = tmp_path / "results.csv"
        results = run_campaign(
            agent_fn=_stub_agent_flaky, trials=5, faults=[], max_cost=100.0, output_path=output
        )

        assert len(results) == 5
        assert all(r.status == "error" for r in results)
        assert all(r.error_type == "RuntimeError" for r in results)

    def test_refuses_to_exceed_max_cost(self, tmp_path):
        output = tmp_path / "results.csv"
        # 10 prompt + 5 completion tokens per trial at the runner's
        # baked-in pricing costs a known, tiny amount per trial. Set
        # max_cost to allow exactly a couple of trials through.
        per_trial_cost = (10 / 1000 * 0.00015) + (5 / 1000 * 0.0006)
        # Budget check runs *before* each trial against cost already spent,
        # so total_cost lands on exactly 2x after trial 1 (0-indexed),
        # tripping the check before trial 2 starts. A non-multiple like
        # 2.5x would let a 3rd trial start before the overage is caught.
        max_cost = per_trial_cost * 2

        with pytest.raises(CostBudgetExceeded):
            run_campaign(
                agent_fn=_stub_agent_success,
                trials=50,
                faults=[],
                max_cost=max_cost,
                output_path=output,
            )

        # Partial results should still be on disk even though the
        # campaign was refused, not silently discarded.
        with output.open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2

    def test_never_starts_a_trial_once_budget_spent(self, tmp_path):
        output = tmp_path / "results.csv"
        with pytest.raises(CostBudgetExceeded):
            run_campaign(
                agent_fn=_stub_agent_success,
                trials=50,
                faults=[],
                max_cost=0.0,
                output_path=output,
            )
        with output.open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 0

    def test_fault_stack_makes_every_trial_fail_cleanly(self, tmp_path):
        # A real end-to-end proof: an agent hitting an always-firing fault
        # through ThaghrTransport should show up as clean error rows, not
        # crash the runner.
        def agent_hitting_faulted_client(client: httpx.Client) -> dict:
            resp = client.get("https://example.invalid/v1/chat")
            resp.raise_for_status()
            return {"content": "unreachable", "prompt_tokens": 0, "completion_tokens": 0}

        output = tmp_path / "results.csv"
        results = run_campaign(
            agent_fn=agent_hitting_faulted_client,
            trials=5,
            faults=[HTTPErrorFault(rate=1.0, seed=1, status_code=429)],
            max_cost=100.0,
            output_path=output,
        )
        assert len(results) == 5
        assert all(r.status == "error" for r in results)
        assert all(r.error_type == "HTTPStatusError" for r in results)
