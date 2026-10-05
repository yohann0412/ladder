"""P1 acceptance: the fixture is deterministic and every scenario's designed git outcome holds."""

import sys
from pathlib import Path

from conftest import REPO_ROOT, build_fixture, git, read_json, run


def _refs(repo: Path) -> str:
    return git(repo, "for-each-ref", "--format=%(objectname) %(refname)")


def _merge_tree(repo: Path, left: str, right: str) -> tuple[str, list[str], list[str]]:
    proc = run(
        ["git", "merge-tree", "--write-tree", "--name-only", left, right], cwd=repo, check=False
    )
    assert proc.returncode in (0, 1), proc.stderr
    if proc.returncode == 0:
        return "clean", [], []
    head, _, messages = proc.stdout.partition("\n\n")
    paths = sorted(set(head.splitlines()[1:]))
    types = [
        line[len("CONFLICT (") :].split(")", 1)[0]
        for line in messages.splitlines()
        if line.startswith("CONFLICT (")
    ]
    return "conflicted", paths, types


def _pytest_at(repo: Path, rev: str, workdir: Path) -> tuple[int, str]:
    workdir.mkdir(parents=True)
    run(["sh", "-c", f"git archive {rev} | tar -x -C {workdir}"], cwd=repo)
    proc = run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=workdir, check=False
    )
    return proc.returncode, proc.stdout


def test_fixture_is_deterministic_and_scenarios_hold(tmp_path: Path) -> None:
    one = build_fixture(tmp_path / "one")
    two = build_fixture(tmp_path / "two")

    assert _refs(one / "repo") and _refs(one / "repo") == _refs(two / "repo")
    origins = sorted(p.name for p in (one / "origins").iterdir())
    assert origins == [f"fx{n:02d}.git" for n in range(1, 11)]
    for name in origins:
        assert _refs(one / "origins" / name) == _refs(two / "origins" / name)

    manifest = read_json(REPO_ROOT / "fixtures" / "pairs.json")
    expected = {
        s["pair_id"]: s for s in read_json(REPO_ROOT / "fixtures" / "expected.json")["scenarios"]
    }
    assert [s["pair_id"] for s in manifest["scenarios"]] == sorted(expected)

    repo = one / "repo"
    code, out = _pytest_at(repo, manifest["scenarios"][0]["base"], tmp_path / "base")
    assert code == 0, out
    passed = int(out.strip().splitlines()[-1].split()[0])
    assert 10 <= passed <= 15

    for scenario in manifest["scenarios"]:
        pair_id = scenario["pair_id"]
        a, b = scenario["a"], scenario["b"]
        assert git(repo, "rev-parse", a["branch"]) == a["head"], pair_id
        assert git(repo, "rev-parse", b["branch"]) == b["head"], pair_id
        origin = one / scenario["origin"]
        assert git(origin, "rev-parse", f"refs/pull/{a['number']}/head") == a["head"], pair_id
        assert git(origin, "rev-parse", f"refs/pull/{b['number']}/head") == b["head"], pair_id
        if scenario["resolved_branch"]:
            assert git(repo, "rev-parse", scenario["resolved_branch"]) == scenario["resolved"]

        want = expected[pair_id]["rungs"]["git-final"]
        status, paths, types = _merge_tree(repo, a["head"], b["head"])
        assert status == want["status"], pair_id
        if want["conflicted_paths"] is not None:
            assert paths == want["conflicted_paths"], pair_id
        if want["types"] is not None:
            assert types == want["types"], pair_id

        for side in (a, b):
            code, out = _pytest_at(repo, side["head"], tmp_path / pair_id / side["branch"])
            assert code == 0, f"{pair_id} {side['branch']} fails alone:\n{out}"

    fx06 = next(s for s in manifest["scenarios"] if s["pair_id"] == "fx06")
    merged = git(repo, "merge-tree", "--write-tree", fx06["a"]["head"], fx06["b"]["head"])
    code, _ = _pytest_at(repo, merged.splitlines()[0], tmp_path / "fx06-merged")
    assert code != 0, "fx06 must fail together"

    trap = one / "traps" / "fx07"
    assert (trap / "rationale.json").is_file()
    a7 = next(s for s in manifest["scenarios"] if s["pair_id"] == "fx07")["a"]["head"]
    assert (trap / "files" / "textkit" / "core.py").read_text() == git(
        repo, "show", f"{a7}:textkit/core.py"
    ) + "\n"
