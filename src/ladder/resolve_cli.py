"""The `ladder resolve` commands: plan, prepare, audit and ingest resolver subagent runs."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape

from ladder.canary import check_canaries, plant_canary
from ladder.cli_support import PairArgument, load_pair, refused
from ladder.context import layout_from
from ladder.finalize import finalize_run
from ladder.jsonio import read_record
from ladder.plan import plan_pair, sample_double
from ladder.prepare import prepare_run
from ladder.refusal import RefusedError
from ladder.resolver_collect import match_transcripts
from ladder.resolver_records import pending_tasks
from ladder.resolver_view import (
    render_canaries,
    render_collected,
    render_pending,
    render_plan,
    render_run,
    render_sample,
    render_task,
)
from ladder.schemas import LlmRung, PairSet

app = typer.Typer(
    help="Plan, prepare, audit and ingest resolver subagent runs.", no_args_is_help=True
)
canary_app = typer.Typer(
    help="Plant markers in repository caches and search resolver outputs for them.",
    no_args_is_help=True,
)
app.add_typer(canary_app, name="canary")

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


@app.command()
def finalize(
    ctx: typer.Context,
    pair_id: PairArgument,
    rung: RungOption,
    run: RunOption,
    *,
    transcript: Annotated[
        Path | None, typer.Option(dir_okay=False, help="The subagent's transcript, JSON lines.")
    ] = None,
    no_transcript: Annotated[
        bool, typer.Option("--no-transcript", help="No transcript exists: audit impossible.")
    ] = False,
) -> None:
    """Audit a finished resolver run and record it with its output; failures are recorded too."""
    if (transcript is not None) == no_transcript:
        raise typer.BadParameter("pass exactly one of --transcript and --no-transcript")
    layout = layout_from(ctx)
    try:
        record = finalize_run(layout, pair_id, rung, run, transcript)
    except RefusedError as error:
        raise refused(error) from error
    render_run(Console(soft_wrap=True, highlight=False), record)


@app.command()
def collect(
    ctx: typer.Context,
    transcripts: Annotated[
        Path,
        typer.Option(
            exists=True, file_okay=False, help="Directory searched recursively for *.jsonl files."
        ),
    ],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Report the matches without finalizing.")
    ] = False,
) -> None:
    """Finalize every pending task whose spawn line opens exactly one transcript under a directory.

    Tasks with no matching transcript stay pending; tasks with more than one are not finalized
    and make the command exit 1.
    """
    layout = layout_from(ctx)
    matches = match_transcripts(layout, transcripts)
    console = Console(soft_wrap=True, highlight=False)
    finalized = 0
    for task, path in matches.matched:
        if dry_run:
            continue
        try:
            record = finalize_run(layout, task.pair_id, task.rung, task.run, path)
        except RefusedError as error:
            console.print(f"{task.pair_id}: not finalized: {escape(str(error))}")
            continue
        render_run(console, record)
        finalized += 1
    render_collected(console, matches, finalized, dry_run=dry_run)
    if matches.conflicts:
        raise typer.Exit(1)


@canary_app.command("plant")
def canary_plant(
    ctx: typer.Context,
    pair_id: PairArgument,
    marker: Annotated[str, typer.Option(help="The marker text to plant.")],
) -> None:
    """Commit a marker on top of the default branch of a pair's repository cache."""
    layout = layout_from(ctx)
    _, pair = load_pair(layout, pair_id)
    try:
        planted = plant_canary(layout, pair, marker)
    except RefusedError as error:
        raise refused(error) from error
    Console(soft_wrap=True, highlight=False).print(
        f"Planted {escape(repr(marker))} for {pair_id} at {planted.commit} (refs/ladder/canary)"
    )


@canary_app.command("check")
def canary_check(ctx: typer.Context) -> None:
    """Search every resolver output for every planted marker; exit 1 on any hit."""
    planted, hits = check_canaries(layout_from(ctx))
    render_canaries(Console(soft_wrap=True, highlight=False), planted, hits)
    if hits:
        raise typer.Exit(1)
