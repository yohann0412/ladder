"""Extract a conflicting pair's human resolution, only once all its resolver runs are settled."""

import hashlib
import shutil
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from ladder.blobs import ensure_files, read_blob, tree_entries, worktree_file
from ladder.completion import is_complete
from ladder.gitio import git_text, run_git
from ladder.jsonio import read_optional, write_record
from ladder.layout import Layout
from ladder.prepare import GIT_RUNG_DIR
from ladder.refusal import RefusedError
from ladder.regions import has_regions, keeps_context
from ladder.resolver_records import read_plan, run_label, unsettled_runs
from ladder.schemas import GitRungResult, Pair, PairRefs, TruthFile, TruthRecord, WorkspaceRecord

TRUTH = "truth"


def extract_truth(layout: Layout, pair: Pair) -> TruthRecord:
    """Write the truth record, and for a located truth its conflicted files; refuse too early.

    Refused for a clean pair, without a resolver plan, or while any planned run has
    neither a run record nor a task status that needs no run. Nothing is written then.
    """
    pair_id = pair.pair_id
    git = _conflicted_git(layout, pair_id)
    _refuse_unsettled(layout, pair_id)
    refs = pair.refs
    if refs is None:
        raise RefusedError(f"{pair_id} is not resolved; run `ladder pairs resolve`")
    if refs.truth_status != "located" or refs.truth_commit is None:
        record = _record(pair_id, refs, [], [], [], leak=False)
    else:
        record = _located(layout, pair, refs, refs.truth_commit, [f.path for f in git.files])
    write_record(layout.result_file(pair_id, TRUTH), record)
    return record


def audit_truth(layout: Layout) -> list[tuple[str, str]]:
    """Return every pair with a truth directory whose resolver runs are not all settled."""
    root = layout.work / TRUTH
    pair_ids = sorted(p.name for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    findings: list[tuple[str, str]] = []
    for pair_id in pair_ids:
        plan = read_plan(layout, pair_id)
        if plan is None:
            findings.append((pair_id, "no resolver plan"))
        elif unsettled := unsettled_runs(layout, plan):
            labels = ", ".join(run_label(run.rung, run.run) for run in unsettled)
            findings.append((pair_id, f"resolver runs not settled: {labels}"))
    return findings


def _conflicted_git(layout: Layout, pair_id: str) -> GitRungResult:
    git = read_optional(layout.result_file(pair_id, "rung-git"), GitRungResult)
    if git is None:
        raise RefusedError(f"no git rung result for {pair_id}; run `ladder rung git` first")
    if git.status == "clean":
        raise RefusedError(f"{pair_id}: clean pair, no truth needed")
    if git.status != "conflicted":
        raise RefusedError(f"{pair_id}: git rung status {git.status}, no truth extracted")
    return git


def _refuse_unsettled(layout: Layout, pair_id: str) -> None:
    plan = read_plan(layout, pair_id)
    if plan is None:
        raise RefusedError(f"{pair_id}: resolver plan missing; run `ladder resolve plan` first")
    unsettled = unsettled_runs(layout, plan)
    if unsettled:
        labels = ", ".join(run_label(run.rung, run.run) for run in unsettled)
        raise RefusedError(
            f"{pair_id}: resolver runs not settled ({labels}); finalize them before truth"
        )


def _located(
    layout: Layout, pair: Pair, refs: PairRefs, commit: str, conflicted: list[str]
) -> TruthRecord:
    pair_id = pair.pair_id
    rung_copy = layout.rung_dir(pair_id, GIT_RUNG_DIR)
    workspace = read_optional(layout.result_file(pair_id, "workspace-replay"), WorkspaceRecord)
    if workspace is None or not is_complete(rung_copy):
        raise RefusedError(
            f"{pair_id}: the replay workspace or the git rung's merge state is gone or incomplete"
        )
    cache = layout.cache_dir(pair.repo)
    changed = _changed(rung_copy, workspace) - set(conflicted)
    paths = [*conflicted, *sorted(changed)]
    ensure_files(cache, commit, paths)
    entries = tree_entries(cache, commit, paths)
    truth = {p: read_blob(cache, e.sha) for p, e in entries.items() if e.kind == "blob"}
    touched = [
        path
        for path in sorted(changed)
        if _lf(truth.get(path)) != _lf(worktree_file(rung_copy, path))
    ]
    outside = [
        path
        for path in conflicted
        if (marked := worktree_file(rung_copy, path)) is not None
        and has_regions(marked)
        and not keeps_context(marked, truth.get(path))
    ]
    truth_tree = _tree(cache, commit)
    heads = [head for head in (refs.a.replay_head, refs.b.replay_head) if head is not None]
    leak = any(_tree(cache, head) == truth_tree for head in heads)
    files = _write_files(layout.truth_dir(pair_id), conflicted, truth)
    return _record(pair_id, refs, files, touched, outside, leak=leak)


def _changed(repo: Path, workspace: WorkspaceRecord) -> set[str]:
    changed: set[str] = set()
    for head in (workspace.a_commit, workspace.b_commit):
        args = ["diff-tree", "-r", "-z", "--no-renames", "--name-only", workspace.base_commit, head]
        out = run_git(args, repo).stdout.decode("utf-8", "surrogateescape")
        changed.update(filter(None, out.split("\0")))
    return changed


def _tree(cache: Path, commit: str) -> str:
    return git_text(["rev-parse", f"{commit}^{{tree}}"], cache)


def _lf(data: bytes | None) -> bytes | None:
    return None if data is None else data.replace(b"\r\n", b"\n")


def _write_files(
    truth_dir: Path, conflicted: Sequence[str], truth: dict[str, bytes]
) -> list[TruthFile]:
    if truth_dir.exists():
        shutil.rmtree(truth_dir)
    truth_dir.mkdir(parents=True)
    files: list[TruthFile] = []
    for path in conflicted:
        content = truth.get(path)
        if content is None:
            files.append(TruthFile(path=path, present=False, sha256=None))
            continue
        target = truth_dir / "files" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        files.append(TruthFile(path=path, present=True, sha256=digest))
    return files


def _record(
    pair_id: str,
    refs: PairRefs,
    files: list[TruthFile],
    touched: list[str],
    outside: list[str],
    *,
    leak: bool,
) -> TruthRecord:
    return TruthRecord(
        pair_id=pair_id,
        status=refs.truth_status,
        commit=refs.truth_commit,
        method=refs.truth_method,
        files=files,
        touched_beyond_conflict=touched,
        outside_region_edit=outside,
        rewrite=bool(touched or outside),
        leak_head_equals_truth=leak,
        extracted_at=datetime.now(UTC),
    )
