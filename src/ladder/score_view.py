"""Render a pair's rung scores as a rich table."""

from rich.console import Console
from rich.table import Table
from rich.text import Text

from ladder.schemas import RungScore, TestOutcome

VERDICT_STYLES = {"yes": "green", "no": "red", "-": "dim"}


def render_scores(console: Console, pair_id: str, scores: list[RungScore]) -> None:
    """Print one row per rung output: availability, mergeability, equivalence, intent, tests."""
    table = Table(title=f"Scores of {pair_id}")
    for column in ("rung", "available", "mergeable", "human-equivalent", "intent a", "intent b"):
        table.add_column(column)
    table.add_column("tests", overflow="fold")
    for score in scores:
        rung = score.rung if score.run == 1 else f"{score.rung} run {score.run}"
        available = _verdict(score.available)
        if score.unavailable_reason:
            available.append(f" ({score.unavailable_reason})", style="dim")
        table.add_row(
            rung,
            available,
            _verdict(score.mergeable if score.available else None),
            _verdict(score.human_equivalent),
            _verdict(score.intent_preserved_a),
            _verdict(score.intent_preserved_b),
            _tests(score),
        )
    console.print(table)
    for score in scores:
        for drop in score.intent_drops:
            console.print(
                f"{score.rung} run {score.run}: dropped {drop.loser.upper()}'s {drop.entity} "
                f"in {drop.path}: {drop.reason}",
                markup=False,
            )


def _verdict(value: bool | None) -> Text:
    word = "-" if value is None else ("yes" if value else "no")
    return Text(word, style=VERDICT_STYLES[word])


def _tests(score: RungScore) -> str:
    parts = [
        f"{name} {_status(result)}"
        for name, result in (("full", score.tests_full), ("a", score.tests_a), ("b", score.tests_b))
        if result is not None
    ]
    return ", ".join(parts) or "-"


def _status(result: TestOutcome) -> str:
    if result.status in ("passed", "failed", "flaky"):
        return f"{result.status} ({result.passed}/{result.passed + result.failed + result.errors})"
    return result.status
