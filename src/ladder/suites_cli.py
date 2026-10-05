"""The `ladder runnable` command."""

from pathlib import Path
from typing import Annotated, NoReturn

import typer
from rich.console import Console

from ladder.context import layout_from
from ladder.jsonio import write_record
from ladder.runnable import classify_dir, classify_pair
from ladder.suites_view import render_runnability


def runnable(
    ctx: typer.Context,
    pair: Annotated[
        str | None, typer.Argument(help="Pair whose workspace base is classified.")
    ] = None,
    directory: Annotated[
        Path | None,
        typer.Option("--dir", help="Plain directory to classify.", exists=True, file_okay=False),
    ] = None,
    record_id: Annotated[
        str | None, typer.Option("--id", help="Id to record a --dir classification under.")
    ] = None,
) -> None:
    """Classify whether a suite runs at a pair's merge base, or in a plain directory."""
    layout = layout_from(ctx)
    if pair is not None and directory is None and record_id is None:
        try:
            record = classify_pair(layout, pair)
        except FileNotFoundError as error:
            _fail(str(error))
    elif pair is None and directory is not None and record_id is not None:
        record = classify_dir(layout, directory.resolve(), record_id)
    else:
        raise typer.BadParameter("pass a PAIR, or --dir together with --id")
    path = layout.result_file(record.pair_id, "runnability")
    write_record(path, record)
    render_runnability(Console(), record, path)


def _fail(message: str) -> NoReturn:
    Console(stderr=True).print(message, style="red", markup=False)
    raise typer.Exit(code=1)
