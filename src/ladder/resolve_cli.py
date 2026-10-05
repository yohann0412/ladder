"""The `ladder resolve` commands: plan, prepare, audit and ingest resolver subagent runs."""

from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape

from ladder.cli_support import PairArgument, load_pair, refused
from ladder.context import layout_from
from ladder.jsonio import read_record
from ladder.plan import plan_pair, sample_double
from ladder.prepare import prepare_run
from ladder.refusal import RefusedError
from ladder.resolver_records import pending_tasks
from ladder.resolver_view import render_pending, render_plan, render_sample, render_task
from ladder.schemas import LlmRung, PairSet

app = typer.Typer(
    help="Plan, prepare, audit and ingest resolver subagent runs.", no_args_is_help=True
)

RungOption = Annotated[LlmRung, typer.Option(help="The LLM rung the run belongs to.")]
RunOption = Annotated[int, typer.Option(min=1, help="The run number, from 1.")]


@app.command()
def plan(
    ctx: typer.Context,
    pair_id: PairArgument,
    exclude_llm: Annotated[
        str | None,
        typer.Option("--exclude-llm", metavar="REASON", help="Plan no LLM run, for this reason."),
    ] = None,
) -> None:
    """Fix the resolver runs a pair gets, before any truth exists."""
    layout = layout_from(ctx)
    _, pair = load_pair(layout, pair_id)
    try:
        resolver_plan = plan_pair(layout, pair, exclude_llm)
    except RefusedError as error:
        raise refused(error) from error
    render_plan(Console(soft_wrap=True), resolver_plan)


@app.command("sample-double")
def sample_double_command(
    ctx: typer.Context,
    n: Annotated[int, typer.Option("--n", min=1, help="How many pairs to draw.")] = 30,
    seed: Annotated[int, typer.Option(help="Seed of the draw.")] = 42,
) -> None:
    """Add a second llm-raw run to a seeded sample of the pairs planned for llm-raw run 1."""
    layout = layout_from(ctx)
    try:
        drawn, pool = sample_double(layout, read_record(layout.pairs_file, PairSet), n, seed)
    except RefusedError as error:
        raise refused(error) from error
    render_sample(Console(soft_wrap=True), drawn, pool, seed)


@app.command()
def prepare(ctx: typer.Context, pair_id: PairArgument, rung: RungOption, run: RunOption) -> None:
    """Prepare one resolver run's task directory and print the line that spawns its subagent."""
    layout = layout_from(ctx)
    pair_set, pair = load_pair(layout, pair_id)
    try:
        task = prepare_run(layout, pair_set, pair, rung, run)
    except RefusedError as error:
        raise refused(error) from error
    render_task(Console(stderr=True, soft_wrap=True, highlight=False), task)
    if task.status == "pending":
        Console(soft_wrap=True, highlight=False).print(escape(task.spawn_line))


@app.command()
def pending(ctx: typer.Context) -> None:
    """List every prepared task still waiting for its subagent run, with its spawn line."""
    tasks = pending_tasks(layout_from(ctx))
    if not tasks:
        Console(stderr=True).print("No pending resolver tasks.")
    render_pending(Console(soft_wrap=True, highlight=False), tasks)
