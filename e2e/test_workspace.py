"""F2 acceptance: a workspace holds exactly base, a and b, and nothing that leads to the truth."""

from pathlib import Path

from conftest import Experiment, git, read_json, run


def _lines(repo: Path, rev: str, path: str) -> set[str]:
    proc = run(["git", "show", f"{rev}:{path}"], cwd=repo, check=False)
    return {line.strip() for line in proc.stdout.splitlines() if line.strip()}


def test_workspace_is_leak_proof(fx_resolved: Experiment, fixture_dir: Path) -> None:
    fx = fx_resolved
    repo = fixture_dir / "repo"
    scenario = next(
        s for s in read_json(fixture_dir / "manifest.json")["scenarios"] if s["pair_id"] == "fx08"
    )
    fx.ladder("workspace", "build", "fx08")
    record = fx.result("fx08", "workspace-replay")
    ws = Path(record["path"])

    assert record["source_b"] == git(repo, "rev-parse", "b-pre/8")
    assert record["source_a"] == scenario["a"]["head"]
    assert record["source_base"] == scenario["base"]

    assert len(git(ws, "rev-list", "--all").splitlines()) == 3
    assert git(ws, "for-each-ref", "--format=%(refname)").splitlines() == [
        "refs/heads/a",
        "refs/heads/b",
        "refs/heads/base",
    ]
    assert git(ws, "remote", "-v") == ""
    stored = git(ws, "cat-file", "--batch-all-objects", "--batch-check").splitlines()
    reachable = git(ws, "rev-list", "--objects", "--all").splitlines()
    assert len(stored) == len(reachable) == record["object_count"]
    for absent in ("objects/info/alternates", "FETCH_HEAD", "logs", "shallow"):
        assert not (ws / ".git" / absent).exists(), absent

    truth = scenario["resolved"]
    assert git(ws, "rev-parse", "b^{tree}") != git(repo, "rev-parse", f"{truth}^{{tree}}")
    leaked = _lines(repo, truth, "textkit/core.py") - (
        _lines(repo, scenario["base"], "textkit/core.py")
        | _lines(repo, scenario["a"]["head"], "textkit/core.py")
        | _lines(repo, "b-pre/8", "textkit/core.py")
    )
    assert leaked, "fx08's resolution must contain at least one line found on neither side"
    history = git(ws, "log", "--all", "-p")
    tree_text = run(["git", "grep", "-h", "-e", ".", "a", "b", "base"], cwd=ws).stdout
    for line in leaked:
        assert line not in history and line not in tree_text, line

    assert fx.ladder("workspace", "verify", "fx08").returncode == 0
    git(ws, "update-ref", "refs/heads/leak", git(ws, "rev-parse", "a"))
    rejected = fx.ladder("workspace", "verify", "fx08", check=False)
    assert rejected.returncode != 0 and "refs/heads/leak" in rejected.stdout + rejected.stderr

    unrecoverable = fx.ladder("workspace", "build", "fx10", check=False)
    assert unrecoverable.returncode != 0
    assert "unrecoverable" in unrecoverable.stdout + unrecoverable.stderr
    fx10 = next(
        s for s in read_json(fixture_dir / "manifest.json")["scenarios"] if s["pair_id"] == "fx10"
    )
    fx.ladder("workspace", "build", "fx10", "--heads", "final")
    assert fx.result("fx10", "workspace-final")["source_b"] == fx10["b"]["head"]

    fx.ladder("workspace", "build", "fx08")
    rebuilt = fx.result("fx08", "workspace-replay")
    assert [rebuilt[k] for k in ("base_commit", "a_commit", "b_commit")] == [
        record[k] for k in ("base_commit", "a_commit", "b_commit")
    ]
