"""Match subagent transcripts to pending resolver tasks by the spawn line each one was given."""

from dataclasses import dataclass
from pathlib import Path

from ladder.layout import Layout
from ladder.resolver_records import pending_tasks
from ladder.schemas import ResolverTask
from ladder.transcript import TranscriptError, read_transcript


@dataclass(frozen=True)
class TranscriptMatches:
    """Every pending task sorted by how many transcripts carry its spawn line."""

    matched: list[tuple[ResolverTask, Path]]
    unmatched: list[ResolverTask]
    conflicts: list[tuple[ResolverTask, list[Path]]]
    unreadable: list[tuple[Path, str]]


def match_transcripts(layout: Layout, directory: Path) -> TranscriptMatches:
    """Find, for every pending task, the *.jsonl transcripts under a directory it was spawned with.

    A transcript belongs to a task when its first user message is the task's spawn line, the
    same rule the audit checks.
    """
    by_line: dict[str, list[Path]] = {}
    unreadable: list[tuple[Path, str]] = []
    for path in sorted(directory.rglob("*.jsonl")):
        try:
            first = read_transcript(path).first_user_text
        except TranscriptError as error:
            unreadable.append((path, str(error)))
            continue
        if first is not None:
            by_line.setdefault(first.strip(), []).append(path)
    matched: list[tuple[ResolverTask, Path]] = []
    unmatched: list[ResolverTask] = []
    conflicts: list[tuple[ResolverTask, list[Path]]] = []
    for task in pending_tasks(layout):
        found = by_line.get(task.spawn_line, [])
        if len(found) == 1:
            matched.append((task, found[0]))
        elif found:
            conflicts.append((task, found))
        else:
            unmatched.append(task)
    return TranscriptMatches(matched, unmatched, conflicts, unreadable)
