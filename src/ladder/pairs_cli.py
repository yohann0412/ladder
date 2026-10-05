"""The `ladder pairs` commands: fetch the pair sources and load pairs into pairs.json."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ladder.context import layout_from
from ladder.pairs_view import render_fetch
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
