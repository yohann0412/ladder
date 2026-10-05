"""Name, find and settle the resolver records of a pair."""

import re

from ladder.jsonio import read_optional, read_record
from ladder.layout import Layout
from ladder.schemas import LlmRung, PlannedRun, ResolverPlan, ResolverTask

PLAN = "resolver-plan"
RUN_RECORD = re.compile(r"^resolver-(?:llm-raw|llm-post-weave)-run-\d+\.json$")
TASK_RECORD = "resolver-*-run-*-task.json"
SETTLED_TASK_STATUSES = frozenset({"input_cap", "identical_input"})


def task_name(rung: LlmRung, run: int) -> str:
    """Return the result name of a prepared resolver task."""
    return f"resolver-{rung}-run-{run}-task"


def run_name(rung: LlmRung, run: int) -> str:
    """Return the result name of a finalized resolver run."""
    return f"resolver-{rung}-run-{run}"


def run_label(rung: LlmRung, run: int) -> str:
    """Return how a run is named in messages, such as `llm-raw run 1`."""
    return f"{rung} run {run}"


def read_plan(layout: Layout, pair_id: str) -> ResolverPlan | None:
    """Return a pair's resolver plan, or None when it has none."""
    return read_optional(layout.result_file(pair_id, PLAN), ResolverPlan)


def read_task(layout: Layout, pair_id: str, rung: LlmRung, run: int) -> ResolverTask | None:
    """Return a prepared resolver task, or None when it was never prepared."""
    return read_optional(layout.result_file(pair_id, task_name(rung, run)), ResolverTask)


def run_exists(layout: Layout, pair_id: str, rung: LlmRung, run: int) -> bool:
    """Return whether a resolver run has a ResolverRun record."""
    return layout.result_file(pair_id, run_name(rung, run)).exists()


def has_runs(layout: Layout, pair_id: str) -> bool:
    """Return whether any ResolverRun record exists for a pair."""
    directory = layout.result_dir(pair_id)
    return directory.is_dir() and any(RUN_RECORD.match(p.name) for p in directory.iterdir())


def unsettled_runs(layout: Layout, plan: ResolverPlan) -> list[PlannedRun]:
    """Return the planned runs that have neither a run record nor a task that needs no run."""
    unsettled: list[PlannedRun] = []
    for planned in plan.runs:
        if run_exists(layout, plan.pair_id, planned.rung, planned.run):
            continue
        task = read_task(layout, plan.pair_id, planned.rung, planned.run)
        if task is None or task.status not in SETTLED_TASK_STATUSES:
            unsettled.append(planned)
    return unsettled


def pending_tasks(layout: Layout) -> list[ResolverTask]:
    """Return every prepared task still waiting for its subagent run, by pair, rung and run."""
    root = layout.results / "pairs"
    files = sorted(root.glob(f"*/{TASK_RECORD}")) if root.is_dir() else []
    tasks = [read_record(path, ResolverTask) for path in files]
    waiting = [
        task
        for task in tasks
        if task.status == "pending" and not run_exists(layout, task.pair_id, task.rung, task.run)
    ]
    return sorted(waiting, key=lambda task: (task.pair_id, task.rung, task.run))
