"""Claim C: run the suite at A, at B and at their clean merge, and judge "fails together"."""

from ladder.jsonio import read_optional
from ladder.layout import Layout
from ladder.pairsuite import SuiteUnavailable, open_pair_suite
from ladder.schemas import ClaimCRecord, GitRungResult, Runnability, TestOutcome
from ladder.testrun import not_run, outcome
from ladder.trees import (
    MergeMismatch,
    changed_paths,
    export_merge,
    export_rev,
    find_workspace,
    workspace_repo,
)

SIDES = ("a", "b")
MERGE_LABEL = "merge"
UNRUNNABLE_PREFIX = "unrunnable: "
SUITE_ERROR_PREFIX = "error: "


class ClaimCError(RuntimeError):
    """A pair cannot enter Claim C: no clean git merge, or a missing prerequisite record."""


def run_claim_c(layout: Layout, pair_id: str) -> ClaimCRecord:
    """Run the suite at A, at B and at the clean merge of a runnable pair and judge the result."""
    rung = read_optional(layout.result_file(pair_id, "rung-git"), GitRungResult)
    if rung is None:
        raise ClaimCError(f"{pair_id} has no git rung record; run ladder rung git {pair_id}")
    if rung.status != "clean" or rung.merged_tree is None:
        raise ClaimCError(f"{pair_id} is {rung.status} under git; Claim C needs a clean merge")
    runnability = read_optional(layout.result_file(pair_id, "runnability"), Runnability)
    if runnability is None:
        raise ClaimCError(f"{pair_id} has no runnability record; run ladder runnable {pair_id}")
    workspace = find_workspace(layout, pair_id, rung.heads)
    repo = workspace_repo(workspace)
    files_a = changed_paths(repo, "base", "a")
    files_b = changed_paths(repo, "base", "b")

    def record(
        a: TestOutcome, b: TestOutcome, merge: TestOutcome, excluded: str | None = None
    ) -> ClaimCRecord:
        verdict, reason = judge(a, b, merge) if excluded is None else (None, excluded)
        return ClaimCRecord(
            pair_id=pair_id,
            a=a,
            b=b,
            merge=merge,
            fails_together=verdict,
            excluded_reason=reason,
            files_a=files_a,
            files_b=files_b,
        )

    if runnability.status == "unrunnable":
        skipped = not_run(f"repository unrunnable at base: {runnability.reason}")
        reason = f"{UNRUNNABLE_PREFIX}{runnability.reason} ({runnability.reason_detail})"
        return record(skipped, skipped, skipped, reason)
    try:
        suite = open_pair_suite(layout, runnability, workspace)
    except SuiteUnavailable as error:
        skipped = not_run(str(error))
        return record(skipped, skipped, skipped, f"{SUITE_ERROR_PREFIX}{error}")
    runtime = suite.runtime
    outcomes: list[TestOutcome] = []
    for side in SIDES:
        runtime.clear(side)
        export_rev(repo, side, runtime.tree(side))
        outcomes.append(suite.run(side, runtime.tree(side)))
    runtime.clear(MERGE_LABEL)
    try:
        export_merge(
            repo,
            rung.merged_tree,
            runtime.scratch_repo(),
            runtime.tree(MERGE_LABEL),
            holders=[layout.rung_dir(pair_id, f"git-{rung.heads}")],
        )
    except MergeMismatch as error:
        merge = outcome("error", [], str(error))
    else:
        merge = suite.run(MERGE_LABEL, runtime.tree(MERGE_LABEL))
    return record(outcomes[0], outcomes[1], merge)


def judge(a: TestOutcome, b: TestOutcome, merge: TestOutcome) -> tuple[bool | None, str | None]:
    """Return fails_together, or None with the reason the pair is excluded."""
    problems: list[str] = []
    for name, result in (("a", a), ("b", b), (MERGE_LABEL, merge)):
        if result.status in ("flaky", "capped"):
            problems.append(f"{result.status} at {name}")
        elif result.status in ("error", "not_run"):
            problems.append(f"{result.status} at {name}: {result.detail[:200]}")
    problems.extend(
        f"{name} fails alone" for name, result in (("a", a), ("b", b)) if result.status == "failed"
    )
    if problems:
        return None, "; ".join(problems)
    return merge.status == "failed", None
