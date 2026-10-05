"""Compare a fixture run's records with every asserted cell of the expected outcomes table."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ladder.collect import PairRecords
from ladder.schemas import (
    ExpectedRung,
    ExpectedScenario,
    FixtureExpectations,
    GitRungResult,
    PairRefs,
    Record,
    RungScore,
    StructuralResult,
)

type Value = str | bool | list[str] | None
type Observed = dict[str, Value]

EXPECTATIONS_FILE = "expectations.json"
ABSENT = "absent"
RESOLVED = "resolved"
LLM_RUNGS = frozenset({"llm-raw", "llm-post-weave"})
SCENARIO_CELLS = (
    "resolve_status",
    "contaminated",
    "truth_status",
    "truth_method",
    "truth_rewrite",
    "claim_c_fails_together",
)
RUNG_CELLS = tuple(name for name in ExpectedRung.model_fields if name != "basis")


class Mismatch(Record):
    """One asserted cell whose observed value differs from the expected one."""

    pair_id: str
    cell: str
    expected: Value
    observed: Value


class ExpectationReport(Record):
    """How many cells were compared, which differed, and how many LLM cells were skipped."""

    checked: int
    mismatches: list[Mismatch]
    skipped_llm: int


@dataclass(frozen=True)
class CellCheck:
    """One asserted cell: what was expected, what the records show, and whether it was skipped."""

    pair_id: str
    cell: str
    basis: str | None
    expected: Value
    observed: Value
    skipped: bool

    @property
    def matched(self) -> bool:
        """Return whether the observed value equals the expected one."""
        return self.expected == self.observed


def check_expectations(
    expectations: FixtureExpectations,
    records: Mapping[str, PairRecords],
    selected: Sequence[str],
    *,
    no_llm: bool,
) -> list[CellCheck]:
    """Check every asserted cell of the selected pairs' scenarios against their records.

    With no_llm, every asserted LLM cell other than an `absent` status is skipped. A scenario
    whose pair is not in pairs.json is one failed `pair` cell.
    """
    checks: list[CellCheck] = []
    for scenario in expectations.scenarios:
        pair = records.get(scenario.pair_id)
        if pair is None:
            checks.append(CellCheck(scenario.pair_id, "pair", None, "present", ABSENT, False))
        elif scenario.pair_id in selected:
            checks += _scenario_checks(scenario, pair, no_llm=no_llm)
    return checks


def expectation_report(checks: Sequence[CellCheck]) -> ExpectationReport:
    """Return the compared count, the mismatches and the skipped LLM count of a set of checks."""
    compared = [check for check in checks if not check.skipped]
    return ExpectationReport(
        checked=len(compared),
        mismatches=[
            Mismatch(
                pair_id=check.pair_id,
                cell=check.cell,
                expected=check.expected,
                observed=check.observed,
            )
            for check in compared
            if not check.matched
        ],
        skipped_llm=len(checks) - len(compared),
    )


def _scenario_checks(
    scenario: ExpectedScenario, pair: PairRecords, *, no_llm: bool
) -> list[CellCheck]:
    pair_id = scenario.pair_id
    observed = _scenario(pair)
    checks = [
        CellCheck(pair_id, cell, None, expected, observed[cell], False)
        for cell in SCENARIO_CELLS
        if (expected := getattr(scenario, cell)) is not None
    ]
    for rung, want in scenario.rungs.items():
        seen = observe_rung(pair, rung)
        for cell in RUNG_CELLS:
            expected = getattr(want, cell)
            if expected is None:
                continue
            skipped = no_llm and rung in LLM_RUNGS and expected != ABSENT
            checks.append(
                CellCheck(pair_id, f"{rung}.{cell}", want.basis, expected, seen.get(cell), skipped)
            )
    return checks


def _scenario(pair: PairRecords) -> Observed:
    refs = pair.pair.refs
    return {
        "resolve_status": None if refs is None else refs.status,
        "contaminated": None if refs is None else _contaminated(refs),
        "truth_status": None if refs is None else refs.truth_status,
        "truth_method": None if refs is None else refs.truth_method,
        "truth_rewrite": None if pair.truth is None else pair.truth.rewrite,
        "claim_c_fails_together": None if pair.claim_c is None else pair.claim_c.fails_together,
    }


def observe_rung(pair: PairRecords, rung: str) -> Observed:
    """Return what a pair's records show for one rung, keyed like ExpectedRung's cells."""
    match rung:
        case "git-final":
            return _git(pair.git_final, None)
        case "git":
            return _git(pair.git, pair.score("git"))
        case "weave" | "mergiraf":
            record = pair.weave if rung == "weave" else pair.mergiraf
            return _structural(record, pair.score(rung))
        case "trap":
            return _trap(pair.score(rung))
        case _ if rung in LLM_RUNGS:
            return _llm(pair, rung)
        case _:
            return {}


def _git(record: GitRungResult | None, score: RungScore | None) -> Observed:
    if record is None:
        return {"status": ABSENT}
    return {
        **_scored(score),
        "status": record.status,
        "conflicted_paths": [file.path for file in record.files],
        "types": record.types,
    }


def _structural(record: StructuralResult | None, score: RungScore | None) -> Observed:
    if record is None:
        return {"status": ABSENT}
    return {
        **_scored(score),
        "status": record.status,
        "conflicted_paths": record.remaining_conflicted,
        "parses": all(file.parses is True for file in record.files),
    }


def _trap(score: RungScore | None) -> Observed:
    available = score is not None and score.available
    return {**_scored(score), "status": RESOLVED if available else ABSENT}


def _llm(pair: PairRecords, rung: str) -> Observed:
    if not pair.planned(rung):
        return {"status": ABSENT}
    score = pair.score(rung)
    if score is not None and score.available:
        return {**_scored(score), "status": RESOLVED}
    run = pair.runs.get((rung, 1))
    task = pair.tasks.get((rung, 1))
    if run is not None:
        status = f"failed ({run.failure})"
    elif task is not None and task.status != "pending":
        status = task.status
    else:
        status = "pending"
    return {**_scored(score), "status": status}


def _scored(score: RungScore | None) -> Observed:
    if score is None:
        return {}
    available = score.available
    tests = score.tests_full
    return {
        "mergeable": score.mergeable,
        "human_equivalent": score.human_equivalent,
        "intent_loser": _loser(score) if available else None,
        "tests_pass": None if tests is None else tests.status == "passed",
        "parses": all(file.parses is True for file in score.files) if available else None,
    }


def _loser(score: RungScore) -> str:
    losers = sorted({drop.loser for drop in score.intent_drops})
    return ",".join(losers) if losers else "none"


def _contaminated(refs: PairRefs) -> str:
    sides = [side for side, pr in (("a", refs.a), ("b", refs.b)) if pr.contaminated]
    return ",".join(sides) if sides else "none"
