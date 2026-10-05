"""F6 acceptance: truth equals resolved/<n> and is refused before the pair's resolver runs exist."""

from pathlib import Path

from conftest import Experiment, git, read_json


def test_truth_extraction_and_guard(fx_resolved: Experiment, fixture_dir: Path) -> None:
    fx = fx_resolved
    for pair_id in ("fx03", "fx07"):
        fx.ladder("workspace", "build", pair_id)
        fx.ladder("rung", "git", pair_id)
        fx.ladder("rung", "structural", pair_id, "--tool", "weave")
        fx.ladder("resolve", "plan", pair_id)
    assert fx.result("fx07", "resolver-plan")["runs"] == []
    assert fx.result("fx07", "resolver-plan")["excluded_reason"]

    refused = fx.ladder("truth", "extract", "fx03", check=False)
    assert refused.returncode != 0
    assert "resolver" in (refused.stdout + refused.stderr).lower()
    assert not (fx.work / "truth" / "fx03").exists()

    fx.ladder("truth", "extract", "fx07")
    truth = fx.result("fx07", "truth")
    scenario = next(
        s for s in read_json(fixture_dir / "manifest.json")["scenarios"] if s["pair_id"] == "fx07"
    )
    assert truth["status"] == "located" and truth["method"] == "merge_parent"
    assert truth["commit"] == scenario["resolved"]
    assert [(f["path"], f["present"]) for f in truth["files"]] == [("textkit/core.py", True)]
    stored = fx.work / "truth" / "fx07" / "files" / "textkit" / "core.py"
    assert (
        stored.read_text()
        == git(fixture_dir / "repo", "show", f"{scenario['resolved']}:textkit/core.py") + "\n"
    )
    assert truth["rewrite"] is False and truth["leak_head_equals_truth"] is False
    assert truth["touched_beyond_conflict"] == [] and truth["outside_region_edit"] == []

    assert fx.ladder("truth", "audit").returncode == 0
    (fx.work / "truth" / "fx03").mkdir(parents=True)
    flagged = fx.ladder("truth", "audit", check=False)
    assert flagged.returncode != 0 and "fx03" in flagged.stdout + flagged.stderr
