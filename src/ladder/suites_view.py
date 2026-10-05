"""Render runnability and Claim C records as rich tables."""

from pathlib import Path

from rich.console import Console
from rich.table import Table

from ladder.schemas import ClaimCRecord, Runnability, TestOutcome


def render_runnability(console: Console, record: Runnability, path: Path) -> None:
    """Print how a suite was classified, every setup attempt and the base outcome."""
    table = Table(title=f"Runnability of {record.pair_id}", show_header=False)
    table.add_column("field", style="bold")
    table.add_column("value", overflow="fold")
    table.add_row("status", record.status)
    if record.reason is not None:
        table.add_row("reason", f"{record.reason}: {record.reason_detail}")
    table.add_row("language", record.language or "-")
    table.add_row("package manager", record.package_manager or "-")
    table.add_row("test runner", record.test_runner or "-")
    for modification in record.modifications:
        table.add_row("modification", modification)
    for number, attempt in enumerate(record.attempts, start=1):
        command = " ".join(attempt.command)
        table.add_row(
            f"attempt {number}", f"exit {attempt.exit_code} ({attempt.duration_s} s): {command}"
        )
    if record.base_outcome is not None:
        table.add_row("base suite", _outcome(record.base_outcome))
    table.add_row("test cap", f"{record.timeout_s} s")
    console.print(table)
    console.print(f"Wrote {path}", markup=False)


def render_claim_c(console: Console, record: ClaimCRecord, path: Path) -> None:
    """Print the suite outcome at A, at B and at the merge, and the verdict."""
    table = Table(title=f"Claim C for {record.pair_id}")
    table.add_column("tree")
    table.add_column("outcome", overflow="fold")
    for name, result in (("a", record.a), ("b", record.b), ("merge", record.merge)):
        table.add_row(name, _outcome(result))
    console.print(table)
    console.print(f"fails together: {_verdict(record)}", markup=False)
    console.print(f"Wrote {path}", markup=False)


def render_claim_c_all(console: Console, records: list[ClaimCRecord], skipped: int) -> None:
    """Print one row per pair that entered Claim C."""
    table = Table(title="Claim C")
    for column in ("pair", "a", "b", "merge", "fails together"):
        table.add_column(column)
    for record in records:
        table.add_row(
            record.pair_id, record.a.status, record.b.status, record.merge.status, _verdict(record)
        )
    console.print(table)
    console.print(f"{len(records)} pairs judged; {skipped} skipped (no clean merge or workspace)")


def _outcome(result: TestOutcome) -> str:
    counts = f"{result.passed} passed, {result.failed} failed, {result.errors} errors"
    retried = ", retried" if result.retried else ""
    return f"{result.status}{retried}: {counts}, {result.skipped} skipped in {result.duration_s} s"


def _verdict(record: ClaimCRecord) -> str:
    if record.fails_together is None:
        return f"excluded ({record.excluded_reason})"
    return "yes" if record.fails_together else "no"
