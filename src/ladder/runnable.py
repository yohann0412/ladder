"""Classify whether a suite runs at the merge base: detect, install in up to two ways, run."""

import shutil
import time
from collections.abc import Callable
from pathlib import Path

from ladder.adapters.base import (
    INSTALL_CAP_S,
    TEST_CAP_S,
    Adapter,
    Site,
    Strategy,
    Unsupported,
)
from ladder.completion import mark_complete
from ladder.detect import detect
from ladder.layout import Layout
from ladder.procrun import Runner, StepResult
from ladder.reasons import AttemptTrace, unrunnable_reason
from ladder.runtime import BASE_LABEL, RuntimeDir, remove_tree, runtime_for
from ladder.schemas import Runnability, SetupAttempt, TestOutcome, UnrunnableReason
from ladder.testrun import run_suite
from ladder.trees import copy_dir, dir_commit, export_rev, find_workspace, workspace_repo

Exporter = Callable[[Path], None]
PASSING = ("passed", "flaky")
TAIL_LINES = 8


def classify_pair(layout: Layout, pair_id: str) -> Runnability:
    """Classify the suite at the base of a pair's workspace."""
    workspace = find_workspace(layout, pair_id)
    repo = workspace_repo(workspace)
    runtime = runtime_for(layout, pair_id)
    return classify(
        runtime, pair_id, workspace.source_base, lambda dest: export_rev(repo, "base", dest)
    )


def classify_dir(layout: Layout, source: Path, record_id: str) -> Runnability:
    """Classify the suite of a plain directory, recorded under its own id."""
    runtime = runtime_for(layout, record_id)
    return classify(runtime, record_id, dir_commit(source), lambda dest: copy_dir(source, dest))


def classify(runtime: RuntimeDir, record_id: str, commit: str, export: Exporter) -> Runnability:
    """Export the base tree, try the standard install and then one fallback, and classify.

    A runnable base tree is marked complete, together with the environment installed for it.
    """
    runtime.reset()
    tree = runtime.tree(BASE_LABEL)
    export(tree)
    found = detect(tree)
    if isinstance(found, Unsupported):
        return _unrunnable(record_id, commit, found=found, reason=found.reason, detail=found.detail)
    if shutil.which(found.toolchain) is None:
        detail = f"{found.toolchain} is not installed"
        return _unrunnable(
            record_id, commit, found=found, reason="missing_toolchain", detail=detail
        )
    attempts: list[SetupAttempt] = []
    traces: list[AttemptTrace] = []
    for number, strategy in enumerate(found.strategies(), start=1):
        if number > 1:
            remove_tree(tree)
            remove_tree(runtime.env(BASE_LABEL))
            export(tree)
        setup, trace = _attempt(runtime, found, strategy, number)
        attempts.append(setup)
        traces.append(trace)
        if trace.outcome is not None and trace.outcome.status in PASSING:
            mark_complete(tree)
            return _runnable(
                record_id,
                commit,
                adapter=found,
                strategy=strategy,
                attempts=attempts,
                outcome=trace.outcome,
            )
        if any(step.timed_out or step.disk_floor for step in trace.steps) or (
            trace.outcome is not None and trace.outcome.status == "capped"
        ):
            break
    reason, detail = unrunnable_reason(traces)
    base_outcome = next((trace.outcome for trace in traces if trace.outcome is not None), None)
    return _unrunnable(
        record_id,
        commit,
        found=found,
        reason=reason,
        detail=detail,
        attempts=attempts,
        outcome=base_outcome,
    )


def _attempt(
    runtime: RuntimeDir, adapter: Adapter, strategy: Strategy, number: int
) -> tuple[SetupAttempt, AttemptTrace]:
    label = f"{BASE_LABEL}-attempt-{number}"
    runner = Runner(runtime.logs(label), runtime.scratch())
    site = Site(runtime.tree(BASE_LABEL), runtime.env(BASE_LABEL))
    start = time.monotonic()
    steps = adapter.install(runner, site, strategy)
    failing = next((step for step in steps if not step.ok), None)
    outcome = None
    if failing is None:
        outcome = run_suite(runner, adapter, site, strategy, reports=runtime.reports(label))
    principal = failing or next((step for step in steps if step.name == "install"), steps[-1])
    setup = SetupAttempt(
        command=principal.argv,
        exit_code=principal.exit_code,
        duration_s=round(time.monotonic() - start, 1),
        detail=_attempt_detail(strategy, steps, failing, outcome),
    )
    return setup, AttemptTrace(steps, outcome)


def _attempt_detail(
    strategy: Strategy,
    steps: list[StepResult],
    failing: StepResult | None,
    outcome: TestOutcome | None,
) -> str:
    name = (
        strategy.name
        if strategy.modification is None
        else f"{strategy.name} ({strategy.modification})"
    )
    parts = [step.summary() for step in steps]
    if outcome is not None:
        parts.append(f"suite {outcome.status}: {outcome.detail}")
    if failing is not None:
        lines = [line for line in failing.output().strip().splitlines() if line.strip()]
        parts.append("output tail: " + " | ".join(lines[-TAIL_LINES:]))
    return f"{name}, install cap {INSTALL_CAP_S} s: " + "; ".join(parts)


def _runnable(
    record_id: str,
    commit: str,
    *,
    adapter: Adapter,
    strategy: Strategy,
    attempts: list[SetupAttempt],
    outcome: TestOutcome,
) -> Runnability:
    modifications = [strategy.modification] if strategy.modification else []
    return Runnability(
        pair_id=record_id,
        commit=commit,
        language=adapter.language,
        package_manager=adapter.package_manager,
        test_runner=adapter.test_runner,
        status="runnable_with_modifications" if modifications else "runnable",
        reason=None,
        reason_detail="",
        modifications=modifications,
        attempts=attempts,
        test_count=_total(outcome),
        base_outcome=outcome,
        timeout_s=TEST_CAP_S,
    )


def _unrunnable(
    record_id: str,
    commit: str,
    *,
    found: Adapter | Unsupported,
    reason: UnrunnableReason,
    detail: str,
    attempts: list[SetupAttempt] | None = None,
    outcome: TestOutcome | None = None,
) -> Runnability:
    return Runnability(
        pair_id=record_id,
        commit=commit,
        language=found.language,
        package_manager=found.package_manager,
        test_runner=found.test_runner,
        status="unrunnable",
        reason=reason,
        reason_detail=detail,
        modifications=[],
        attempts=attempts or [],
        test_count=_total(outcome) if outcome is not None else None,
        base_outcome=outcome,
        timeout_s=TEST_CAP_S,
    )


def _total(outcome: TestOutcome) -> int:
    return outcome.passed + outcome.failed + outcome.errors + outcome.skipped
