"""Find git conflict markers in a file's bytes."""

REGION_OPENING = b"<<<<<<< "
MARKER_PREFIXES = (b"<<<<<<<", b"|||||||", b">>>>>>>")


def conflict_regions(data: bytes) -> int:
    """Return the number of conflict regions, counted by their `<<<<<<< ` opening lines."""
    return sum(1 for line in data.splitlines() if line.startswith(REGION_OPENING))


def has_markers(data: bytes) -> bool:
    """Return whether any line starts with a `<<<<<<<`, `|||||||` or `>>>>>>>` marker.

    A `=======` line is a marker only between such markers, which already count, so a bare
    `=======` line (a Markdown or reST underline) never counts on its own.
    """
    return any(line.startswith(MARKER_PREFIXES) for line in data.splitlines())
