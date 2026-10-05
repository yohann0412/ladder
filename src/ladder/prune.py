"""Delete a pair's working copies once `ladder run` is done with them; records always stay."""

from pathlib import Path

from ladder.completion import unmark, unmark_all
from ladder.jsonio import read_record
from ladder.layout import Layout
from ladder.resolver_records import TASK_RECORD, run_exists
from ladder.runtime import BASE_LABEL, RuntimeDir, remove_tree
from ladder.schemas import ResolverTask

SNAPSHOT_GLOB = "*/run-*/workspace"


def prune_pair(layout: Layout, pair_id: str) -> list[Path]:
    """Delete a pair's replay workspace, rung copies, runtime and settled task snapshots.

    Snapshots of tasks still waiting for their subagent are kept, and so are every task's
    PROMPT.md and files/, every result record, resolver output and truth file. Completion marks
    go first, so a prune cut short leaves no marked partial tree. Return the deleted paths.
    """
    waiting = _waiting_snapshots(layout, pair_id)
    snapshots = sorted((layout.work / "resolver" / pair_id).glob(SNAPSHOT_GLOB))
    workspace = layout.workspace_dir(pair_id, "replay")
    rungs = layout.rung_dir(pair_id, "git-replay").parent
    runtime = RuntimeDir(layout.runtime_dir(pair_id))
    unmark(workspace)
    unmark_all(rungs)
    unmark(runtime.tree(BASE_LABEL))
    candidates = [
        workspace,
        rungs,
        *(path for path in snapshots if path.resolve() not in waiting),
        runtime.root,
    ]
    deleted = [path for path in candidates if path.exists() or path.is_symlink()]
    for path in deleted:
        remove_tree(path)
    return deleted


def prune_cache(layout: Layout, repo: str) -> Path | None:
    """Delete a repository's cache; return it, or None when there was none."""
    cache = layout.cache_dir(repo)
    if not cache.exists():
        return None
    remove_tree(cache)
    return cache


def _waiting_snapshots(layout: Layout, pair_id: str) -> set[Path]:
    tasks = [
        read_record(path, ResolverTask)
        for path in sorted(layout.result_dir(pair_id).glob(TASK_RECORD))
    ]
    return {
        Path(task.snapshot_dir).resolve()
        for task in tasks
        if task.status == "pending" and not run_exists(layout, pair_id, task.rung, task.run)
    }
