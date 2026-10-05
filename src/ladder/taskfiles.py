"""Collect the base, a, b and conflicted versions of each file a resolver reads, within a cap."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ladder.blobs import file_at, worktree_file
from ladder.workspace import Synthetic

MAX_FILES = 20
MAX_VERSION_BYTES = 200_000
MAX_TOTAL_BYTES = 600_000


@dataclass(frozen=True)
class FileVersions:
    """One conflicted path and its versions by name; a version absent there is left out."""

    path: str
    versions: dict[str, bytes]


def collect_versions(
    repo: Path, commits: Synthetic, merged: Path, paths: Sequence[str]
) -> list[FileVersions]:
    """Read each path at repo's base, a and b commits and in the merged working tree."""
    collected: list[FileVersions] = []
    for path in paths:
        found = {
            "base": file_at(repo, commits.base, path),
            "a": file_at(repo, commits.a, path),
            "b": file_at(repo, commits.b, path),
            "conflicted": worktree_file(merged, path),
        }
        versions = {name: data for name, data in found.items() if data is not None}
        collected.append(FileVersions(path, versions))
    return collected


def input_bytes(files: Sequence[FileVersions]) -> int:
    """Return the size of every version of every file together."""
    return sum(len(data) for file in files for data in file.versions.values())


def cap_breaches(files: Sequence[FileVersions]) -> list[str]:
    """Return how these inputs exceed the resolver input cap; empty when they are within it."""
    breaches: list[str] = []
    if len(files) > MAX_FILES:
        breaches.append(f"input cap: {len(files)} conflicted files, more than {MAX_FILES}")
    breaches += [
        f"input cap: {file.path} version {name} has {len(data)} bytes, "
        f"more than {MAX_VERSION_BYTES}"
        for file in files
        for name, data in file.versions.items()
        if len(data) > MAX_VERSION_BYTES
    ]
    total = input_bytes(files)
    if total > MAX_TOTAL_BYTES:
        breaches.append(f"input cap: {total} bytes in all versions, more than {MAX_TOTAL_BYTES}")
    return breaches


def write_versions(task_dir: Path, files: Sequence[FileVersions]) -> None:
    """Write each file's versions to <task>/files/<k>/<name>, numbering files from 1."""
    for k, file in enumerate(files, start=1):
        directory = task_dir / "files" / str(k)
        directory.mkdir(parents=True)
        for name, data in file.versions.items():
            (directory / name).write_bytes(data)
