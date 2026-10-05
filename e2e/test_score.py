"""F7 acceptance: the trap is tests-pass and intent-dropped (B); structural fx01 is equivalent."""

from conftest import Experiment


def test_scoring(fx_resolved: Experiment) -> None:
    fx = fx_resolved
    for pair_id in ("fx01", "fx07"):
        fx.ladder("workspace", "build", pair_id)
        fx.ladder("rung", "git", pair_id)
        fx.ladder("rung", "structural", pair_id, "--tool", "weave")
        fx.ladder("rung", "structural", pair_id, "--tool", "mergiraf")
        fx.ladder("runnable", pair_id)
    fx.ladder("rung", "trap", "fx07")
    fx.ladder("resolve", "plan", "fx07")
    fx.ladder("resolve", "plan", "fx01", "--exclude-llm", "acceptance test of non-LLM scoring")
    for pair_id in ("fx01", "fx07"):
        fx.ladder("truth", "extract", pair_id)
        fx.ladder("score", pair_id)

    trap = fx.result("fx07", "score-trap")
    assert trap["available"] and trap["mergeable"] is True
    assert trap["human_equivalent"] is False
    assert trap["tests_full"]["status"] == "passed"
    assert trap["intent_preserved_a"] is True and trap["intent_preserved_b"] is False
    assert [(d["loser"], d["path"], d["entity"]) for d in trap["intent_drops"]] == [
        ("b", "textkit/core.py", "validate")
    ]
    assert trap["tests_a"]["status"] == "passed"
    assert trap["tests_b"]["status"] == "not_run"

    git_rung = fx.result("fx07", "score-git")
    assert git_rung["mergeable"] is False
    assert git_rung["files"][0]["has_markers"] is True

    for tool in ("weave", "mergiraf"):
        score = fx.result("fx01", f"score-{tool}")
        assert score["available"] and score["mergeable"] is True, tool
        assert score["human_equivalent"] is True, tool
        assert score["intent_preserved_a"] is True and score["intent_preserved_b"] is True, tool
        assert score["intent_drops"] == [], tool
        assert score["tests_full"]["status"] == "passed", tool
        assert [f["mode"] for f in score["files"]] == ["ast"], tool
        assert score["files"][0]["similarity"] == 1.0, tool

    excluded = fx.result("fx01", "score-llm-raw")
    assert excluded["available"] is False
    assert "acceptance test" in excluded["unavailable_reason"]
