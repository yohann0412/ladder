"""Compute every headline number of an experiment into a Summary."""

from collections import Counter
from collections.abc import Callable, Iterable

from ladder.agreement import RunAgreement
from ladder.collect import Collected, PairRecords
from ladder.failure_causes import EXCUSED, excused, failure_cause
from ladder.ladder_metrics import (
    oracle_human_equivalent,
    practical_best_case,
    practical_human_equivalent,
    rung_rows,
)
from ladder.layout import Layout
from ladder.schemas import GitRungResult, Rate, ResolverRun, Summary
from ladder.stats import rate, share
from ladder.verdicts import verdicts

STRATA = ("same", "cross")
POOL = "pool"
UNRESOLVED = "unresolved"


def sorted_counts(values: Iterable[str]) -> dict[str, int]:
    """Count values into a dict ordered by key."""
    return dict(sorted(Counter(values).items()))


def resolve_status(pair: PairRecords) -> str:
    """Return the pair's ref resolution status, or `unresolved` when refs were never resolved."""
    return UNRESOLVED if pair.pair.refs is None else pair.pair.refs.status


def conflict_rates(
    pairs: list[PairRecords], conflicted: Callable[[PairRecords], bool | None]
) -> dict[str, Rate]:
    """Return conflicting/evaluable per stratum and pooled; conflicted is None when unevaluable."""
    outcomes = [(pair.pair.stratum, conflicted(pair)) for pair in pairs]
    evaluable = [(stratum, flag) for stratum, flag in outcomes if flag is not None]
    rates = {
        stratum: share([flag for group, flag in evaluable if group == stratum], bool)
        for stratum in STRATA
    }
    rates[POOL] = share([flag for _, flag in evaluable], bool)
    return rates


def paper_conflicted(pair: PairRecords) -> bool | None:
    """Return the paper's label as conflicted or clean, None when it is unavailable or absent."""
    paper = pair.pair.paper
    if paper is None or paper.label not in ("CLEAN", "CONFLICT"):
        return None
    return paper.label == "CONFLICT"


def git_conflicted(result: GitRungResult | None) -> bool | None:
    """Return a git rung record as conflicted or clean, None when it errored or is absent."""
    if result is None or result.status == "error":
        return None
    return result.status == "conflicted"


def reconciliation(pairs: list[PairRecords]) -> dict[str, dict[str, Rate]]:
    """Return the paper, final-head and replay-head conflict rates; empty when no record exists."""
    sources: dict[str, tuple[bool, Callable[[PairRecords], bool | None]]] = {
        "paper": (any(p.pair.paper is not None for p in pairs), paper_conflicted),
        "final": (
            any(p.git_final is not None for p in pairs),
            lambda pair: git_conflicted(pair.git_final),
        ),
        "replay": (any(p.git is not None for p in pairs), lambda pair: git_conflicted(pair.git)),
    }
    return {
        name: conflict_rates(pairs, conflicted) if present else {}
        for name, (present, conflicted) in sources.items()
    }


def conflict_types(pairs: list[PairRecords]) -> dict[str, int]:
    """Count conflict types over replay-head git records that conflicted, most frequent first."""
    counts = Counter(
        kind for pair in pairs if pair.git and pair.in_ladder for kind in pair.git.types
    )
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def llm_failures(
    pairs: list[PairRecords], cause: Callable[[ResolverRun], str | None]
) -> dict[str, int]:
    """Count failed resolver runs by cause, adding input-capped tasks that have no run record."""
    causes = [label for pair in pairs for run in pair.runs.values() if (label := cause(run))]
    capped = [
        "input_cap"
        for pair in pairs
        for key, task in pair.tasks.items()
        if task.status == "input_cap" and key not in pair.runs
    ]
    return sorted_counts([*causes, *capped])


def claim_c_rate(pairs: list[PairRecords]) -> Rate:
    """Return fails-together among Claim C records with a decided outcome."""
    decided = [
        pair.claim_c.fails_together
        for pair in pairs
        if pair.claim_c is not None and pair.claim_c.fails_together is not None
    ]
    return share(decided, bool)


def runnability_counts(pairs: list[PairRecords]) -> dict[str, int]:
    """Count runnability statuses and, for unrunnable pairs, `unrunnable:<reason>`."""
    labels: list[str] = []
    for pair in pairs:
        record = pair.runnability
        if record is None:
            continue
        labels.append(record.status)
        if record.status == "unrunnable":
            labels.append(f"unrunnable:{record.reason or 'unspecified'}")
    return sorted_counts(labels)


def summarise(layout: Layout, collected: Collected, agreements: list[RunAgreement]) -> Summary:
    """Return the Summary of an experiment's records."""
    pairs = collected.pairs
    rows = rung_rows(pairs)
    practical = practical_human_equivalent(pairs)
    best_case = practical_best_case(pairs, lambda pair: excused(layout, pair))
    causes = llm_failures(pairs, lambda run: failure_cause(layout, run))
    fails_together = claim_c_rate(pairs)
    rates = reconciliation(pairs)
    llm_raw = next((row for row in rows if row.rung == "llm-raw"), None)
    return Summary(
        pairs_attempted=len(pairs),
        resolve_status=sorted_counts(resolve_status(pair) for pair in pairs),
        paper_conflict_rate=rates["paper"],
        final_conflict_rate=rates["final"],
        replay_conflict_rate=rates["replay"],
        conflict_types=conflict_types(pairs),
        ladder_set=sum(pair.in_ladder for pair in pairs),
        truth_located=sum(pair.in_ladder and pair.truth_located for pair in pairs),
        rungs=rows,
        practical_ladder_human_equivalent=practical,
        claim_a_best_case=best_case,
        oracle_ladder_human_equivalent=oracle_human_equivalent(pairs),
        llm_failures=llm_failures(pairs, lambda run: run.failure),
        llm_failure_causes=causes,
        resolver_agreement=rate(sum(item.agrees for item in agreements), len(agreements)),
        claim_c_fails_together=fails_together,
        runnability=runnability_counts(pairs),
        verdicts=verdicts(
            practical, None if EXCUSED.isdisjoint(causes) else best_case, llm_raw, fails_together
        ),
    )
