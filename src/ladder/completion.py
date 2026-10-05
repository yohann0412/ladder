"""Completion marks: a file beside a working directory saying the step that wrote it finished.

A step removes the mark before its first write to the directory and writes it after its last,
so a directory left behind by a step killed part-way has no mark and is never trusted. The mark
lives outside the directory, where neither scoring nor git status sees it.
"""

from pathlib import Path

SUFFIX = ".complete"


def mark_file(directory: Path) -> Path:
    """Return the completion mark of a working directory: a file beside it."""
    return directory.with_name(directory.name + SUFFIX)


def unmark(directory: Path) -> None:
    """Remove a working directory's completion mark, if it has one."""
    mark_file(directory).unlink(missing_ok=True)


def unmark_all(parent: Path) -> None:
    """Remove the completion mark of every working directory directly inside a directory."""
    for mark in parent.glob(f"*{SUFFIX}"):
        mark.unlink()


def mark_complete(directory: Path) -> None:
    """Write a working directory's completion mark once its step has finished writing it."""
    mark_file(directory).touch()


def is_complete(directory: Path) -> bool:
    """Return whether a working directory exists and the step that wrote it finished."""
    return directory.is_dir() and mark_file(directory).is_file()
