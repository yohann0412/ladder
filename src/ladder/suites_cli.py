"""The `ladder runnable` and `ladder claim-c` commands."""

from pathlib import Path
from typing import Annotated, NoReturn

import typer
from rich.console import Console

from ladder.claimc import ClaimCError, run_claim_c
from ladder.context import layout_from
from ladder.jsonio import read_optional, read_record, write_record
from ladder.layout import Layout
from ladder.runnable import classify_dir, classify_pair
from ladder.schemas import ClaimCRecord, GitRungResult, PairSet, Runnability
from ladder.suites_view import render_claim_c, render_claim_c_all, render_runnability


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


def claim_c(
    ctx: typer.Context,
    pair: Annotated[str | None, typer.Argument(help="Pair to run Claim C on.")] = None,
    all_pairs: Annotated[
        bool, typer.Option("--all", help="Every pair whose git rung merged cleanly.")
    ] = False,
) -> None:
    """Run the suite at A, at B and at their clean merge, and record whether they fail together."""
    layout = layout_from(ctx)
    console = Console()
    if pair is not None and not all_pairs:
        try:
            record = run_claim_c(layout, pair)
        except (ClaimCError, FileNotFoundError) as error:
            _fail(str(error))
        path = layout.result_file(pair, "claim-c")
        write_record(path, record)
        render_claim_c(console, record, path)
        return
    if pair is not None or not all_pairs:
        raise typer.BadParameter("pass a PAIR or --all")
    records: list[ClaimCRecord] = []
    skipped = 0
    for item in read_record(layout.pairs_file, PairSet).pairs:
        rung = read_optional(layout.result_file(item.pair_id, "rung-git"), GitRungResult)
        if rung is None or rung.status != "clean":
            skipped += 1
            continue
        try:
            records.append(_claim_c_with_runnability(layout, item.pair_id))
        except FileNotFoundError as error:
            console.print(f"skipped {item.pair_id}: {error}", style="yellow", markup=False)
            skipped += 1
    render_claim_c_all(console, records, skipped)


def _claim_c_with_runnability(layout: Layout, pair_id: str) -> ClaimCRecord:
    runnability_path = layout.result_file(pair_id, "runnability")
    if read_optional(runnability_path, Runnability) is None:
        write_record(runnability_path, classify_pair(layout, pair_id))
    record = run_claim_c(layout, pair_id)
    write_record(layout.result_file(pair_id, "claim-c"), record)
    return record


def _fail(message: str) -> NoReturn:
    Console(stderr=True).print(message, style="red", markup=False)
    raise typer.Exit(code=1)
