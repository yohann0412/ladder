"""Intent preservation: which entity changes of A or B a resolution lost. Never uses the truth.

For each entity key of a conflicted path, a side changed it when its version differs from
base's. A change made by one side only must survive as that side's version. A change both
sides made identically must survive. Different changes by both are lost when the resolution
keeps base's version, or keeps exactly one side's version while the other side's added lines
appear nowhere in the resolved files that A or B changed (containment).
"""

from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import cached_property

from ladder.entitymap import FileEntities, Key, display, normalized_lines
from ladder.pairsides import SIDES, PairSides, PathSides
from ladder.rungoutputs import ResolvedState
from ladder.schemas import IntentDrop, Side

Form = tuple[str, ...] | None
NAMES: dict[Side, str] = {"a": "A", "b": "B"}
OTHER: dict[Side, Side] = {"a": "b", "b": "a"}


@dataclass(frozen=True)
class Loss:
    """One side's change to one entity that the resolution lost, and why."""

    key: Key
    loser: Side
    reason: str


@dataclass
class ResolvedLines:
    """The normalized lines of the resolved files that A or B changed, read on first use."""

    state: ResolvedState
    paths: list[str]

    @cached_property
    def lines(self) -> frozenset[str]:
        """Return every normalized line of those files."""
        found: set[str] = set()
        for path in self.paths:
            data = self.state.read(path)
            if data is not None:
                found.update(normalized_lines(data))
        return frozenset(found)

    def contain(self, lines: Iterable[str]) -> bool:
        """Return whether every given line occurs among them."""
        return all(line in self.lines for line in lines)


def intent_drops(
    pair: PairSides, resolved: Mapping[str, FileEntities], state: ResolvedState
) -> list[IntentDrop]:
    """Return every change of A or B to a conflicted path's entities that the resolution lost."""
    lines = ResolvedLines(state, sorted({*pair.changed["a"], *pair.changed["b"]}))
    return [
        IntentDrop(
            path=sides.path,
            entity=display(loss.key),
            loser=loss.loser,
            reason=loss.reason,
            loser_touched_unconflicted_files=pair.touched_unconflicted(loss.loser),
        )
        for sides in pair.paths
        for loss in path_losses(sides, resolved[sides.path], lines.contain)
    ]


def path_losses(
    sides: PathSides, resolved: FileEntities, contain: Callable[[Iterable[str]], bool]
) -> list[Loss]:
    """Return one path's lost changes, leaving out an enclosing entity's loss to the same side."""
    keys = dict.fromkeys([*sides.base.versions, *sides.a.versions, *sides.b.versions])
    losses = [loss for key in keys for loss in _key_losses(key, sides, resolved, contain)]
    parents = [sides.base.parents, sides.a.parents, sides.b.parents, resolved.parents]
    covered = {
        (ancestor, loss.loser) for loss in losses for ancestor in _ancestors(loss.key, parents)
    }
    return [loss for loss in losses if (loss.key, loss.loser) not in covered]


def _form(entities: FileEntities, key: Key) -> Form:
    version = entities.versions.get(key)
    return None if version is None else version.form


def _key_losses(
    key: Key, sides: PathSides, resolved: FileEntities, contain: Callable[[Iterable[str]], bool]
) -> list[Loss]:
    base, result = _form(sides.base, key), _form(resolved, key)
    versions: dict[Side, Form] = {side: _form(sides.side(side), key) for side in SIDES}
    changed: list[Side] = [side for side in SIDES if versions[side] != base]
    if len(changed) == 1:
        side = changed[0]
        if result == versions[side]:
            return []
        name = NAMES[side]
        return [Loss(key, side, f"only {name} changed it; the resolution lacks {name}'s version")]
    if not changed:
        return []

    def contained(side: Side) -> bool:
        return contain(_added(sides, key, side))

    return _both_changed(key, base, versions, result, contained)


def _both_changed(
    key: Key,
    base: Form,
    versions: dict[Side, Form],
    result: Form,
    contained: Callable[[Side], bool],
) -> list[Loss]:
    if versions["a"] == versions["b"]:
        if result == versions["a"]:
            return []
        return _both(key, "both sides made the same change; the resolution lacks it")
    if result == base:
        return _both(key, "both sides changed it; the resolution keeps the base version")
    kept: Side | None = next((side for side in SIDES if result == versions[side]), None)
    if kept is None or contained(OTHER[kept]):
        return []
    loser = OTHER[kept]
    reason = (
        f"both sides changed it; the resolution keeps {NAMES[kept]}'s version and lacks "
        f"lines {NAMES[loser]} added to it"
    )
    return [Loss(key, loser, reason)]


def _both(key: Key, reason: str) -> list[Loss]:
    return [Loss(key, side, reason) for side in SIDES]


def _added(sides: PathSides, key: Key, side: Side) -> list[str]:
    new = sides.side(side).versions.get(key)
    old = sides.base.versions.get(key)
    added = Counter(new.lines if new else ()) - Counter(old.lines if old else ())
    return list(added.elements())


def _ancestors(key: Key, parents: list[dict[Key, Key]]) -> set[Key]:
    found: set[Key] = set()
    frontier = [key]
    while frontier:
        current = frontier.pop()
        for mapping in parents:
            parent = mapping.get(current)
            if parent is not None and parent not in found:
                found.add(parent)
                frontier.append(parent)
    return found
