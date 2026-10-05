"""The `ladder run` command: every step of the ladder for the selected pairs, in-process."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from ladder.collect import collect
from ladder.context import layout_from
from ladder.expect import (
    EXPECTATIONS_FILE,
    check_expectations,
    expectation_report,
)
from ladder.expect_view import render_expectations
from ladder.jsonio import read_record, write_record
from ladder.layout import Layout
from ladder.orchestrate import RunOptions, RunResult, run_pairs
from ladder.pairselect import UnknownPairError, select_pairs
from ladder.run_view import render_outcomes, render_spawn_lines
from ladder.schemas import FixtureExpectations, Pair, PairOrigin, PairSet

AWAITING_RESOLVERS = 3


def run(
    ctx: typer.Context,
    pair_ids: Annotated[
        list[str] | None, typer.Argument(metavar="[PAIR]...", help="Pair ids to run.")
    ] = None,
    *,
    all_pairs: Annotated[bool, typer.Option("--all", help="Run every pair.")] = False,
    origin: Annotated[
        PairOrigin | None, typer.Option(help="Run every pair of this origin.")
    ] = None,
    no_llm: Annotated[
        bool, typer.Option("--no-llm", help="Plan no resolver run for pairs not yet planned.")
    ] = False,
    expect: Annotated[
        Path | None,
        typer.Option(
            exists=True, dir_okay=False, help="Expected outcomes table to compare the records with."
        ),
    ] = None,
    prune: Annotated[
        bool,
        typer.Option("--prune", help="Delete each pair's working copies after its last step."),
    ] = False,
    skip_claim_c: Annotated[
        bool, typer.Option("--skip-claim-c", help="Run no Claim C on clean pairs.")
    ] = False,
    min_free_gb: Annotated[
        float, typer.Option(min=0, help="Wait before each pair while less is free, in GiB.")
    ] = 5.0,
    jobs: Annotated[
        int, typer.Option(min=1, help="Repositories resolved in parallel for pairs without refs.")
    ] = 4,
) -> None:
    """Drive every step for the selected pairs, skipping recorded steps; 3 = awaiting resolvers."""
    layout = layout_from(ctx)
    pair_set = read_record(layout.pairs_file, PairSet)
    selected = _select(pair_set, pair_ids or [], all_pairs=all_pairs, origin=origin)
    expectations = None if expect is None else read_record(expect, FixtureExpectations)
    console = Console(soft_wrap=True, highlight=False)
    options = RunOptions(
        no_llm=no_llm,
        skip_claim_c=skip_claim_c,
        prune=prune,
        min_free_gib=min_free_gb,
        jobs=jobs,
    )
    result = run_pairs(layout, pair_set, selected, options, console)
    render_outcomes(console, result.outcomes)
    mismatched = False
    if expectations is not None:
        mismatched = _compare(console, layout, expectations, selected, result, no_llm=no_llm)
    if result.pending:
        render_spawn_lines(console, result.pending)
        raise typer.Exit(AWAITING_RESOLVERS)
    if result.failed or mismatched:
        raise typer.Exit(1)


def _select(
    pair_set: PairSet, pair_ids: list[str], *, all_pairs: bool, origin: PairOrigin | None
) -> list[Pair]:
    if sum((bool(pair_ids), all_pairs, origin is not None)) != 1:
        raise typer.BadParameter("pass pair ids, --all or --origin (exactly one of them)")
    if all_pairs:
        return list(pair_set.pairs)
    if origin is not None:
        return [pair for pair in pair_set.pairs if pair.origin == origin]
    try:
        return select_pairs(pair_set, pair_ids)
    except UnknownPairError as error:
        raise typer.BadParameter(str(error)) from error


def _compare(
    console: Console,
    layout: Layout,
    expectations: FixtureExpectations,
    selected: list[Pair],
    result: RunResult,
    *,
    no_llm: bool,
) -> bool:
    """Write and print the comparison with the expected table; return whether any cell differs."""
    if result.pending:
        console.print(
            f"Expectations not compared: {len(result.pending)} resolver runs are pending."
        )
        return False
    records = {pair.pair_id: pair for pair in collect(layout).pairs}
    ids = [pair.pair_id for pair in selected]
    checks = check_expectations(expectations, records, ids, no_llm=no_llm)
    report = expectation_report(checks)
    path = layout.results / EXPECTATIONS_FILE
    write_record(path, report)
    render_expectations(console, checks, report, path)
    return bool(report.mismatches)
