"""Render resolver plans, tasks and run records."""

from collections.abc import Sequence

from rich.console import Console
from rich.markup import escape

from ladder.canary import CanaryHit, PlantedCanary
from ladder.resolver_records import run_label
from ladder.schemas import ResolverPlan, ResolverRun, ResolverTask


def render_plan(console: Console, plan: ResolverPlan) -> None:
    """Print the runs a pair's plan holds, or why it holds none."""
    if plan.runs:
        runs = ", ".join(run_label(planned.rung, planned.run) for planned in plan.runs)
        console.print(f"{plan.pair_id}: {runs}")
    else:
        console.print(f"{plan.pair_id}: no resolver run ({escape(plan.excluded_reason or '')})")


def render_sample(console: Console, drawn: Sequence[str], pool: int, seed: int) -> None:
    """Print the pairs drawn for a second llm-raw run."""
    console.print(f"Drew {len(drawn)} of {pool} pairs with seed {seed} for llm-raw run 2:")
    for pair_id in drawn:
        console.print(f"  {pair_id}")


def render_task(console: Console, task: ResolverTask) -> None:
    """Print a prepared task's inputs and status."""
    label = f"{task.pair_id} {run_label(task.rung, task.run)}"
    flags = ", ".join(task.pr_text_flags) or "none"
    console.print(
        f"{label}: {task.status}; conflicted files: {len(task.files)}; "
        f"input bytes: {task.input_bytes}; PR text flags: {flags}"
    )
    if task.identical_to is not None:
        console.print(f"  input identical to {task.identical_to}; that run is reused")


def render_pending(console: Console, tasks: Sequence[ResolverTask]) -> None:
    """Print one line per pending task: pair, rung, run and spawn line."""
    for task in tasks:
        label = run_label(task.rung, task.run)
        console.print(escape(f"{task.pair_id} {label}: {task.spawn_line}"))


def render_run(console: Console, record: ResolverRun) -> None:
    """Print a run record's outcome and every violation."""
    label = f"{record.pair_id} {run_label(record.rung, record.run)}"
    outcome = "ok" if record.failure is None else f"failed ({record.failure})"
    console.print(
        f"{label}: {outcome}; tool calls: {record.tool_calls}; files: {len(record.files)}"
    )
    for violation in record.violations:
        console.print(f"  {escape(violation)}")


def render_canaries(
    console: Console, planted: Sequence[PlantedCanary], hits: Sequence[CanaryHit]
) -> None:
    """Print every canary hit, then how many markers were searched for."""
    for hit in hits:
        console.print(escape(f"HIT {hit.marker!r} (planted for {hit.pair_id}) in {hit.path}"))
    console.print(f"{len(hits)} hits for {len(planted)} planted markers")
