"""Validate what a resolver wrote and turn it into per-file records."""

import hashlib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from ladder.schemas import Record, ResolvedFile, ResolverFailure

RATIONALE = "rationale.json"
FILES = "files"


class RationaleEntry(Record):
    """The resolver's decision for one conflicted path."""

    path: str
    action: Literal["keep", "delete"]
    rationale: str


class Rationale(Record):
    """The rationale.json a resolver writes next to its files."""

    files: list[RationaleEntry]


@dataclass(frozen=True)
class Ingested:
    """A resolver's output: why it is unusable, if it is, and its files when it is valid."""

    failure: ResolverFailure | None
    problems: list[str]
    files: list[ResolvedFile]


def ingest_output(output_dir: Path, paths: Sequence[str]) -> Ingested:
    """Check rationale.json and files/ against the conflicted paths; record each path's outcome."""
    written = [p for p in output_dir.rglob("*") if not p.is_dir()] if output_dir.is_dir() else []
    if not written:
        return Ingested("no_output", [f"output: nothing was written to {output_dir}"], [])
    rationale, problems = _rationale(output_dir / RATIONALE)
    listed = rationale.files if rationale is not None else []
    entries = {entry.path: entry for entry in listed if entry.path in paths}
    if rationale is not None:
        problems += _entry_problems(rationale, paths)
    kept = {path for path, entry in entries.items() if entry.action == "keep"}
    files_dir = output_dir / FILES
    for path, entry in entries.items():
        if entry.action == "keep" and not (files_dir / path).is_file():
            problems.append(f"output: {path} is marked keep but {FILES}/{path} was not written")
        if entry.action == "delete" and (files_dir / path).exists():
            problems.append(f"output: {path} is marked delete but {FILES}/{path} exists")
    found = [p.relative_to(files_dir).as_posix() for p in written if p.is_relative_to(files_dir)]
    problems += [f"output: unexpected file {FILES}/{path}" for path in found if path not in kept]
    if problems:
        return Ingested("malformed_output", problems, [])
    return Ingested(None, [], [_resolved(files_dir, entries[path]) for path in paths])


def _rationale(path: Path) -> tuple[Rationale | None, list[str]]:
    if not path.is_file():
        return None, [f"output: {RATIONALE} was not written"]
    try:
        return Rationale.model_validate_json(path.read_bytes()), []
    except ValidationError as error:
        first = error.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        return None, [f"output: {RATIONALE} is invalid at {where or 'top'}: {first['msg']}"]


def _entry_problems(rationale: Rationale, paths: Sequence[str]) -> list[str]:
    counts = Counter(entry.path for entry in rationale.files)
    problems = [
        f"output: {path} has {n} entries in {RATIONALE}" for path, n in counts.items() if n > 1
    ]
    problems += [f"output: {path} is not a conflicted path" for path in counts if path not in paths]
    problems += [
        f"output: {path} has no entry in {RATIONALE}" for path in paths if path not in counts
    ]
    return problems


def _resolved(files_dir: Path, entry: RationaleEntry) -> ResolvedFile:
    digest = None
    if entry.action == "keep":
        digest = hashlib.sha256((files_dir / entry.path).read_bytes()).hexdigest()
    return ResolvedFile(
        path=entry.path, action=entry.action, sha256=digest, rationale=entry.rationale
    )
