"""F8 acceptance: the fixture's suite runs at base; a broken copy is classified build-fails."""

from pathlib import Path

from conftest import Experiment, run


def test_runnability_classifier(fx_resolved: Experiment, tmp_path: Path) -> None:
    fx = fx_resolved
    fx.ladder("workspace", "build", "fx01")
    fx.ladder("runnable", "fx01")
    record = fx.result("fx01", "runnability")
    assert record["status"] == "runnable"
    assert record["language"] == "python" and record["test_runner"] == "pytest"
    assert record["reason"] is None and record["modifications"] == []
    assert 10 <= record["test_count"] <= 15
    outcome = record["base_outcome"]
    assert outcome["status"] == "passed" and outcome["passed"] == record["test_count"]
    assert outcome["failed"] == 0 and record["timeout_s"] > 0

    workspace = Path(fx.result("fx01", "workspace-replay")["path"])
    broken = tmp_path / "broken"
    broken.mkdir()
    run(["sh", "-c", f"git archive base | tar -x -C {broken}"], cwd=workspace)
    (broken / "pyproject.toml").write_text(
        '[project]\nname = "textkit"\nversion = "0.0.0"\n'
        'dependencies = ["ladder-fixture-package-that-does-not-exist==9.9.9"]\n\n'
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\npythonpath = ["."]\n'
    )
    fx.ladder("runnable", "--dir", str(broken), "--id", "broken-copy")
    failed = fx.result("broken-copy", "runnability")
    assert failed["status"] == "unrunnable" and failed["reason"] == "build_fails"
    assert len(failed["attempts"]) == 2
    assert failed["base_outcome"] is None or failed["base_outcome"]["status"] != "passed"
