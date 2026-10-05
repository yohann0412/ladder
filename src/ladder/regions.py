"""Find the context outside a marker file's conflict regions, and look for it in another text."""

import re
from collections.abc import Sequence

START = re.compile(r"^<{7}(?: |$)")
END = re.compile(r"^>{7}(?: |$)")


def text_lines(data: bytes) -> list[str]:
    """Return a file's lines with trailing whitespace, carriage returns included, stripped."""
    lines = data.decode("utf-8", "surrogateescape").split("\n")
    if lines[-1] == "":
        lines.pop()
    return [line.rstrip() for line in lines]


def has_regions(marked: bytes) -> bool:
    """Return whether a file holds at least one conflict region opened by `<<<<<<<`."""
    return any(START.match(line) for line in text_lines(marked))


def context_chunks(marked: bytes) -> list[list[str]]:
    """Return the runs of lines outside the `<<<<<<<`..`>>>>>>>` regions, skipping empty runs."""
    chunks: list[list[str]] = [[]]
    inside = False
    for line in text_lines(marked):
        if not inside and START.match(line):
            inside = True
            chunks.append([])
        elif inside and END.match(line):
            inside = False
        elif not inside:
            chunks[-1].append(line)
    return [chunk for chunk in chunks if chunk]


def keeps_context(marked: bytes, other: bytes | None) -> bool:
    """Return whether another text holds every context chunk, each contiguous, all in order.

    An absent text holds no chunk.
    """
    lines = text_lines(other) if other is not None else []
    position = 0
    for chunk in context_chunks(marked):
        found = _find(lines, chunk, position)
        if found is None:
            return False
        position = found + len(chunk)
    return True


def _find(lines: Sequence[str], chunk: Sequence[str], start: int) -> int | None:
    width = len(chunk)
    for index in range(start, len(lines) - width + 1):
        if lines[index] == chunk[0] and list(lines[index : index + width]) == list(chunk):
            return index
    return None
