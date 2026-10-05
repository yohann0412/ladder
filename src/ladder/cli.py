"""Command-line entry point."""

from pathlib import Path
from typing import Annotated

import typer

from ladder import pairs_cli, workspace_cli
from ladder.layout import Layout
from ladder.rung_cli import app as rung_app
from ladder.syntax_cli import app as syntax_app

app = typer.Typer(
    help="Measure how far up the git -> structural -> LLM ladder agent PR conflicts climb.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


@app.callback()
def main(
    ctx: typer.Context,
    pairs: Annotated[
        Path, typer.Option(envvar="LADDER_PAIRS", help="pairs.json to read and update.")
    ] = Path("data/pairs.json"),
    work: Annotated[
        Path, typer.Option(envvar="LADDER_WORK", help="Directory for clones, workspaces, outputs.")
    ] = Path("work"),
    results: Annotated[
        Path, typer.Option(envvar="LADDER_RESULTS", help="Directory for result records.")
    ] = Path("data/results"),
) -> None:
    """Store the experiment layout for the subcommands."""
    ctx.obj = Layout(pairs_file=pairs, work=work, results=results)


app.add_typer(pairs_cli.app, name="pairs")
app.add_typer(rung_app, name="rung")
app.add_typer(syntax_app)
app.add_typer(workspace_cli.app, name="workspace")
