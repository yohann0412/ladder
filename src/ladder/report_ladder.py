"""Report sections about the ladder: rung table, ladders, sensitivity cuts, file categories."""

from ladder.collect import PairRecords
from ladder.cuts import (
    CATEGORIES,
    human_equivalent_by_category,
    intent_dropped_by_category,
    sensitivity,
)
from ladder.ladder_metrics import (
    accepted_at,
    mergeable_not_equivalent,
    practical_mergeable,
    structural_human_equivalent,
    structural_mergeable,
)
from ladder.md import section, table
from ladder.ratefmt import cell
from ladder.schemas import Rate, RungRow, Summary

LADDER_HEADERS = (
    "rung",
    "available",
    "mergeable",
    "human-equivalent",
    "human-equivalent up to order",
    "intent preserved both",
    "intent dropped",
    "tests pass",
    "tests pass but intent dropped",
)
LADDER_NOTE = (
    "Each cell is k/n (percent, Wilson 95% interval). Available and mergeable are over the "
    "pairs a rung applies to: the ladder set for git, weave and mergiraf; ladder pairs whose "
    "resolver plan includes the rung for the LLM rungs; pairs with a planted trap for trap. "
    "Human-equivalent columns are over those pairs with a located human resolution. Intent "
    "columns are over available outputs. Test columns are over available outputs whose full "
    "suite passed or failed (flaky, capped, errored and not-run suites are excluded)."
)


def _metrics(row: RungRow) -> list[Rate]:
    return [
        row.available,
        row.mergeable,
        row.human_equivalent,
        row.human_equivalent_unordered,
        row.intent_preserved_both,
        row.intent_dropped,
        row.tests_pass,
        row.tests_pass_intent_dropped,
    ]


def ladder_section(summary: Summary, pairs: list[PairRecords]) -> str:
    """Return the ladder table and the mergeable-but-not-human-equivalent line per rung."""
    rows = [[row.rung, *(cell(rate) for rate in _metrics(row))] for row in summary.rungs]
    not_equivalent = table(
        ["rung", "mergeable but not human-equivalent"],
        [[row.rung, cell(mergeable_not_equivalent(row.rung, pairs))] for row in summary.rungs],
    )
    return section("Ladder", table(LADDER_HEADERS, rows), LADDER_NOTE, not_equivalent)


def ladders_section(summary: Summary, pairs: list[PairRecords]) -> str:
    """Return the practical and oracle ladders, the structural half, and where pairs stopped."""
    lines = "\n".join(
        [
            "- Practical ladder (weave, mergiraf, then the LLM; first mergeable output accepted), "
            f"human-equivalent: {cell(summary.practical_ladder_human_equivalent)}",
            f"- Practical ladder reaches a mergeable output: {cell(practical_mergeable(pairs))}",
            "- Oracle ladder (any of git, weave, mergiraf, llm-raw, llm-post-weave "
            f"human-equivalent): {cell(summary.oracle_ladder_human_equivalent)}",
            "- Structural half (weave or mergiraf) mergeable over the ladder set: "
            f"{cell(structural_mergeable(pairs))}",
            "- Structural half human-equivalent over pairs with a located human resolution: "
            f"{cell(structural_human_equivalent(pairs))}",
        ]
    )
    stops = table(
        ["accepted at", "pairs", "human-equivalent"],
        [list(row) for row in accepted_at(pairs)],
    )
    return section("Practical and oracle ladders", lines, stops)


def sensitivity_section(summary: Summary, pairs: list[PairRecords]) -> str:
    """Return human-equivalent rates without rewrite-truth pairs and without flagged PR text."""
    rungs = [row.rung for row in summary.rungs]
    rows = [[name, *(cell(rate) for rate in rates)] for name, rates in sensitivity(pairs, rungs)]
    headers = [
        "human-equivalent",
        "all",
        "without rewrite truth",
        "without PR text about conflicts, rebases or merging",
    ]
    return section("Sensitivity cuts", table(headers, rows))


def category_section(summary: Summary, pairs: list[PairRecords]) -> str:
    """Return per-file human-equivalent and intent-dropped rates by file category and rung."""
    rungs = [row.rung for row in summary.rungs]
    equivalent = {rung: human_equivalent_by_category(pairs, rung) for rung in rungs}
    dropped = {rung: intent_dropped_by_category(pairs, rung) for rung in rungs}

    def grid(rates: dict[str, dict[str, Rate]]) -> str:
        shown = [c for c in CATEGORIES if any(rates[rung][c].denominator for rung in rungs)]
        return table(
            ["category", *rungs], [[c, *(cell(rates[rung][c]) for rung in rungs)] for c in shown]
        )

    return section(
        "By file category",
        "Per conflicted file of available outputs. Human-equivalent is over files of pairs with "
        "a located human resolution; intent dropped counts files on which a drop was recorded.",
        "### Human-equivalent files\n\n" + grid(equivalent),
        "### Files with intent dropped\n\n" + grid(dropped),
    )
