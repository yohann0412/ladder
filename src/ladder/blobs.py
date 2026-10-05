"""Read single files of a commit, or of a working tree, without walking history."""

import os
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from ladder.cache import fetch_objects
from ladder.gitio import run_git
from ladder.treecopy import MISSING, MissingObjectsError

PATH_BATCH = 500
LITERAL = {"GIT_LITERAL_PATHSPECS": "1"}


@dataclass(frozen=True)
class TreeEntry:
    """One entry of a tree: its mode, its object type and its object id."""

    mode: str
    kind: str
    sha: str


def tree_entries(repo: Path, commit: str, paths: Sequence[str]) -> dict[str, TreeEntry]:
    """Return the tree entries of these paths at a commit; paths absent there are left out.

    Only trees are read, so a blob-less clone never fetches anything here.
    """
    wanted = set(paths)
    entries: dict[str, TreeEntry] = {}
    for batch in _batches(sorted(wanted)):
        args = ["ls-tree", "-z", "--full-tree", commit, "--", *batch]
        for record in filter(None, run_git(args, repo, env=LITERAL).stdout.split(b"\0")):
            meta, _, name = record.partition(b"\t")
            mode, kind, sha = meta.decode("ascii").split()
            path = os.fsdecode(name)
            if path in wanted:
                entries[path] = TreeEntry(mode, kind, sha)
    return entries


def ensure_files(cache: Path, commit: str, paths: Sequence[str]) -> None:
    """Fetch from origin the blobs of these paths at a commit that a blob-less clone lacks."""
    missing = _missing(cache, commit, paths)
    if not missing:
        return
    fetch_objects(cache, missing)
    still = _missing(cache, commit, paths)
    if still:
        raise MissingObjectsError(f"{len(still)} objects missing from {cache}: {still[0]}...")


def read_blob(repo: Path, sha: str) -> bytes:
    """Return the content of a blob."""
    return run_git(["cat-file", "blob", sha], repo).stdout


def file_at(repo: Path, commit: str, path: str) -> bytes | None:
    """Return a file's content at a commit, or None when the path is not a file there."""
    entry = tree_entries(repo, commit, [path]).get(path)
    if entry is None or entry.kind != "blob":
        return None
    return read_blob(repo, entry.sha)


def worktree_file(repo: Path, path: str) -> bytes | None:
    """Return a working-tree file's content (a symlink's target), or None when it is no file."""
    target = repo / path
    if target.is_symlink():
        return os.fsencode(target.readlink())
    if target.is_file():
        return target.read_bytes()
    return None


def _missing(repo: Path, commit: str, paths: Sequence[str]) -> list[str]:
    missing: list[str] = []
    for batch in _batches(list(paths)):
        args = ["rev-list", "--objects", "--no-object-names", "--no-walk", "--missing=print"]
        listed = run_git([*args, commit, "--", *batch], repo, env=LITERAL).stdout.split()
        missing += [line[1:].decode("ascii") for line in listed if line.startswith(MISSING)]
    return sorted(set(missing))


def _batches(paths: list[str]) -> Iterator[list[str]]:
    for start in range(0, len(paths), PATH_BATCH):
        yield paths[start : start + PATH_BATCH]
