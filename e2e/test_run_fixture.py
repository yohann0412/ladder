"""Orchestration acceptance: `ladder run --all` reproduces the expected outcomes table."""

from conftest import REPO_ROOT, Experiment, read_json


def test_run_reproduces_expected_table(fx: Experiment) -> None:
    proc = fx.ladder(
        "run", "--all", "--no-llm", "--expect", str(REPO_ROOT / "fixtures" / "expected.json")
    )
    comparison = read_json(fx.results / "expectations.json")
    assert comparison["mismatches"] == [], comparison["mismatches"]
    assert comparison["checked"] >= 60
    assert comparison["skipped_llm"] > 0
    assert "fx08" in proc.stdout and "fx10" in proc.stdout

    again = fx.ladder(
        "run", "--all", "--no-llm", "--expect", str(REPO_ROOT / "fixtures" / "expected.json")
    )
    assert again.returncode == 0
    assert read_json(fx.results / "expectations.json")["mismatches"] == []
