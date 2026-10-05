"""Run a test suite under the cap, re-run a failing run once, and record a TestOutcome."""

from pathlib import Path

from ladder.adapters.base import TEST_CAP_S, Adapter, Site, Strategy, SuiteCommand
from ladder.diskfloor import stopped_below
from ladder.procrun import Runner
from ladder.schemas import TestOutcome, TestStatus

ERROR_TAIL_CHARS = 1500
RETRIED_STATUSES: tuple[TestStatus, ...] = ("failed", "error")


def not_run(detail: str) -> TestOutcome:
    """Return the outcome of a suite that was deliberately not run."""
    return outcome("not_run", [], detail)


def outcome(status: TestStatus, command: list[str], detail: str) -> TestOutcome:
    """Return an outcome with no test counts."""
    return TestOutcome(
        status=status,
        command=command,
        passed=0,
        failed=0,
        errors=0,
        skipped=0,
        duration_s=0.0,
        retried=False,
        failing_tests=[],
        detail=detail,
    )


def run_suite(
    runner: Runner,
    adapter: Adapter,
    site: Site,
    strategy: Strategy,
    *,
    reports: Path,
    only: list[str] | None = None,
) -> TestOutcome:
    """Run the suite or some test files; re-run a failing run once, and a pass then is flaky."""
    if only is not None and not only:
        return not_run("no test files selected")
    reports.mkdir(parents=True, exist_ok=True)

    def once(name: str) -> TestOutcome:
        report = reports / f"{name}.report"
        report.unlink(missing_ok=True)
        return _run_once(runner, adapter, site, adapter.suite(site, strategy, report, only), report)

    first = once("run-1")
    if first.status not in RETRIED_STATUSES:
        return first
    second = once("run-2")
    if second.status == "passed":
        detail = f"passed on the retry after: {first.detail}"
        return first.model_copy(update={"status": "flaky", "retried": True, "detail": detail})
    detail = f"{second.detail}; first run {first.status}: {_counts(first)}"
    return second.model_copy(update={"retried": True, "detail": detail})


def _run_once(
    runner: Runner, adapter: Adapter, site: Site, command: SuiteCommand, report: Path
) -> TestOutcome:
    step = runner.run(report.stem, command.argv, site.tree, cap=TEST_CAP_S, env=command.env)
    notes = [command.note] if command.note else []
    if step.missing:
        return outcome("error", command.argv, "; ".join([step.summary(), *notes]))
    if step.timed_out or step.disk_floor:
        detail = (
            f"suite exceeded the {TEST_CAP_S} s cap"
            if step.timed_out
            else f"suite {stopped_below(step.floor_gib)}"
        )
        capped = outcome("capped", command.argv, "; ".join([detail, *notes]))
        return capped.model_copy(update={"duration_s": round(step.duration_s, 1)})
    log_text = step.output()
    counts = adapter.parse(site, report, log_text)
    if counts is None:
        status: TestStatus = "error"
        problem = f"runner exited {step.exit_code} without a readable report"
    elif counts.failed + counts.errors:
        status, problem = "failed", ""
    elif counts.total == 0:
        status, problem = "error", "no tests ran"
    elif step.exit_code != 0:
        status, problem = "error", f"runner exited {step.exit_code} although no test failed"
    else:
        status, problem = "passed", ""
    if problem:
        notes = [problem, *notes, f"output tail: {log_text[-ERROR_TAIL_CHARS:].strip()}"]
    result = TestOutcome(
        status=status,
        command=command.argv,
        passed=counts.passed if counts else 0,
        failed=counts.failed if counts else 0,
        errors=counts.errors if counts else 0,
        skipped=counts.skipped if counts else 0,
        duration_s=round(step.duration_s, 1),
        retried=False,
        failing_tests=counts.failing if counts else [],
        detail="",
    )
    return result.model_copy(update={"detail": "; ".join([_counts(result), *notes])})


def _counts(result: TestOutcome) -> str:
    failing = f" ({', '.join(result.failing_tests[:5])})" if result.failing_tests else ""
    return (
        f"{result.passed} passed, {result.failed} failed, {result.errors} errors, "
        f"{result.skipped} skipped{failing}"
    )
