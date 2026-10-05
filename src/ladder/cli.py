"""Command-line entry point."""

from pathlib import Path
from typing import Annotated

import typer

from ladder import pairs_cli, suites_cli
from ladder.layout import Layout

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
app.command("runnable")(suites_cli.runnable)
app.command("claim-c")(suites_cli.claim_c)
