"""The structural rungs: retry the merge with weave or mergiraf as git's driver for every path."""

import subprocess
from pathlib import Path
from typing import Literal

from ladder.completion import mark_complete
from ladder.drivers import driver_failures, install, locate
from ladder.filecheck import check_file
from ladder.gitio import GitError
from ladder.gitrung import git_record_name
from ladder.jsonio import read_optional, write_record
from ladder.layout import Layout
from ladder.mergework import RungError, fresh_copy, merge_b, unmerged_paths
from ladder.schemas import GitRungResult, StructuralResult, StructuralTool

MERGE_TIMEOUT_S = 1800

StructuralStatus = Literal["resolved", "conflicted", "error"]


def run_structural_rung(layout: Layout, pair_id: str, tool: StructuralTool) -> StructuralResult:
    """Merge b into a on a fresh replay workspace copy with the tool as git's merge driver."""
    git_rung = _conflicted_git_rung(layout, pair_id, tool)
    driver = locate(tool)
    copy = fresh_copy(layout.workspace_dir(pair_id, "replay"), layout.rung_dir(pair_id, tool))
    error = _merge_error(copy, install(copy, driver))
    remaining = unmerged_paths(copy)
    status: StructuralStatus = "conflicted" if remaining else "resolved"
    detail = f"unmerged paths left: {len(remaining)} of {len(git_rung.files)}"
    if error is not None:
        status, detail = "error", error
    result = StructuralResult(
        pair_id=pair_id,
        tool=tool,
        tool_version=driver.version,
        status=status,
        detail=detail,
        remaining_conflicted=remaining,
        files=[check_file(copy, file.path) for file in git_rung.files],
        output_dir=str(copy.resolve()),
    )
    mark_complete(copy)
    write_record(layout.result_file(pair_id, f"rung-{tool}"), result)
    return result


def _conflicted_git_rung(layout: Layout, pair_id: str, tool: StructuralTool) -> GitRungResult:
    record = layout.result_file(pair_id, git_record_name("replay"))
    git_rung = read_optional(record, GitRungResult)
    if git_rung is None:
        raise RungError(
            f"{pair_id}: no replay git rung record at {record}; "
            f"run `ladder rung git {pair_id}` first"
        )
    if git_rung.status != "conflicted":
        raise RungError(
            f"{pair_id}: the replay git rung is {git_rung.status}, not conflicted; "
            f"there is nothing for {tool} to resolve"
        )
    return git_rung


def _merge_error(copy: Path, failure_log: Path) -> str | None:
    try:
        merge_b(copy, timeout=MERGE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return f"git merge timed out after {MERGE_TIMEOUT_S} s"
    except GitError as error:
        return str(error)
    failures = driver_failures(failure_log)
    return "; ".join(failures) if failures else None
