"""Prepare one resolver run: guards, snapshot, per-file inputs, prompt, manifest and task record."""

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ladder.blobs import worktree_file
from ladder.completion import is_complete
from ladder.jsonio import read_optional, write_record
from ladder.layout import Layout
from ladder.manifest import manifest_path, take_manifest
from ladder.prompt import render_prompt, spawn_line, template_path, template_sha256
from ladder.prtext import pr_text_flags
from ladder.refusal import RefusedError
from ladder.resolver_records import run_exists, run_label, run_name, task_name
from ladder.schemas import (
    GitRungResult,
    LlmRung,
    Pair,
    PairSet,
    ResolverRun,
    ResolverTask,
    StructuralResult,
    TaskStatus,
    WorkspaceRecord,
)
from ladder.snapshot import post_weave_snapshot, raw_snapshot
from ladder.taskfiles import (
    FileVersions,
    cap_breaches,
    collect_versions,
    input_bytes,
    write_versions,
)
from ladder.workspace import Synthetic
from ladder.wsverify import Verification, verify_snapshot, verify_workspace

GIT_RUNG_DIR = "git-replay"
SNAPSHOT = "workspace"
REUSED_RUN = "llm-raw/run-1"


@dataclass(frozen=True)
class Inputs:
    """What a run's resolver is asked to merge: the paths and the rung state they come from."""

    git: GitRungResult
    weave: StructuralResult | None
    paths: list[str]
    merged: Path


def prepare_run(
    layout: Layout, pair_set: PairSet, pair: Pair, rung: LlmRung, run: int
) -> ResolverTask:
    """Prepare a resolver task, or record why it needs no subagent; refuse on any broken guard."""
    pair_id = pair.pair_id
    _refuse_truth(layout, pair_set, pair)
    output_dir = layout.resolution_dir(pair_id, rung, run).resolve()
    label = run_label(rung, run)
    if output_dir.exists():
        raise RefusedError(
            f"{pair_id} {label} already has output at {output_dir}; runs never repeat"
        )
    if run_exists(layout, pair_id, rung, run):
        raise RefusedError(f"{pair_id} {label} is already finalized; runs never repeat")
    inputs = _inputs(layout, pair_id, rung)
    workspace = _verified_workspace(layout, pair_id)
    commits = Synthetic(base=workspace.base_commit, a=workspace.a_commit, b=workspace.b_commit)
    task_file = layout.result_file(pair_id, task_name(rung, run))
    task_file.unlink(missing_ok=True)
    task_dir = layout.resolver_task_dir(pair_id, rung, run).resolve()
    snapshot = task_dir / SNAPSHOT
    files = collect_versions(Path(workspace.path), commits, inputs.merged, inputs.paths)
    status, reasons = _status(layout, pair_id, inputs, files)
    if task_dir.exists():
        shutil.rmtree(task_dir)
    task_dir.mkdir(parents=True)
    if status == "pending":
        _build_snapshot(rung, Path(workspace.path), inputs.merged, snapshot, commits)
        files = collect_versions(snapshot, commits, snapshot, inputs.paths)
    write_versions(task_dir, files)
    template = template_path()
    prompt = render_prompt(
        template.read_text(encoding="utf-8"),
        pair=pair,
        rung=rung,
        task_dir=task_dir,
        output_dir=output_dir,
        snapshot_dir=snapshot,
        files=[(path, _types(inputs.git, path)) for path in inputs.paths],
    )
    (task_dir / "PROMPT.md").write_text(prompt, encoding="utf-8")
    write_record(manifest_path(layout, pair_id, rung, run), take_manifest(task_dir))
    task = ResolverTask(
        pair_id=pair_id,
        rung=rung,
        run=run,
        task_dir=str(task_dir),
        snapshot_dir=str(snapshot),
        output_dir=str(output_dir),
        spawn_line=spawn_line(task_dir),
        files=inputs.paths,
        input_bytes=input_bytes(files),
        pr_text_flags=pr_text_flags(pair),
        template_sha256=template_sha256(template),
        status=status,
        identical_to=REUSED_RUN if status == "identical_input" else None,
        prepared_at=datetime.now(UTC),
    )
    write_record(task_file, task)
    if status == "input_cap":
        write_record(layout.result_file(pair_id, run_name(rung, run)), _capped(task, reasons))
    return task


def _refuse_truth(layout: Layout, pair_set: PairSet, pair: Pair) -> None:
    if layout.truth_dir(pair.pair_id).exists():
        raise RefusedError(f"truth exists for {pair.pair_id}; no resolver run may start after it")
    siblings = [
        other.pair_id
        for other in pair_set.pairs
        if other.repo == pair.repo
        and other.pair_id != pair.pair_id
        and layout.truth_dir(other.pair_id).exists()
    ]
    if siblings:
        raise RefusedError(
            f"truth exists for {', '.join(siblings)} in the same repository {pair.repo}; "
            f"no resolver run of {pair.pair_id} may start after it"
        )


