"""F1b acceptance: resolve records heads, bases and merge commits, and rewinds contamination."""

from datetime import datetime
from pathlib import Path
from typing import Any

from conftest import REPO_ROOT, Experiment, git, read_json


def _epoch(stamp: str) -> int:
    return int(datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp())


def _commit_on_main_at(repo: Path, main: str, merged_at: str) -> str:
    log = git(repo, "log", "--first-parent", "--format=%H %ct", main).splitlines()
    hits = [sha for sha, ct in (line.split() for line in log) if int(ct) == _epoch(merged_at)]
    assert len(hits) == 1, (main, merged_at, hits)
    return hits[0]


def test_resolve_records_refs_and_rewinds_contaminated_head(
    fx: Experiment, fixture_dir: Path
) -> None:
    fx.ladder("pairs", "resolve", "--all")
    pairs: dict[str, Any] = {p["pair_id"]: p for p in read_json(fx.pairs)["pairs"]}
    manifest = {s["pair_id"]: s for s in read_json(fixture_dir / "manifest.json")["scenarios"]}
    expected = {
        s["pair_id"]: s for s in read_json(REPO_ROOT / "fixtures" / "expected.json")["scenarios"]
    }
    repo = fixture_dir / "repo"
    assert set(pairs) == set(manifest)

    for pair_id, scenario in manifest.items():
        refs, want = pairs[pair_id]["refs"], expected[pair_id]
        n = int(pair_id[2:])
        assert refs["status"] == want["resolve_status"], pair_id
        assert refs["default_branch"] == "main", pair_id
        assert refs["a"]["final_head"] == scenario["a"]["head"], pair_id
        assert refs["b"]["final_head"] == scenario["b"]["head"], pair_id
        assert refs["final_merge_base"] == scenario["base"], pair_id
        contaminated = [s for s in ("a", "b") if refs[s]["contaminated"]]
        assert contaminated == ([] if want["contaminated"] == "none" else [want["contaminated"]])
        for side in ("a", "b"):
            located = _commit_on_main_at(repo, f"main/{n}", scenario[side]["merged_at"])
            assert refs[side]["merge_commit"] == located, (pair_id, side)
        assert refs["truth_status"] == want["truth_status"], pair_id
        assert refs["truth_method"] == want["truth_method"], pair_id
        if want["truth_method"] in ("merge_parent", "absorption"):
            assert refs["truth_commit"] == scenario["resolved"], pair_id
        if want["resolve_status"] == "ok" and want["contaminated"] == "none":
            assert refs["a"]["replay_head"] == scenario["a"]["head"], pair_id
            assert refs["b"]["replay_head"] == scenario["b"]["head"], pair_id
            assert refs["replay_merge_base"] == scenario["base"], pair_id

    fx08 = pairs["fx08"]["refs"]
    assert fx08["b"]["replay_head"] == git(repo, "rev-parse", "b-pre/8")
    assert fx08["b"]["rewound_commits"] == 1
    assert fx08["a"]["replay_head"] == fx08["a"]["final_head"]
    assert fx08["a"]["merge_commit_method"] == "subject_time"
    assert fx08["replay_merge_base"] == manifest["fx08"]["base"]
    assert pairs["fx01"]["refs"]["b"]["merge_commit_method"] == "merge_parent"

    fx10 = pairs["fx10"]["refs"]
    assert fx10["b"]["replay_head"] is None
    assert fx10["replay_merge_base"] is None
