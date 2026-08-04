from __future__ import annotations

import csv
from pathlib import Path

import pytest

from thaghr.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]
HELLO_AGENT = REPO_ROOT / "examples" / "01-hello-agent"


@pytest.fixture
def stub_example(tmp_path):
    example_dir = tmp_path / "stub-agent"
    example_dir.mkdir()
    (example_dir / "agent.py").write_text(
        "def run(http_client=None):\n"
        "    return {'content': 'hi', 'prompt_tokens': 1, 'completion_tokens': 1}\n"
    )
    return example_dir


class TestCLIAgainstStub:
    def test_run_completes_and_writes_output(self, stub_example, tmp_path):
        output = tmp_path / "out.csv"
        exit_code = main(
            ["run", str(stub_example), "--trials", "20", "--output", str(output), "--max-cost", "10"]
        )
        assert exit_code == 0
        with output.open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 20

    def test_missing_agent_file_raises(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            main(["run", str(empty_dir), "--trials", "1"])

    def test_max_cost_zero_exits_nonzero(self, stub_example, tmp_path):
        output = tmp_path / "out.csv"
        exit_code = main(
            ["run", str(stub_example), "--trials", "5", "--output", str(output), "--max-cost", "0"]
        )
        assert exit_code == 1

    def test_run_prints_report_card(self, stub_example, tmp_path, capsys):
        output = tmp_path / "out.csv"
        exit_code = main(
            ["run", str(stub_example), "--trials", "10", "--output", str(output), "--max-cost", "10"]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "thaghr report card" in captured.out
        assert "pass^1: 100%" in captured.out

    def test_run_respects_k_flag(self, stub_example, tmp_path, capsys):
        output = tmp_path / "out.csv"
        exit_code = main(
            [
                "run",
                str(stub_example),
                "--trials",
                "10",
                "--k",
                "3",
                "--output",
                str(output),
                "--max-cost",
                "10",
            ]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "pass^3:" in captured.out

    def test_run_pretty_flag_uses_rich(self, stub_example, tmp_path, capsys):
        output = tmp_path / "out.csv"
        exit_code = main(
            [
                "run",
                str(stub_example),
                "--trials",
                "10",
                "--pretty",
                "--output",
                str(output),
                "--max-cost",
                "10",
            ]
        )
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "thaghr report card" in captured.out
        # rich's box-drawing differs from the plain renderer's; this just
        # confirms the pretty path actually ran instead of the plain one.
        assert "╭" in captured.out or "─" in captured.out


class TestCLICompare:
    def test_compare_writes_two_csvs_and_prints_report_card(self, stub_example, tmp_path, capsys):
        output_dir = tmp_path / "results"
        exit_code = main(
            [
                "compare",
                str(stub_example),
                "--baseline-trials",
                "20",
                "--fault-trials",
                "20",
                "--fault-rate",
                "0.3",
                "--seed",
                "1",
                "--max-cost",
                "10",
                "--output-dir",
                str(output_dir),
            ]
        )
        assert exit_code == 0
        assert (output_dir / "baseline.csv").exists()
        assert (output_dir / "faulted.csv").exists()
        captured = capsys.readouterr()
        assert "thaghr compare report card" in captured.out
        assert "baseline" in captured.out
        assert "faulted" in captured.out
        assert "robustness" in captured.out
        assert "survival" in captured.out

    def test_compare_baseline_is_actually_unfaulted(self, stub_example, tmp_path):
        # The stub agent always succeeds regardless of faults (it never
        # touches the injected httpx client), so this proves the baseline
        # campaign really does run with faults=[]: 100% either way here,
        # but robustness should come back defined and equal to 1.0 since
        # both conditions behave identically for this particular stub.
        import csv

        output_dir = tmp_path / "results"
        main(
            [
                "compare",
                str(stub_example),
                "--baseline-trials",
                "10",
                "--fault-trials",
                "10",
                "--max-cost",
                "10",
                "--output-dir",
                str(output_dir),
            ]
        )
        with (output_dir / "baseline.csv").open() as f:
            baseline_rows = list(csv.DictReader(f))
        assert all(row["fault_fired"] == "False" for row in baseline_rows)


class TestCLIAgainstRealExample:
    def test_hello_agent_completes_50_trials_fully_faulted(self, tmp_path):
        # fault-rate=1.0 means every call gets short-circuited with an
        # injected 429 before it ever reaches the real network. This proves
        # the CLI, the runner, and the real examples/01-hello-agent wire
        # together correctly, entirely offline, no OPENAI_API_KEY needed.
        output = tmp_path / "hello-agent-results.csv"
        exit_code = main(
            [
                "run",
                str(HELLO_AGENT),
                "--trials",
                "50",
                "--fault-rate",
                "1.0",
                "--seed",
                "1",
                "--max-cost",
                "10",
                "--output",
                str(output),
            ]
        )
        assert exit_code == 0
        with output.open() as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 50
        # Every trial failed, since every call was faulted, but the
        # campaign still completed cleanly and wrote all 50 rows.
        assert all(r["status"] == "error" for r in rows)
