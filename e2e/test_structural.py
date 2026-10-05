"""F4 acceptance: weave and mergiraf resolve scenario 1 and leave scenario 3 conflicted."""

from pathlib import Path

from conftest import Experiment


def test_structural_rungs(fx_resolved: Experiment) -> None:
    fx = fx_resolved
    for pair_id in ("fx01", "fx03"):
        fx.ladder("workspace", "build", pair_id)
        fx.ladder("rung", "git", pair_id)

    outputs: list[Path] = []
    for tool, version in (("weave", "0.5.2"), ("mergiraf", "0.20.0")):
        fx.ladder("rung", "structural", "fx01", "--tool", tool)
        one = fx.result("fx01", f"rung-{tool}")
        assert one["tool"] == tool and one["tool_version"] == version
        assert one["status"] == "resolved" and one["remaining_conflicted"] == []
        assert [f["path"] for f in one["files"]] == ["textkit/core.py"]
        for f in one["files"]:
            assert f["present"] and not f["has_markers"] and f["parses"] is True
            assert f["language"] == "python"
        merged = Path(one["output_dir"]) / "textkit" / "core.py"
        assert "<<<<<<<" not in merged.read_text()
        outputs.append(Path(one["output_dir"]))

        fx.ladder("rung", "structural", "fx03", "--tool", tool)
        three = fx.result("fx03", f"rung-{tool}")
        assert three["status"] == "conflicted"
        assert three["remaining_conflicted"] == ["textkit/core.py"]
        assert [f["has_markers"] for f in three["files"]] == [True]

    assert outputs[0] != outputs[1]
