"""Fresh rung copies of a workspace, the rung merge command, and the paths it leaves unmerged."""

import shutil
import subprocess
from pathlib import Path

from ladder.completion import is_complete, unmark
from ladder.gitio import run_git

MERGE_B = ("-c", "merge.conflictStyle=diff3", "merge", "--no-ff", "--no-edit", "b")


class RungError(RuntimeError):
    """A rung cannot run because an input it needs is missing."""


def fresh_copy(workspace: Path, dest: Path) -> Path:
    """Unmark dest and replace it with a copy of a complete workspace, symlinks preserved."""
    if not is_complete(workspace):
        raise RungError(f"workspace directory {workspace} does not exist or is incomplete")
    unmark(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(workspace, dest, symlinks=True)
    return dest


def merge_b(repo: Path, *, timeout: float | None = None) -> subprocess.CompletedProcess[bytes]:
    """Merge branch b into the checked-out branch with diff3 markers; exit 1 means conflicts."""
    return run_git(MERGE_B, repo, ok_codes=(0, 1), timeout=timeout)


def unmerged_paths(repo: Path) -> list[str]:
    """Return the sorted paths that still have unmerged index entries."""
    out = run_git(["diff", "-z", "--name-only", "--diff-filter=U"], repo).stdout
    return sorted({path.decode("utf-8", "replace") for path in out.split(b"\0") if path})
