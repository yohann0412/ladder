"""Run a mergeable resolved state's tests: the full suite, then the test files A and B touched."""

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from ladder.layout import Layout
from ladder.pairsides import SIDES, PairSides
from ladder.pairsuite import PairSuite, SuiteUnavailable, open_pair_suite
from ladder.schemas import Runnability, Side, TestOutcome, WorkspaceRecord
from ladder.testrun import not_run, outcome

RUNNABLE = frozenset({"runnable", "runnable_with_modifications"})


@dataclass(frozen=True)
class SuiteOutcomes:
    """The full suite's outcome and the outcomes of A's and of B's own test files."""

    full: TestOutcome | None
    a: TestOutcome | None
    b: TestOutcome | None


NOT_TESTED = SuiteOutcomes(None, None, None)


@dataclass
class PairTests:
    """Runs a pair's suite on its resolved states, opening the base environment once."""

    layout: Layout
    runnability: Runnability | None
    workspace: WorkspaceRecord
    sides: PairSides

    def outcomes(self, label: str, tree: Path, mergeable: bool) -> SuiteOutcomes:
        """Return the tests of a mergeable state; not_run on an unrunnable repository."""
        if not mergeable:
            return NOT_TESTED
        if self.runnability is None or self.runnability.status not in RUNNABLE:
            return _same(not_run(self._unrunnable()))
        suite = self._suite
        if isinstance(suite, SuiteUnavailable):
            return _same(outcome("error", [], f"suite unavailable: {suite}"))
        full = suite.run(label, tree)
        a, b = (self._side(suite, label, tree, side) for side in SIDES)
        return SuiteOutcomes(full, a, b)

    def _side(self, suite: PairSuite, label: str, tree: Path, side: Side) -> TestOutcome:
        files = [path for path in self.sides.tests[side] if (tree / path).is_file()]
        if not files:
            return not_run(f"no tests changed by {side.upper()}")
        return suite.run(label, tree, only=files)

    @cached_property
    def _suite(self) -> PairSuite | SuiteUnavailable:
        if self.runnability is None:
            return SuiteUnavailable("no runnability record")
        try:
            return open_pair_suite(self.layout, self.runnability, self.workspace)
        except SuiteUnavailable as error:
            return error

    def _unrunnable(self) -> str:
        if self.runnability is None:
            return "no runnability record; run ladder runnable first"
        record = self.runnability
        return f"repository unrunnable at base: {record.reason} ({record.reason_detail})"


def _same(result: TestOutcome) -> SuiteOutcomes:
    return SuiteOutcomes(result, result, result)
