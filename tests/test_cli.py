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