def _inputs(layout: Layout, pair_id: str, rung: LlmRung) -> Inputs:
    git = read_optional(layout.result_file(pair_id, "rung-git"), GitRungResult)
    if git is None or git.status != "conflicted":
        state = "no git rung result" if git is None else f"git rung status {git.status}"
        raise RefusedError(f"{pair_id} has {state}; only conflicted pairs get resolver runs")
    git_dir = layout.rung_dir(pair_id, GIT_RUNG_DIR)
    if not is_complete(git_dir):
        raise RefusedError(f"the git rung's merge state is missing or incomplete at {git_dir}")
    if rung == "llm-raw":
        return Inputs(git, None, [file.path for file in git.files], git_dir)
    weave = read_optional(layout.result_file(pair_id, "rung-weave"), StructuralResult)
    if weave is None or weave.status != "conflicted":
        state = "no weave rung result" if weave is None else f"weave rung status {weave.status}"
        raise RefusedError(f"{pair_id} has {state}; llm-post-weave needs weave's conflicts")
    weave_dir = Path(weave.output_dir)
    if not is_complete(weave_dir):
        raise RefusedError(f"weave's merge state is missing or incomplete at {weave_dir}")
    order = [file.path for file in git.files]
    remaining = [path for path in order if path in weave.remaining_conflicted]
    remaining += [path for path in weave.remaining_conflicted if path not in order]
    return Inputs(git, weave, remaining, weave_dir)


def _verified_workspace(layout: Layout, pair_id: str) -> WorkspaceRecord:
    workspace = read_optional(layout.result_file(pair_id, "workspace-replay"), WorkspaceRecord)
    if workspace is None:
        raise RefusedError(f"no replay workspace for {pair_id}; run `ladder workspace build`")
    if not is_complete(Path(workspace.path)):
        raise RefusedError(
            f"the replay workspace of {pair_id} at {workspace.path} is missing or incomplete; "
            "run `ladder workspace build`"
        )
    commits = Synthetic(base=workspace.base_commit, a=workspace.a_commit, b=workspace.b_commit)
    verification = verify_workspace(Path(workspace.path), commits.refs())
    if not verification.passed:
        raise RefusedError(_failed("the canonical replay workspace", workspace.path, verification))
    return workspace


def _status(
    layout: Layout, pair_id: str, inputs: Inputs, files: list[FileVersions]
) -> tuple[TaskStatus, list[str]]:
    if inputs.weave is not None and _identical(layout, pair_id, inputs.git, inputs.weave):
        return "identical_input", []
    breaches = cap_breaches(files)
    return ("input_cap", breaches) if breaches else ("pending", [])


def _identical(layout: Layout, pair_id: str, git: GitRungResult, weave: StructuralResult) -> bool:
    paths = [file.path for file in git.files]
    if set(weave.remaining_conflicted) != set(paths):
        return False
    git_dir, weave_dir = layout.rung_dir(pair_id, GIT_RUNG_DIR), Path(weave.output_dir)
    return all(worktree_file(git_dir, path) == worktree_file(weave_dir, path) for path in paths)


def _build_snapshot(
    rung: LlmRung, workspace: Path, merged: Path, snapshot: Path, commits: Synthetic
) -> None:
    if rung == "llm-raw":
        raw_snapshot(workspace, snapshot)
    else:
        post_weave_snapshot(merged, snapshot)
    verification = verify_snapshot(snapshot, commits.refs())
    if not verification.passed:
        shutil.rmtree(snapshot.parent)
        raise RefusedError(_failed("the workspace snapshot", str(snapshot), verification))


def _failed(what: str, path: str, verification: Verification) -> str:
    failed = [f"{check.name}: {check.detail}" for check in verification.checks if not check.passed]
    return f"{what} at {path} failed verification: " + "; ".join(failed)


def _types(git: GitRungResult, path: str) -> list[str]:
    for file in git.files:
        if file.path == path:
            return file.types
    return []


def _capped(task: ResolverTask, reasons: list[str]) -> ResolverRun:
    return ResolverRun(
        pair_id=task.pair_id,
        rung=task.rung,
        run=task.run,
        status="failed",
        failure="input_cap",
        violations=reasons,
        duration_ms=None,
        tokens=None,
        tool_calls=0,
        files=[],
        finalized_at=datetime.now(UTC),
    )
