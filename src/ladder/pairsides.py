"""The base, A and B sides of a conflicting pair: conflicted files' entities, each PR's changes."""

from dataclasses import dataclass
from pathlib import Path

from ladder.entitymap import FileEntities, file_entities
from ladder.gitio import run_git
from ladder.languages import language_for
from ladder.schemas import GitRungResult, Side
from ladder.syntax import parse
from ladder.testpick import added_or_modified_tests
from ladder.trees import changed_paths

SIDES: tuple[Side, ...] = ("a", "b")


@dataclass(frozen=True)
class PathSides:
    """One conflicted path: its language and the entities of its base, A and B versions."""

    path: str
    language: str | None
    base: FileEntities
    a: FileEntities
    b: FileEntities

    def side(self, side: Side) -> FileEntities:
        """Return the entities of one side's version."""
        return self.a if side == "a" else self.b


@dataclass(frozen=True)
class PairSides:
    """A conflicting pair's conflicted paths and what each PR changed relative to base."""

    paths: list[PathSides]
    changed: dict[Side, list[str]]
    tests: dict[Side, list[str]]

    def conflicted(self) -> list[str]:
        """Return the conflicted paths in the git rung's order."""
        return [item.path for item in self.paths]

    def touched_unconflicted(self, side: Side) -> bool:
        """Return whether a side changed any path outside the conflicted set."""
        conflicted = set(self.conflicted())
        return any(path not in conflicted for path in self.changed[side])


def blob_at(repo: Path, rev: str, path: str) -> bytes | None:
    """Return a file's bytes at a revision, or None when no blob is at that path."""
    proc = run_git(["cat-file", "blob", f"{rev}:{path}"], repo, ok_codes=(0, 128))
    return proc.stdout if proc.returncode == 0 else None


def load_sides(repo: Path, git_rung: GitRungResult) -> PairSides:
    """Read every conflicted path at base, A and B from a workspace repository."""
    paths = [_path_sides(repo, file.path) for file in git_rung.files]
    changed: dict[Side, list[str]] = {side: changed_paths(repo, "base", side) for side in SIDES}
    tests: dict[Side, list[str]] = {side: added_or_modified_tests(repo, side) for side in SIDES}
    return PairSides(paths, changed, tests)


def _path_sides(repo: Path, path: str) -> PathSides:
    language = language_for(path)

    def entities(rev: str) -> FileEntities:
        data = blob_at(repo, rev, path)
        return file_entities(None if data is None else parse(data, language))

    return PathSides(path, language, entities("base"), entities("a"), entities("b"))
