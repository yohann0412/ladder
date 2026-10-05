"""Report sections about the pair set: taxonomy, reconciliation, statuses, runnability, pairs."""

from ladder.collect import PairRecords
from ladder.cuts import subset_profile
from ladder.md import section, table
from ladder.metrics import POOL, STRATA
from ladder.pair_table import pair_line
from ladder.ratefmt import cell
from ladder.schemas import Summary
from ladder.taxonomy import agent_pairs, files_by_category, resolve_facts, transitions

NOT_MEASURED = "not measured"


def taxonomy_section(summary: Summary, pairs: list[PairRecords]) -> str:
    """Return conflict types, conflicted files by category, and conflicts per agent pair."""
    types = table(
        ["type", "CONFLICT messages"], [list(item) for item in summary.conflict_types.items()]
    )
    categories = table(
        ["category", "conflicted files"], [list(item) for item in files_by_category(pairs).items()]
    )
    agents = table(
        ["agent A / agent B", "conflicting at replay heads"],
        [[label, cell(rate)] for label, rate in agent_pairs(pairs)],
    )
    return section(
        "Conflict taxonomy",
        "Over the git rung at replay heads.",
        "### Conflict types\n\n" + types,
        "### Conflicted files by category\n\n" + categories,
        "### Agent pairs\n\n" + agents,
    )


def reconciliation_section(summary: Summary, pairs: list[PairRecords]) -> str:
    """Return paper, final-head and replay-head conflict rates and the label transitions."""
    sources = [
        summary.paper_conflict_rate,
        summary.final_conflict_rate,
        summary.replay_conflict_rate,
    ]
    rates = table(
        ["stratum", "paper", "final heads", "replay heads"],
        [
            [stratum, *(cell(rates[stratum]) if rates else NOT_MEASURED for rates in sources)]
            for stratum in (*STRATA, POOL)
        ],
    )
    moves = table(
        ["paper label", "final heads", "replay heads", "pairs"],
        [list(row) for row in transitions(pairs)],
    )
    return section(
        "Reconciliation with the paper",
        "Conflicting / (clean + conflicting); unavailable paper labels and git errors are "
        "excluded.",
        rates,
        "### Transitions\n\n" + moves,
    )


def status_section(summary: Summary, pairs: list[PairRecords]) -> str:
    """Return ref resolution statuses and contamination, rewind and truth counts."""
    statuses = table(
        ["resolve status", "pairs"], [list(item) for item in summary.resolve_status.items()]
    )
    facts = table(["fact", "pairs"], [list(item) for item in resolve_facts(pairs)])
    return section("Resolve statuses", statuses, facts)


def runnability_section(summary: Summary, pairs: list[PairRecords]) -> str:
    """Return runnability counts with reasons and the runnable subset against the ladder set."""
    counts = table(["runnability", "pairs"], [list(item) for item in summary.runnability.items()])
    profile = table(
        ["characteristic", "runnable ladder pairs", "all ladder pairs"],
        [list(row) for row in subset_profile(pairs)],
    )
    return section(
        "Runnability",
        counts,
        "### Runnable subset against the ladder set\n\n"
        "Language is the one the runnability check detected; `unknown` when it was not run.\n\n"
        + profile,
    )


def pairs_section(pairs: list[PairRecords]) -> str:
    """Return one row per attempted pair with its outcome and blocker."""
    headers = [
        "pair",
        "resolve",
        "git final -> replay",
        "rungs with output",
        "truth",
        "runnability",
        "outcome",
        "blocker",
    ]
    lines = [pair_line(pair) for pair in pairs]
    rows = [
        [
            line.pair_id,
            line.resolve,
            line.git,
            line.outputs,
            line.truth,
            line.runnability,
            line.outcome,
            line.blocker,
        ]
        for line in lines
    ]
    return section("Every pair attempted", table(headers, rows))
