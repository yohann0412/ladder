"""The git rung: merge b into a with git's ort strategy and record the conflict taxonomy."""

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from ladder.categories import categorize
from ladder.conflicts import conflict_messages, conflict_type, types_for_path
from ladder.gitio import GitError, run_git
from ladder.jsonio import read_optional, write_record
from ladder.layout import Layout
from ladder.markers import conflict_regions
from ladder.mergework import RungError, fresh_copy, merge_b, unmerged_paths
from ladder.schemas import ConflictedFile, GitRungResult, HeadsKind, WorkspaceRecord

GitStatus = Literal["clean", "conflicted", "error"]
MERGE_TREE = ("merge-tree", "--write-tree", "--messages", "--name-only", "a", "b")


def git_record_name(heads: HeadsKind) -> str:
    """Return the name of the git rung's result record at the given heads."""
    return "rung-git" if heads == "replay" else "rung-git-final"


def run_git_rung(layout: Layout, pair_id: str, heads: HeadsKind) -> GitRungResult:
    """Merge b into a in a fresh copy of the pair's workspace; record and return the outcome."""
    record = layout.result_file(pair_id, f"workspace-{heads}")
    if read_optional(record, WorkspaceRecord) is None:
        raise RungError(
            f"{pair_id}: no {heads} workspace record at {record}; "
            f"run `ladder workspace build {pair_id} --heads {heads}` first"
        )
    copy = fresh_copy(
        layout.workspace_dir(pair_id, heads), layout.rung_dir(pair_id, f"git-{heads}")
    )
    try:
        result = _merge(copy, pair_id, heads)
    except GitError as error:
        result = git_result(pair_id, heads, "error", str(error))
    write_record(layout.result_file(pair_id, git_record_name(heads)), result)
    return result


def _merge(copy: Path, pair_id: str, heads: HeadsKind) -> GitRungResult:
    tree = run_git(MERGE_TREE, copy, ok_codes=(0, 1))
    output = tree.stdout.decode("utf-8", "replace")
    messages = conflict_messages(output)
    tree_clean = tree.returncode == 0
    merge_clean = merge_b(copy).returncode == 0
    if merge_clean != tree_clean:
        detail = f"git merge-tree is {_word(tree_clean)} but git merge is {_word(merge_clean)}"
        return git_result(pair_id, heads, "error", detail, messages=messages)
    if tree_clean:
        merged_tree = output.splitlines()[0].strip()
        return git_result(
            pair_id, heads, "clean", "b merges into a cleanly", merged_tree=merged_tree
        )
    files = [_conflicted_file(copy, path, messages) for path in unmerged_paths(copy)]
    detail = f"conflict messages: {len(messages)}, conflicted files: {len(files)}"
    return git_result(pair_id, heads, "conflicted", detail, messages=messages, files=files)


def _conflicted_file(copy: Path, path: str, messages: list[str]) -> ConflictedFile:
    file = copy / path
    return ConflictedFile(
        path=path,
        types=types_for_path(path, messages),
        regions=conflict_regions(file.read_bytes()) if file.is_file() else 0,
        category=categorize(path),
    )


def git_result(
    pair_id: str,
    heads: HeadsKind,
    status: GitStatus,
    detail: str,
    *,
    messages: Sequence[str] = (),
    files: Sequence[ConflictedFile] = (),
    merged_tree: str | None = None,
) -> GitRungResult:
    """Return a git rung record with one conflict type per message."""
    return GitRungResult(
        pair_id=pair_id,
        heads=heads,
        status=status,
        detail=detail,
        messages=list(messages),
        types=[conflict_type(message) for message in messages],
        files=list(files),
        merged_tree=merged_tree,
    )


def _word(clean: bool) -> str:
    return "clean" if clean else "conflicted"
