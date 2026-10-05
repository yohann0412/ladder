"""The `ladder report` command: summary.json, plots and RESULTS.md from every result record."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from ladder.agreement import run_agreements
from ladder.collect import collect
from ladder.context import layout_from
from ladder.jsonio import write_record
from ladder.metrics import summarise
from ladder.plots import write_plots
from ladder.ratefmt import cell
from ladder.report_md import render_report
from ladder.schemas import Summary

app = typer.Typer()

SUMMARY_FILE = "summary.json"
PLOTS_DIR = "plots"


def _headline(summary: Summary) -> Table:
    table = Table(title="Headline numbers")
    table.add_column("metric")
    table.add_column("value", justify="right")
    table.add_row("pairs attempted", str(summary.pairs_attempted))
    table.add_row("ladder set", str(summary.ladder_set))
    table.add_row("truth located", str(summary.truth_located))
    table.add_row(
        "practical ladder human-equivalent", cell(summary.practical_ladder_human_equivalent)
    )
    table.add_row("oracle ladder human-equivalent", cell(summary.oracle_ladder_human_equivalent))
    table.add_row("resolver agreement", cell(summary.resolver_agreement))
    table.add_row("Claim C fails together", cell(summary.claim_c_fails_together))
    return table


@app.command()
def report(
    ctx: typer.Context,
    out: Annotated[Path, typer.Option(help="Markdown report to write.")] = Path("RESULTS.md"),
) -> None:
    """Write summary.json, one plot per claim, and the Markdown report from every record."""
    layout = layout_from(ctx)
    console = Console()
    if not layout.pairs_file.is_file():
        console.print(f"[red]no pairs file at {layout.pairs_file}[/red]")
        raise typer.Exit(1)
    collected = collect(layout)
    agreements = run_agreements(layout, collected.pairs)
    summary = summarise(collected, agreements)
    write_record(layout.results / SUMMARY_FILE, summary)
    plots = write_plots(summary, layout.results / PLOTS_DIR)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(collected, summary, agreements, plots, out), encoding="utf-8")
    console.print(_headline(summary))
    for claim, text in summary.verdicts.items():
        console.print(f"[bold]{claim}[/bold] {text}", highlight=False)
    if collected.unknown_dirs:
        console.print(
            f"Ignored {len(collected.unknown_dirs)} result directories of pairs not in "
            f"{layout.pairs_file}: {', '.join(collected.unknown_dirs)}"
        )
    console.print(f"Wrote {layout.results / SUMMARY_FILE}, {len(plots)} plots, {out}")
