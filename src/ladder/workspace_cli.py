"""The `ladder workspace` commands: build and verify a pair's leak-proof workspace."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ladder.context import layout_from
from ladder.jsonio import read_optional, read_record
from ladder.pairselect import UnknownPairError, find_pair
from ladder.schemas import HeadsKind, PairSet, WorkspaceRecord
from ladder.workspace import Synthetic, UnusablePairError, build_recorded
from ladder.workspace_view import render_checks
from ladder.wsverify import verify_workspace

app = typer.Typer(help="Build and verify leak-proof workspaces.", no_args_is_help=True)

PairArgument = Annotated[str, typer.Argument(help="Pair id.")]
HeadsOption = Annotated[HeadsKind, typer.Option(help="Which heads the workspace holds.")]


@app.command()
def build(ctx: typer.Context, pair_id: PairArgument, heads: HeadsOption = "replay") -> None:
    """Rebuild a pair's workspace from scratch as three synthetic commits, then verify it."""
    layout = layout_from(ctx)
    try:
        pair = find_pair(read_record(layout.pairs_file, PairSet), pair_id)
    except UnknownPairError as error:
        raise typer.BadParameter(str(error)) from error
    try:
        built = build_recorded(layout, pair, heads)
    except UnusablePairError as error:
        Console(stderr=True).print(str(error), soft_wrap=True, highlight=False)
        raise typer.Exit(2) from error
    render_checks(Console(), built.path, built.verification)
    if built.record is None:
        raise typer.Exit(1)


@app.command()
def verify(ctx: typer.Context, pair_id: PairArgument, heads: HeadsOption = "replay") -> None:
    """Re-run the leak checks on a built workspace; exit non-zero if any fails."""
    record_file = layout_from(ctx).result_file(pair_id, f"workspace-{heads}")
    record = read_optional(record_file, WorkspaceRecord)
    if record is None:
        Console(stderr=True).print(
            f"no {heads} workspace record for {pair_id}; run `ladder workspace build`",
            soft_wrap=True,
        )
        raise typer.Exit(2)
    synthetic = Synthetic(base=record.base_commit, a=record.a_commit, b=record.b_commit)
    path = Path(record.path)
    verification = verify_workspace(path, synthetic.refs())
    render_checks(Console(), path, verification)
    if not verification.passed:
        raise typer.Exit(1)
