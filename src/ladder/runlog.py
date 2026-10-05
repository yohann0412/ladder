"""The run log of `ladder run`: every step that raised, with its pair, its error and the time."""

from datetime import UTC, datetime
from pathlib import Path

from ladder.jsonio import read_optional, write_record
from ladder.layout import Layout
from ladder.schemas import Record

RUN_LOG = "run-log.json"


class RunLogEntry(Record):
    """One step of one pair that raised during `ladder run`."""

    pair_id: str
    step: str
    error: str
    time: datetime


class RunLog(Record):
    """Every failed step of every `ladder run`, oldest first."""

    entries: list[RunLogEntry]


def run_log_path(layout: Layout) -> Path:
    """Return where the run log of an experiment is kept."""
    return layout.results / RUN_LOG


def append_failure(layout: Layout, pair_id: str, step: str, error: str) -> RunLogEntry:
    """Add one failed step to the run log and return its entry."""
    path = run_log_path(layout)
    log = read_optional(path, RunLog) or RunLog(entries=[])
    entry = RunLogEntry(pair_id=pair_id, step=step, error=error, time=datetime.now(UTC))
    write_record(path, RunLog(entries=[*log.entries, entry]))
    return entry
