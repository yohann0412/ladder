"""The `ladder resolve` commands: plan, prepare, audit and ingest resolver subagent runs."""

from typing import Annotated

import typer
from rich.console import Console

from ladder.cli_support import PairArgument, load_pair, refused
from ladder.context import layout_from
from ladder.jsonio import read_record
from ladder.plan import plan_pair, sample_double
from ladder.refusal import RefusedError
from ladder.resolver_view import render_plan, render_sample
from ladder.schemas import PairSet

app = typer.Typer(
    help="Plan, prepare, audit and ingest resolver subagent runs.", no_args_is_help=True
)


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
