"""Render what the `pairs` commands fetched and loaded as rich tables."""

from collections import Counter
from pathlib import Path

from rich.console import Console
from rich.table import Table

from ladder.sources import FetchResult


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


def _by_revision(counts: Counter[str | None]) -> str:
    names = sorted(name for name in counts if name is not None)
    return ", ".join([*(f"{name} {counts[name]}" for name in names), f"missing {counts[None]}"])
