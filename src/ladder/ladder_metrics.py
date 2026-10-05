"""Per-rung rates and the practical and oracle ladders over the ladder set."""

from typing import TypeGuard

from ladder.collect import PairRecords
from ladder.schemas import Rate, RungRow, RungScore
from ladder.stats import share

RUNG_ORDER = ("git", "weave", "mergiraf", "llm-raw", "llm-post-weave", "trap")
LLM_RUNGS = frozenset({"llm-raw", "llm-post-weave"})
STRUCTURAL_RUNGS = ("weave", "mergiraf")
ORACLE_RUNGS = ("git", "weave", "mergiraf", "llm-raw", "llm-post-weave")
DECIDED_TESTS = frozenset({"passed", "failed"})


def applicable(rung: str, pairs: list[PairRecords]) -> list[PairRecords]:
    """Return the pairs a rung's rates are taken over."""
    if rung == "trap":
        return [pair for pair in pairs if pair.score("trap") is not None]
    ladder = [pair for pair in pairs if pair.in_ladder]
    if rung in LLM_RUNGS:
        return [pair for pair in ladder if pair.planned(rung)]
    return ladder


def available(score: RungScore | None) -> TypeGuard[RungScore]:
    """Return whether a rung produced an output for the pair."""
    return score is not None and score.available


def mergeable(score: RungScore | None) -> TypeGuard[RungScore]:
    """Return whether a rung produced a mergeable output."""
    return score is not None and score.available and score.mergeable


def human_equivalent(score: RungScore | None) -> bool:
    """Return whether a rung produced an output equivalent to the human resolution."""
    return score is not None and score.available and score.human_equivalent is True


def intent_dropped(score: RungScore) -> bool:
    """Return whether an output lost a change of either PR."""
    return bool(score.intent_drops)


def tests_passed(score: RungScore) -> bool:
    """Return whether the full suite passed on an output."""
    return score.tests_full is not None and score.tests_full.status == "passed"


def tests_decided(score: RungScore) -> bool:
    """Return whether the full suite ran on an output and passed or failed."""
    return score.tests_full is not None and score.tests_full.status in DECIDED_TESTS


def rung_row(rung: str, pairs: list[PairRecords]) -> RungRow:
    """Return every rate of one rung, run 1, over the pairs it applies to."""
    scope = applicable(rung, pairs)
    scores = [pair.score(rung) for pair in scope]
    located = [pair.score(rung) for pair in scope if pair.truth_located]
    outputs = [score for score in scores if score is not None and score.available]
    tested = [score for score in outputs if tests_decided(score)]
    return RungRow(
        rung=rung,
        available=share(scores, available),
        mergeable=share(scores, mergeable),
        human_equivalent=share(located, human_equivalent),
        human_equivalent_unordered=share(
            located, lambda score: available(score) and score.human_equivalent_unordered is True
        ),
        intent_preserved_both=share(
            outputs,
            lambda score: score.intent_preserved_a is True and score.intent_preserved_b is True,
        ),
        intent_dropped=share(outputs, intent_dropped),
        tests_pass=share(tested, tests_passed),
        tests_pass_intent_dropped=share(
            tested, lambda score: tests_passed(score) and intent_dropped(score)
        ),
    )


def scored_rungs(pairs: list[PairRecords]) -> list[str]:
    """Return the rungs, in ladder order, that have a run-1 score for at least one pair."""
    return [rung for rung in RUNG_ORDER if any(pair.score(rung) is not None for pair in pairs)]


def rung_rows(pairs: list[PairRecords]) -> list[RungRow]:
    """Return the ladder table: one row per scored rung."""
    return [rung_row(rung, pairs) for rung in scored_rungs(pairs)]


def practical_llm_rung(pair: PairRecords) -> str:
    """Return the LLM rung the practical ladder climbs to when no structural output merges."""
    post_weave_task = pair.tasks.get(("llm-post-weave", 1))
    if post_weave_task is not None and post_weave_task.status == "identical_input":
        return "llm-raw"
    return "llm-post-weave" if pair.planned("llm-post-weave") else "llm-raw"


def practical_step(pair: PairRecords) -> tuple[str, RungScore] | None:
    """Return the first mergeable output on weave, mergiraf, then the LLM, with its rung."""
    for rung in (*STRUCTURAL_RUNGS, practical_llm_rung(pair)):
        score = pair.score(rung)
        if mergeable(score):
            return rung, score
    return None


def judged(pairs: list[PairRecords]) -> list[PairRecords]:
    """Return the ladder pairs whose human resolution was located."""
    return [pair for pair in pairs if pair.in_ladder and pair.truth_located]


def practical_human_equivalent(pairs: list[PairRecords]) -> Rate:
    """Return the share of judged pairs whose practical-ladder output is human-equivalent."""

    def hit(pair: PairRecords) -> bool:
        step = practical_step(pair)
        return step is not None and human_equivalent(step[1])

    return share(judged(pairs), hit)


def oracle_human_equivalent(pairs: list[PairRecords]) -> Rate:
    """Return the share of judged pairs for which any rung's output is human-equivalent."""
    return share(
        judged(pairs),
        lambda pair: any(human_equivalent(pair.score(rung)) for rung in ORACLE_RUNGS),
    )


def practical_mergeable(pairs: list[PairRecords]) -> Rate:
    """Return the share of ladder pairs whose practical ladder reaches a mergeable output."""
    return share(
        [pair for pair in pairs if pair.in_ladder], lambda pair: practical_step(pair) is not None
    )


def structural_mergeable(pairs: list[PairRecords]) -> Rate:
    """Return the share of ladder pairs that weave or mergiraf makes mergeable."""
    return share(
        [pair for pair in pairs if pair.in_ladder],
        lambda pair: any(mergeable(pair.score(rung)) for rung in STRUCTURAL_RUNGS),
    )


def structural_human_equivalent(pairs: list[PairRecords]) -> Rate:
    """Return the share of judged pairs that weave or mergiraf resolves as the humans did."""
    return share(
        judged(pairs),
        lambda pair: any(human_equivalent(pair.score(rung)) for rung in STRUCTURAL_RUNGS),
    )


def accepted_at(pairs: list[PairRecords]) -> list[tuple[str, int, int]]:
    """Return (rung, judged pairs accepted there, how many human-equivalent); `none` = never."""
    steps = [practical_step(pair) for pair in judged(pairs)]
    order = [*STRUCTURAL_RUNGS, "llm-post-weave", "llm-raw", "none"]
    rows: list[tuple[str, int, int]] = []
    for rung in order:
        here = [step for step in steps if (step[0] if step else "none") == rung]
        equivalent = sum(step is not None and human_equivalent(step[1]) for step in here)
        rows.append((rung, len(here), equivalent))
    return rows


def mergeable_not_equivalent(rung: str, pairs: list[PairRecords]) -> Rate:
    """Return the share of a rung's judged pairs with a mergeable, not human-equivalent output."""
    return share(
        [pair.score(rung) for pair in applicable(rung, pairs) if pair.truth_located],
        lambda score: mergeable(score) and not human_equivalent(score),
    )
