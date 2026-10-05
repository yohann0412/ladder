"""The `ladder pairs` commands: fetch the pair sources and load pairs into pairs.json."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ladder.context import layout_from
from ladder.extracts import AIDEV_PRS, AidevPr, read_rows
from ladder.jsonio import write_record
from ladder.pairload import pairs_from_fixture, pairs_from_source
from ladder.pairs_view import render_fetch, render_fixture, render_summary
from ladder.pairsummary import summarise
from ladder.sources import fetch_sources

app = typer.Typer(
    help="Fetch the pair sources and load pairs into pairs.json.", no_args_is_help=True
)


@app.command("fetch-sources")
def fetch_sources_command(
    ctx: typer.Context,
    out: Annotated[
        Path, typer.Option(help="Directory to write the vendored source extracts into.")
    ] = Path("data/source"),
) -> None:
    """Download the replication package and AIDev tables and vendor the extracts load reads."""
    downloads = layout_from(ctx).work / "downloads"
    render_fetch(Console(), fetch_sources(out, downloads), out)


@app.command()
def load(
    ctx: typer.Context,
    source: Annotated[
        Path | None,
        typer.Option(
            help="Vendored paper sources (from fetch-sources).", exists=True, file_okay=False
        ),
    ] = None,
    fixture: Annotated[
        Path | None,
        typer.Option(
            help="Fixture build directory holding manifest.json.", exists=True, file_okay=False
        ),
    ] = None,
) -> None:
    """Write pairs.json, offline, from the vendored paper sources or from a fixture build."""
    target = layout_from(ctx).pairs_file
    console = Console()
    if source is not None and fixture is None:
        pair_set = pairs_from_source(source)
        write_record(target, pair_set)
        summary = summarise(pair_set, read_rows(source / AIDEV_PRS, AidevPr))
        render_summary(console, summary, target)
    elif fixture is not None and source is None:
        pair_set = pairs_from_fixture(fixture)
        write_record(target, pair_set)
        render_fixture(console, pair_set, target)
    else:
        raise typer.BadParameter("pass exactly one of --source and --fixture")
