"""The `ladder pairs` commands: fetch the pair sources, load and sample pairs, resolve them."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress

from ladder.context import layout_from
from ladder.extracts import AIDEV_PRS, AidevPr, read_rows
from ladder.jsonio import read_optional, read_record, write_record
from ladder.pairload import pairs_from_fixture, pairs_from_source
from ladder.pairs_view import render_fetch, render_fixture, render_summary, render_supplementary
from ladder.pairselect import UnknownPairError, select_pairs
from ladder.pairsummary import summarise
from ladder.resolve import resolve_pairs, with_refs
from ladder.resolve_view import render_resolve
from ladder.schemas import PairRefs, PairSet
from ladder.sources import fetch_sources
from ladder.supplementary import sample_supplementary, with_supplementary

app = typer.Typer(
    help="Fetch the pair sources, load or sample pairs into pairs.json and resolve their commits.",
    no_args_is_help=True,
)


@app.command("fetch-sources")
def fetch_sources_command(
    ctx: typer.Context,
    out: Annotated[
        Path, typer.Option(help="Directory to write the vendored source extracts into.")
    ] = Path("data/source"),
) -> None:
    """Download the replication package and AIDev tables and vendor the extracts and candidates."""
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


@app.command("sample-supplementary")
def sample_supplementary_command(
    ctx: typer.Context,
    source: Annotated[
        Path,
        typer.Option(
            help="Vendored sources holding the supplementary candidates (from fetch-sources).",
            exists=True,
            file_okay=False,
        ),
    ] = Path("data/source"),
    seed: Annotated[int, typer.Option(help="Seed of the repository shuffle (D15: 42).")] = 42,
) -> None:
    """Write one supplementary pair per candidate repository, offline, in the seed's order."""
    target = layout_from(ctx).pairs_file
    existing = read_optional(target, PairSet)
    pairs = sample_supplementary(source, seed)
    pair_set = with_supplementary(existing, pairs, source)
    write_record(target, pair_set)
    render_supplementary(Console(), pairs, len(pair_set.pairs) - len(pairs), seed, target)


@app.command()
def resolve(
    ctx: typer.Context,
    all_pairs: Annotated[bool, typer.Option("--all", help="Resolve every pair.")] = False,
    pair: Annotated[
        list[str] | None, typer.Option("--pair", help="Pair id to resolve; repeatable.")
    ] = None,
    jobs: Annotated[int, typer.Option(min=1, help="Repositories resolved in parallel.")] = 4,
    refresh: Annotated[
        bool, typer.Option("--refresh", help="Also re-fetch the branches of cached clones.")
    ] = False,
) -> None:
    """Fetch both PR heads of each pair and record heads, bases, merge and truth commits."""
    layout = layout_from(ctx)
    pair_set = read_record(layout.pairs_file, PairSet)
    if all_pairs == bool(pair):
        raise typer.BadParameter("pass either --all or at least one --pair")
    try:
        selected = pair_set.pairs if all_pairs else select_pairs(pair_set, pair or [])
    except UnknownPairError as error:
        raise typer.BadParameter(str(error)) from error
    results: dict[str, PairRefs] = {}
    with Progress(console=Console(stderr=True), transient=True) as progress:
        task = progress.add_task("resolving pairs", total=len(selected))

        def done(pair_id: str, refs: PairRefs) -> None:
            results[pair_id] = refs
            progress.advance(task)

        try:
            resolve_pairs(layout, selected, jobs=jobs, refresh=refresh, done=done)
        finally:
            write_record(layout.pairs_file, with_refs(pair_set, results))
    render_resolve(Console(), [results[pair.pair_id] for pair in selected])
