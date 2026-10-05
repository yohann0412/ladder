"""Materialise source trees for test runs: workspace revisions, the clean merge, plain folders."""

import shutil
import tarfile
from collections.abc import Sequence
from pathlib import Path

from ladder.gitio import GitError, git_text, run_git
from ladder.jsonio import read_optional
from ladder.layout import Layout
from ladder.runtime import remove_tree
from ladder.schemas import HeadsKind, WorkspaceRecord

COPY_IGNORED = (".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".tox")
WORKSPACE_PREFERENCE: tuple[HeadsKind, ...] = ("replay", "final")


class MergeMismatch(RuntimeError):
    """The re-created merge differs from the one the git rung recorded."""


def find_workspace(layout: Layout, pair_id: str, heads: HeadsKind | None = None) -> WorkspaceRecord:
    """Return a pair's workspace record: the given heads, else replay, else final."""
    for kind in (heads,) if heads else WORKSPACE_PREFERENCE:
        record = read_optional(layout.result_file(pair_id, f"workspace-{kind}"), WorkspaceRecord)
        if record is not None:
            return record
    wanted = heads or " or ".join(WORKSPACE_PREFERENCE)
    raise FileNotFoundError(
        f"{pair_id} has no {wanted} workspace record; run ladder workspace build"
    )


def workspace_repo(record: WorkspaceRecord) -> Path:
    """Return the absolute path of a workspace's repository."""
    return Path(record.path).resolve()


def export_rev(repo: Path, rev: str, dest: Path) -> None:
    """Write the tree of a commit or tree object into a fresh directory with git archive."""
    remove_tree(dest)
    dest.mkdir(parents=True)
    archive = (dest.parent / f"{dest.name}.tar").resolve()
    run_git(["archive", "--format=tar", "-o", str(archive), rev], cwd=repo)
    with tarfile.open(archive) as tar:
        tar.extractall(dest, filter="tar")
    archive.unlink()


def export_merge(
    repo: Path, expected_tree: str, scratch: Path, dest: Path, holders: Sequence[Path] = ()
) -> None:
    """Export the clean merge tree from a repository holding it, else re-create and check it."""
    for holder in (repo, *holders):
        if holder.is_dir() and _has_tree(holder, expected_tree):
            export_rev(holder, expected_tree, dest)
            return
    remove_tree(scratch)
    scratch.parent.mkdir(parents=True, exist_ok=True)
    clone = ["clone", "--bare", "--quiet", str(repo.resolve()), str(scratch.resolve())]
    run_git(clone, cwd=scratch.parent)
    merge = run_git(
        ["merge-tree", "--write-tree", "--no-messages", "a", "b"], scratch, ok_codes=(0, 1)
    )
    tree = merge.stdout.decode().split("\n", 1)[0].strip()
    if merge.returncode != 0:
        raise MergeMismatch("b does not merge cleanly into a in the scratch copy")
    if tree != expected_tree:
        raise MergeMismatch(
            f"re-created merge tree {tree} differs from the recorded {expected_tree}"
        )
    export_rev(scratch, tree, dest)


def _has_tree(repo: Path, tree: str) -> bool:
    check = run_git(["cat-file", "-e", f"{tree}^{{tree}}"], repo, ok_codes=(0, 1, 128))
    return check.returncode == 0


def copy_dir(source: Path, dest: Path) -> None:
    """Copy a plain directory into a fresh one, leaving out VCS data and installed dependencies."""
    remove_tree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest, symlinks=True, ignore=shutil.ignore_patterns(*COPY_IGNORED))


def dir_commit(source: Path) -> str:
    """Return the HEAD commit of a directory that is a git checkout, or an empty string."""
    if not (source / ".git").exists():
        return ""
    try:
        return git_text(["rev-parse", "HEAD"], source)
    except GitError:
        return ""


def changed_paths(repo: Path, old: str, new: str) -> list[str]:
    """Return every path that differs between two revisions, renames split into both paths."""
    out = run_git(["diff", "--name-only", "--no-renames", "-z", old, new], repo).stdout
    return sorted(path for path in out.decode("utf-8", "replace").split("\0") if path)
