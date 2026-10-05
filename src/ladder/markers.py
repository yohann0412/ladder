"""Find git conflict markers in a file's bytes."""

REGION_OPENING = b"<<<<<<< "


def conflict_regions(data: bytes) -> int:
    """Return the number of conflict regions, counted by their `<<<<<<< ` opening lines."""
    return sum(1 for line in data.splitlines() if line.startswith(REGION_OPENING))
