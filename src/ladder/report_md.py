"""Assemble RESULTS.md: the verdict paragraph, the plots, then every section."""

from pathlib import Path

from ladder.agreement import RunAgreement
from ladder.collect import Collected
from ladder.plots import Plot
from ladder.report_claims import (
    calibration_section,
    claim_c_section,
    llm_failures_section,
    variance_section,
)
from ladder.report_data import (
    pairs_section,
    reconciliation_section,
    runnability_section,
    status_section,
    taxonomy_section,
)
from ladder.report_ladder import (
    category_section,
    ladder_section,
    ladders_section,
    sensitivity_section,
)
from ladder.schemas import Summary
from ladder.verdicts import CLAIMS

TITLE = "# Ladder results"


def _scope(summary: Summary) -> str:
    return (
        f"Pairs attempted: {summary.pairs_attempted}. Conflicting at replay heads (the ladder "
        f"set): {summary.ladder_set}. Ladder pairs with a located human resolution: "
        f"{summary.truth_located}. Every rate is k/n (percent, Wilson 95% interval); decision "
        "rules are the pre-registered ones in PLAN.md section 1."
    )


def _figures(plots: list[Plot], report: Path) -> str:
    base = report.resolve().parent
    return "\n\n".join(
        f"![{plot.caption}]({plot.path.resolve().relative_to(base, walk_up=True).as_posix()})"
        for plot in plots
    )


def render_report(
    collected: Collected,
    summary: Summary,
    agreements: list[RunAgreement],
    plots: list[Plot],
    report: Path,
) -> str:
    """Return the Markdown report; links to plots are relative to the report's directory."""
    pairs = collected.pairs
    verdict = " ".join(summary.verdicts[claim] for claim in CLAIMS if claim in summary.verdicts)
    blocks = [
        TITLE,
        verdict,
        _scope(summary),
        _figures(plots, report),
        ladder_section(summary, pairs),
        ladders_section(summary, pairs),
        taxonomy_section(summary, pairs),
        reconciliation_section(summary, pairs),
        status_section(summary, pairs),
        llm_failures_section(summary, pairs),
        variance_section(summary, agreements),
        claim_c_section(summary, pairs),
        runnability_section(summary, pairs),
        sensitivity_section(summary, pairs),
        category_section(summary, pairs),
        calibration_section(collected.calibration),
        pairs_section(pairs),
    ]
    return "\n\n".join(blocks) + "\n"
