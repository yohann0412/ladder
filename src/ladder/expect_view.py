"""Render the comparison of a fixture run with the expected outcomes table."""

import json
from collections.abc import Sequence
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from ladder.expect import CellCheck, ExpectationReport, Value


def render_expectations(
    console: Console, checks: Sequence[CellCheck], report: ExpectationReport, path: Path
) -> None:
    """Print per pair its compared, mismatched and skipped cells, then every mismatch."""
    table = Table(title="Expected outcomes")
    for column in ("pair", "checked", "matched", "mismatched", "skipped (llm)"):
        table.add_column(column, justify="left" if column == "pair" else "right")
    for pair_id in dict.fromkeys(check.pair_id for check in checks):
        mine = [check for check in checks if check.pair_id == pair_id]
        compared = [check for check in mine if not check.skipped]
        wrong = sum(not check.matched for check in compared)
        table.add_row(
            pair_id,
            str(len(compared)),
            str(len(compared) - wrong),
            f"[red]{wrong}[/red]" if wrong else "0",
            str(len(mine) - len(compared)),
        )
    console.print(table)
    wrong_checks = [check for check in checks if not check.skipped and not check.matched]
    if wrong_checks:
        mismatches = Table(title="Mismatches")
        for column in ("pair", "cell", "basis", "expected", "observed"):
            mismatches.add_column(column, overflow="fold")
        for check in wrong_checks:
            mismatches.add_row(
                check.pair_id,
                check.cell,
                check.basis or "-",
                escape(_text(check.expected)),
                escape(_text(check.observed)),
            )
        console.print(mismatches)
    console.print(
        f"{report.checked} cells checked, {len(report.mismatches)} mismatches, "
        f"{report.skipped_llm} LLM cells skipped; wrote {escape(str(path))}"
    )


def _text(value: Value) -> str:
    return json.dumps(value)
