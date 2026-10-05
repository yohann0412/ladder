"""Mergeability of a resolved state: no markers, no parse errors, no new duplicate definitions."""

from collections.abc import Sequence, Set

from ladder.entitymap import FileEntities
from ladder.pairsides import PathSides
from ladder.schemas import FileScore


def new_duplicates(sides: PathSides, resolved: FileEntities) -> list[str]:
    """Return the definition names that occur more often in the resolution than in base, A or B."""
    limit = sides.base.names | sides.a.names | sides.b.names
    return sorted(name for name, count in resolved.names.items() if count > limit[name])


def is_mergeable(files: Sequence[FileScore], unresolved: Set[str]) -> bool:
    """Return whether every conflicted path is resolved, marker-free, parseable, duplicate-free."""
    return not unresolved and all(
        not file.has_markers and file.parses is not False and not file.new_duplicates
        for file in files
    )
