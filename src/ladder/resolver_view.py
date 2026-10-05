"""Render resolver plans, tasks and run records."""

from collections.abc import Sequence

from rich.console import Console
from rich.markup import escape

from ladder.resolver_records import run_label
from ladder.schemas import ResolverPlan


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
