"""F3 acceptance: the git rung reproduces every scenario's expected merge outcome."""

from conftest import REPO_ROOT, Experiment, read_json


def test_git_rung_matches_expected_table(fx_resolved: Experiment) -> None:
    fx = fx_resolved
    in_cache = Experiment(pairs=fx.pairs, work=fx.work, results=fx.results.parent / "in-cache")
    scenarios = read_json(REPO_ROOT / "fixtures" / "expected.json")["scenarios"]
    checked = 0
    for scenario in scenarios:
        pair_id = scenario["pair_id"]
        for heads, key, record in (
            ("final", "git-final", "rung-git-final"),
            ("replay", "git", "rung-git"),
        ):
            want = scenario["rungs"][key]
            if want["status"] == "absent":
                continue
            fx.ladder("workspace", "build", pair_id, "--heads", heads)
            fx.ladder("rung", "git", pair_id, "--heads", heads)
            got = fx.result(pair_id, record)
            checked += 1
            assert got["heads"] == heads
            assert got["status"] == want["status"], (pair_id, key)
            paths = [f["path"] for f in got["files"]]
            if want["conflicted_paths"] is not None:
                assert paths == want["conflicted_paths"], (pair_id, key)
            if want["types"] is not None:
                assert got["types"] == want["types"], (pair_id, key)
            assert len(got["messages"]) == len(got["types"])
            if got["status"] == "conflicted":
                assert got["merged_tree"] is None
                for f in got["files"]:
                    assert f["category"] == "source"
                    assert (f["regions"] >= 1) == ("modify/delete" not in f["types"])
            else:
                assert got["merged_tree"] and paths == []
            in_cache.ladder("rung", "git", pair_id, "--heads", heads, "--in-cache")
            cached = in_cache.result(pair_id, record)
            assert {k: v for k, v in cached.items() if k != "detail"} == {
                k: v for k, v in got.items() if k != "detail"
            }, (pair_id, key)
    assert checked == 19
