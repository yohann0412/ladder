"""Copy exactly the objects of a few trees from a repository cache into another repository."""

from collections.abc import Sequence
from pathlib import Path

from ladder.cache import fetch_objects
from ladder.gitio import run_git

MISSING = b"?"


class MissingObjectsError(RuntimeError):
    """Objects of a tree are still missing from the cache after fetching them by id."""


def copy_trees(cache: Path, target: Path, trees: Sequence[str]) -> None:
    """Pack every object of these trees, and nothing else, from the cache into target.

    Blobs a blob-less cache lacks are fetched from origin by id before packing.
    """
    listed = _tree_objects(cache, trees)
    missing = [line[1:].decode("ascii") for line in listed if line.startswith(MISSING)]
    if missing:
        fetch_objects(cache, missing)
        listed = _tree_objects(cache, trees)
        still = [line[1:].decode("ascii") for line in listed if line.startswith(MISSING)]
        if still:
            raise MissingObjectsError(f"{len(still)} objects missing from {cache}: {still[0]}...")
    pack = run_git(["pack-objects", "--stdout", "-q"], cache, stdin=b"\n".join(listed) + b"\n")
    run_git(["index-pack", "--stdin"], target, stdin=pack.stdout)


def _tree_objects(cache: Path, trees: Sequence[str]) -> list[bytes]:
    args = ["rev-list", "--objects", "--no-object-names", "--no-walk", "--missing=print", *trees]
    return run_git(args, cache).stdout.split()
