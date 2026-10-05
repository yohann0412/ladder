"""Build the repository copy a resolver may read, at the conflicted merge state of its rung."""

import re
import shutil
from pathlib import Path

from ladder.gitio import run_git

DIFF3 = ("-c", "merge.conflictStyle=diff3")
DRIVER_ATTRIBUTE = re.compile(r"\bmerge=weave\b")
DRIVER_SECTION = "merge.weave"


def raw_snapshot(workspace: Path, target: Path) -> None:
    """Copy the canonical workspace and merge b into it with git's default strategy and diff3."""
    shutil.copytree(workspace, target, symlinks=True)
    run_git([*DIFF3, "merge", "--no-ff", "--no-edit", "b"], target, ok_codes=(0, 1))


def post_weave_snapshot(weave_dir: Path, target: Path) -> None:
    """Copy weave's merge state and remove its merge-driver configuration from the copy."""
    shutil.copytree(weave_dir, target, symlinks=True)
    attributes = target / ".git" / "info" / "attributes"
    if attributes.exists():
        lines = attributes.read_text(encoding="utf-8").splitlines()
        kept = [line for line in lines if not DRIVER_ATTRIBUTE.search(line)]
        if kept:
            attributes.write_text("\n".join(kept) + "\n", encoding="utf-8")
        else:
            attributes.unlink()
    keys = ["config", "--name-only", "--get-regexp", rf"^{re.escape(DRIVER_SECTION)}\."]
    if run_git(keys, target, ok_codes=(0, 1)).returncode == 0:
        run_git(["config", "--remove-section", DRIVER_SECTION], target)
