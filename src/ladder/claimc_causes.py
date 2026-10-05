"""Name the one cause that excluded a Claim C pair, from its structured outcomes where possible."""

from ladder.claimc import SUITE_ERROR_PREFIX, UNRUNNABLE_PREFIX
from ladder.diskfloor import FREE_DISK
from ladder.pairsuite import INSTALL_FAILED
from ladder.procrun import TIMED_OUT
from ladder.schemas import ClaimCRecord, TestOutcome, TestStatus

SUITE_UNAVAILABLE = "suite unavailable"
DISK_FLOOR = "stopped at the free-disk floor"
MERGE_BREAKS_INSTALL = "merge breaks dependency installation"
FAILS_ALONE = "a or b fails alone"
ERROR_OR_NOT_RUN = "error or not run"
CAPPED = "capped"
FLAKY = "flaky"
OTHER = "other"
NOT_ATTEMPTED = "not attempted: cut"
INSTALLED: frozenset[TestStatus] = frozenset({"passed", "failed", "flaky", "capped"})
STATUS_CAUSES: tuple[tuple[frozenset[TestStatus], str], ...] = (
    (frozenset({"error", "not_run"}), ERROR_OR_NOT_RUN),
    (frozenset({"capped"}), CAPPED),
    (frozenset({"flaky"}), FLAKY),
)


def claim_c_cause(record: ClaimCRecord) -> str | None:
    """Return the first cause, in the report's order, that excluded a record; None if decided."""
    reason = record.excluded_reason
    if reason is None:
        return None
    if reason.startswith(UNRUNNABLE_PREFIX):
        return UNRUNNABLE_PREFIX + reason.removeprefix(UNRUNNABLE_PREFIX).partition(" (")[0]
    if reason.startswith(SUITE_ERROR_PREFIX):
        return SUITE_UNAVAILABLE
    return _outcome_cause(record.a, record.b, record.merge)


def _outcome_cause(a: TestOutcome, b: TestOutcome, merge: TestOutcome) -> str:
    if any(FREE_DISK in outcome.detail for outcome in (a, b, merge)):
        return DISK_FLOOR
    install = _failed_install(merge)
    merge_capped = install is not None and TIMED_OUT in install
    if install is not None and not merge_capped and {a.status, b.status} <= INSTALLED:
        return MERGE_BREAKS_INSTALL
    if "failed" in (a.status, b.status):
        return FAILS_ALONE
    statuses = {a.status, b.status, "capped" if merge_capped else merge.status}
    return next((cause for wanted, cause in STATUS_CAUSES if statuses & wanted), OTHER)


def _failed_install(outcome: TestOutcome) -> str | None:
    """Return the summary of the install step that stopped a suite run, or None."""
    if outcome.status != "error":
        return None
    _, found, step = outcome.detail.partition(f"; {INSTALL_FAILED}: ")
    return step if found else None
