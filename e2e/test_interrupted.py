"""Robustness: a working copy left by an interrupted rebuild is rebuilt, never trusted."""

from pathlib import Path

from conftest import Experiment

RUN = ("run", "fx01", "--no-llm", "--stop-before-truth", "--skip-claim-c")


def test_interrupted_rebuild_is_rebuilt(fx_resolved: Experiment) -> None:
    fx = fx_resolved
    fx.ladder(*RUN)
    workspace = Path(fx.result("fx01", "workspace-replay")["path"])
    git_copy = fx.work / "rungs" / "fx01" / "git-replay"
    structural = [
        Path(fx.result("fx01", f"rung-{tool}")["output_dir"]) for tool in ("weave", "mergiraf")
    ]
    merged = [(directory / "textkit" / "core.py").read_text() for directory in structural]

    fx.ladder(*RUN, "--prune")
    for directory in (workspace, git_copy, *structural):
        assert not directory.exists(), directory
        # A rebuild killed part-way leaves its directory behind with only part of the tree.
        (directory / "textkit").mkdir(parents=True)

    fx.ladder(*RUN)
    for directory in (workspace, git_copy, *structural):
        assert (directory / "textkit" / "core.py").is_file(), directory
        assert (directory / ".git").is_dir(), directory
    assert [(directory / "textkit" / "core.py").read_text() for directory in structural] == merged
