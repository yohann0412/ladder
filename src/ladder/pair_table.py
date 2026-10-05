"""One line per attempted pair: how far it got, what it produced, and what stopped it."""

from dataclasses import dataclass

from ladder.collect import PairRecords
from ladder.ladder_metrics import RUNG_ORDER, available, human_equivalent, practical_step
from ladder.metrics import resolve_status
from ladder.taxonomy import ABSENT

NONE = "-"


@dataclass(frozen=True)
class PairLine:
    """The full-table row of one pair."""

    pair_id: str
    resolve: str
    git: str
    outputs: str
    truth: str
    runnability: str
    outcome: str
    blocker: str


def _outputs(pair: PairRecords) -> str:
    order = {rung: index for index, rung in enumerate(RUNG_ORDER)}
    keys = sorted(
        (key for key, score in pair.scores.items() if available(score)),
        key=lambda key: (order.get(key[0], len(order)), key),
    )
    return ", ".join(rung if run == 1 else f"{rung} run {run}" for rung, run in keys) or NONE


def _truth(pair: PairRecords) -> str:
    if pair.truth is None:
        return NONE
    return pair.truth.status + (" (rewrite)" if pair.truth.rewrite else "")


def _runnability(pair: PairRecords) -> str:
    record = pair.runnability
    if record is None:
        return NONE
    return record.status if record.reason is None else f"{record.status}: {record.reason}"


def _ladder_outcome(pair: PairRecords) -> str:
    step = practical_step(pair)
    if step is None:
        return "no rung mergeable"
    rung, score = step
    if not pair.truth_located:
        return f"{rung}: mergeable"
    verdict = "human-equivalent" if human_equivalent(score) else "not human-equivalent"
    return f"{rung}: {verdict}"


def _claim_c_outcome(pair: PairRecords) -> str:
    record = pair.claim_c
    if record is None or record.fails_together is None:
        return "clean"
    return "clean, fails together" if record.fails_together else "clean, passes together"


def _blocker(pair: PairRecords) -> str:
    refs = pair.pair.refs
    if refs is None or refs.status != "ok":
        return resolve_status(pair)
    if pair.git is None or pair.git.status == "error":
        return "no replay-head git record" if pair.git is None else "git error"
    if pair.in_ladder:
        if pair.truth_located:
            return NONE
        return f"truth {'not extracted' if pair.truth is None else pair.truth.status}"
    if pair.claim_c is None:
        return "no Claim C record"
    reason = pair.claim_c.excluded_reason
    return NONE if reason is None else f"Claim C excluded: {reason}"


def pair_line(pair: PairRecords) -> PairLine:
    """Return the full-table row of one pair."""
    final = ABSENT if pair.git_final is None else pair.git_final.status
    replay = ABSENT if pair.git is None else pair.git.status
    if pair.in_ladder:
        outcome = _ladder_outcome(pair)
    elif pair.git is not None and pair.git.status == "clean":
        outcome = _claim_c_outcome(pair)
    else:
        outcome = NONE
    return PairLine(
        pair_id=pair.pair_id,
        resolve=resolve_status(pair),
        git=f"{final} -> {replay}",
        outputs=_outputs(pair),
        truth=_truth(pair),
        runnability=_runnability(pair),
        outcome=outcome,
        blocker=_blocker(pair),
    )
