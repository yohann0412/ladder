"""Describe what each step of `ladder run` recorded, and render the run's outcome."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from ladder.resolver_records import run_label
from ladder.schemas import (
    ClaimCRecord,
    GitRungResult,
    ResolverPlan,
    ResolverTask,
    RungScore,
    Runnability,
    StructuralResult,
    TruthRecord,
)

PairState = Literal["done", "stopped", "pending", "waiting", "failed"]
STATE_STYLES: dict[PairState, str] = {
    "done": "green",
    "stopped": "cyan",
    "pending": "yellow",
    "waiting": "yellow",
    "failed": "red",
}


@dataclass(frozen=True)
class PairOutcome:
    """How far one pair got in this run, and why it stopped there."""

    pair_id: str
    state: PairState
    detail: str


def git_summary(result: GitRungResult) -> str:
    """Return a git rung record in one phrase."""
    if result.status == "conflicted":
        types = ", ".join(f"{kind} {count}" for kind, count in Counter(result.types).items())
        return f"conflicted, {len(result.files)} files ({types})"
    if result.status == "error":
        return f"error: {result.detail}"
    return "clean"


def structural_summary(result: StructuralResult) -> str:
    """Return a structural rung record in one phrase."""
    if result.status == "error":
        return f"error: {result.detail}"
    left = len(result.remaining_conflicted)
    return f"{result.status}, {left} of {len(result.files)} files still conflicted"


def plan_summary(plan: ResolverPlan) -> str:
    """Return the runs a resolver plan holds, or why it holds none."""
    if not plan.runs:
        return f"no resolver run ({plan.excluded_reason})"
    return ", ".join(run_label(planned.rung, planned.run) for planned in plan.runs)


def task_summary(task: ResolverTask) -> str:
    """Return a prepared resolver task in one phrase."""
    return f"{run_label(task.rung, task.run)} prepared: {task.status}"


def truth_summary(record: TruthRecord) -> str:
    """Return a truth record in one phrase."""
    if record.status != "located":
        return record.status
    rewrite = "yes" if record.rewrite else "no"
    return f"located by {record.method}, rewrite {rewrite}"


def runnability_summary(record: Runnability) -> str:
    """Return a runnability record in one phrase."""
    if record.reason is None:
        return record.status
    return f"{record.status} ({record.reason}: {record.reason_detail})"


def score_summary(scores: Sequence[RungScore]) -> str:
    """Return which of a pair's scored outputs are mergeable and human-equivalent."""
    mergeable = [_name(score) for score in scores if score.mergeable]
    equivalent = [_name(score) for score in scores if score.human_equivalent]
    return (
        f"scored {len(scores)} outputs; mergeable: {', '.join(mergeable) or '-'}; "
        f"human-equivalent: {', '.join(equivalent) or '-'}"
    )


def claim_c_summary(record: ClaimCRecord) -> str:
    """Return a Claim C record's verdict in one phrase."""
    if record.fails_together is None:
        return f"excluded ({record.excluded_reason})"
    return "fails together" if record.fails_together else "passes together"


def render_outcomes(console: Console, outcomes: Sequence[PairOutcome]) -> None:
    """Print one row per pair with how far it got, then the count of each state."""
    table = Table(title="ladder run")
    table.add_column("pair")
    table.add_column("state")
    table.add_column("detail", overflow="fold")
    for outcome in outcomes:
        style = STATE_STYLES[outcome.state]
        table.add_row(
            outcome.pair_id, f"[{style}]{outcome.state}[/{style}]", escape(outcome.detail)
        )
    console.print(table)
    counts = Counter(outcome.state for outcome in outcomes)
    console.print(", ".join(f"{state} {counts[state]}" for state in STATE_STYLES))


def render_spawn_lines(console: Console, tasks: Sequence[ResolverTask]) -> None:
    """Print every pending task's spawn line, one per line, then how many there are."""
    for task in tasks:
        console.print(task.spawn_line, markup=False, highlight=False, soft_wrap=True)
    console.print(f"{len(tasks)} resolver runs pending: awaiting resolver runs")


def _name(score: RungScore) -> str:
    return score.rung if score.run == 1 else f"{score.rung} run {score.run}"
