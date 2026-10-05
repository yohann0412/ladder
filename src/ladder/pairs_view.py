"""Render what the `pairs` commands fetched and loaded as rich tables."""

from collections import Counter
from pathlib import Path

from rich.console import Console
from rich.table import Table

from ladder.pairsummary import ConflictRate, PairSummary
from ladder.schemas import PairSet
from ladder.sources import FetchResult

UNAVAILABLE_PREFIX = "UNAVAIL_"


def render_fetch(console: Console, result: FetchResult, out: Path) -> None:
    """Print every downloaded file with its md5, and which revision supplied the AIDev rows."""
    files = Table(title=f"Pair sources vendored into {out}")
    files.add_column("source file")
    files.add_column("md5")
    for file in result.files:
        files.add_row(file.name, file.md5)
    console.print(files)
    for revision in result.revisions:
        console.print(f"AIDev {revision.name} = {revision.sha}")
    console.print(f"AIDev PR rows: {_by_revision(Counter(pr.revision for pr in result.prs))}")
    repo_revisions = Counter(repo.revision for repo in result.repos)
    console.print(f"AIDev repository rows: {_by_revision(repo_revisions)}")
    candidates = result.candidates
    strata = Counter(candidate.stratum for candidate in candidates.first)
    console.print(
        f"Supplementary candidates: {candidates.pairs} pairs in {len(candidates.first)} "
        f"repositories; first per repository: same {strata['same']}, cross {strata['cross']}"
    )


def render_summary(console: Console, summary: PairSummary, target: Path) -> None:
    """Print conflict rates, agent pairs, conflict types, merge state and AIDev coverage."""
    console.print(f"Loaded {summary.pairs} paper pairs into {target}")
    console.print(_rate_table("Conflicts per stratum", ["stratum"], summary.strata, detailed=True))
    console.print(
        _rate_table(
            "Conflicts per agent pair", ["agent A", "agent B"], summary.agent_pairs, detailed=False
        )
    )
    types = Table(title="Conflict types")
    types.add_column("type")
    types.add_column("CONFLICT messages", justify="right")
    for kind, count in summary.types:
        types.add_row(kind, str(count))
    types.add_section()
    types.add_row("total", str(sum(count for _, count in summary.types)))
    console.print(types)
    console.print(f"Conflicted files: {summary.conflicted_files}")
    console.print(
        f"Both PRs merged: {summary.both_merged} of {summary.pairs} pairs, "
        f"{summary.both_merged_conflict} of {summary.conflict_pairs} CONFLICT pairs"
    )
    console.print(f"AIDev PR rows: {_by_revision(Counter(summary.pr_revisions))}")
    console.print(f"PRs missing from AIDev: {summary.pr_revisions.get(None, 0)}")


def render_fixture(console: Console, pair_set: PairSet, target: Path) -> None:
    """Print the fixture pairs that were written."""
    ids = ", ".join(pair.pair_id for pair in pair_set.pairs)
    console.print(f"Loaded {len(pair_set.pairs)} fixture pairs into {target}: {ids}")


def _rate_table(
    title: str, headers: list[str], rates: list[ConflictRate], *, detailed: bool
) -> Table:
    table = Table(title=title)
    for header in headers:
        table.add_column(header)
    table.add_column("conflicts/evaluable", justify="right")
    table.add_column("rate", justify="right")
    table.add_column("unavailable", justify="left" if detailed else "right")
    for rate in rates:
        percent = "-" if rate.percent is None else f"{rate.percent:.1f}%"
        table.add_row(*rate.group, rate.ratio, percent, _unavailable(rate.unavailable, detailed))
    return table


def _unavailable(counts: dict[str, int], detailed: bool) -> str:
    total = sum(counts.values())
    if not total or not detailed:
        return str(total)
    parts = ", ".join(
        f"{label.removeprefix(UNAVAILABLE_PREFIX)} {count}" for label, count in counts.items()
    )
    return f"{total} ({parts})"


def _by_revision(counts: Counter[str | None]) -> str:
    names = sorted(name for name in counts if name is not None)
    return ", ".join([*(f"{name} {counts[name]}" for name in names), f"missing {counts[None]}"])
