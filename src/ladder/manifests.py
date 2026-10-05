"""Dependency manifests: which files decide an install, and their git blob ids in a tree."""

import fnmatch
import hashlib
import os
from pathlib import Path, PurePosixPath

from ladder.gitio import run_git

MANIFEST_NAMES = frozenset(
    {
        "package.json",
        "package-lock.json",
        "npm-shrinkwrap.json",
        "pnpm-lock.yaml",
        "pnpm-workspace.yaml",
        "yarn.lock",
        ".yarnrc.yml",
        ".yarnrc",
        ".npmrc",
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "uv.lock",
        "poetry.lock",
        "Pipfile",
        "Pipfile.lock",
        "go.mod",
        "go.sum",
        "go.work",
        "go.work.sum",
        "Cargo.toml",
        "Cargo.lock",
    }
)
REQUIREMENTS_PATTERN = "*requirements*.txt"
UNWALKED = frozenset({".git", "node_modules"})


def is_manifest(path: str) -> bool:
    """Return True when a path names a file that decides what gets installed."""
    name = PurePosixPath(path).name
    return name in MANIFEST_NAMES or fnmatch.fnmatch(name, REQUIREMENTS_PATTERN)


def rev_manifests(repo: Path, rev: str) -> dict[str, str]:
    """Return the blob id of every manifest in a revision of a repository."""
    listing = run_git(["ls-tree", "-r", "-z", rev], cwd=repo).stdout.decode("utf-8", "replace")
    manifests: dict[str, str] = {}
    for entry in filter(None, listing.split("\0")):
        meta, path = entry.split("\t", 1)
        _mode, kind, blob = meta.split(" ")
        if kind == "blob" and is_manifest(path):
            manifests[path] = blob
    return manifests


def tree_manifests(tree: Path) -> dict[str, str]:
    """Return the git blob id of every manifest in a directory, as git would hash it."""
    manifests: dict[str, str] = {}
    for root, dirnames, filenames in os.walk(tree):
        dirnames[:] = [name for name in dirnames if name not in UNWALKED]
        for name in filenames:
            path = Path(root) / name
            relative = path.relative_to(tree).as_posix()
            if is_manifest(relative):
                manifests[relative] = _blob_id(path)
    return manifests


def differing(left: dict[str, str], right: dict[str, str]) -> list[str]:
    """Return the manifest paths whose presence or content differs between two listings."""
    return sorted(path for path in left.keys() | right.keys() if left.get(path) != right.get(path))


def _blob_id(path: Path) -> str:
    data = str(path.readlink()).encode() if path.is_symlink() else path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()
