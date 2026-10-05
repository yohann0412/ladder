"""Commit, before any truth exists, to the resolver runs each conflicting pair gets."""

import random
from datetime import UTC, datetime

from ladder.jsonio import read_optional, write_record
from ladder.layout import Layout
from ladder.refusal import RefusedError
from ladder.resolver_records import PLAN, has_runs, read_plan
from ladder.schemas import (
    GitRungResult,
    Pair,
    PairSet,
    PlannedRun,
    ResolverPlan,
    StructuralResult,
)

CLEAN_REASON = "git merged cleanly"
TRAP_REASON = "trap scenario: the planted resolution is scored instead of a resolver run"
RAW_RUN = PlannedRun(rung="llm-raw", run=1)
POST_WEAVE_RUN = PlannedRun(rung="llm-post-weave", run=1)
DOUBLE_RUN = PlannedRun(rung="llm-raw", run=2)


def plan_pair(layout: Layout, pair: Pair, exclude_reason: str | None) -> ResolverPlan:
    """Write a pair's resolver plan; refuse once its truth or any of its runs exists.

    A pair gets no run when git merged it cleanly, when it is a trap scenario, or when an
    exclusion reason is given; otherwise llm-raw run 1, plus llm-post-weave run 1 when weave
    left it conflicted.
    """
    pair_id = pair.pair_id
    if layout.truth_dir(pair_id).exists():
        raise RefusedError(f"truth already exists for {pair_id}, so its resolver plan is fixed")
    if has_runs(layout, pair_id):
        raise RefusedError(f"{pair_id} already has resolver runs, so its resolver plan is fixed")
    git = read_optional(layout.result_file(pair_id, "rung-git"), GitRungResult)
    if git is None:
        raise RefusedError(f"no git rung result for {pair_id}; run `ladder rung git` first")
    if git.status == "error":
        raise RefusedError(f"the git rung failed for {pair_id}: {git.detail}")
    reason = _excluded_reason(git, pair, exclude_reason)
    runs = [] if reason is not None else [RAW_RUN, *_post_weave_runs(layout, pair_id)]
    plan = ResolverPlan(
        pair_id=pair_id, runs=runs, excluded_reason=reason, created_at=datetime.now(UTC)
    )
    write_record(layout.result_file(pair_id, PLAN), plan)
    return plan


def sample_double(layout: Layout, pair_set: PairSet, n: int, seed: int) -> tuple[list[str], int]:
    """Add a second llm-raw run to n pairs drawn with a fixed seed; return them and the pool size.

    The pool is every pair whose plan has llm-raw run 1, sorted by pair id; when it holds
    fewer than n pairs, all of them are drawn.
    """
    pool = sorted(
        pair.pair_id
        for pair in pair_set.pairs
        if (plan := read_plan(layout, pair.pair_id)) is not None and RAW_RUN in plan.runs
    )
    drawn = sorted(random.Random(seed).sample(pool, min(n, len(pool))))
    with_truth = [pair_id for pair_id in drawn if layout.truth_dir(pair_id).exists()]
    if with_truth:
        raise RefusedError(f"truth already exists for sampled pairs: {', '.join(with_truth)}")
    for pair_id in drawn:
        plan = read_plan(layout, pair_id)
        if plan is not None and DOUBLE_RUN not in plan.runs:
            doubled = plan.model_copy(update={"runs": [*plan.runs, DOUBLE_RUN]})
            write_record(layout.result_file(pair_id, PLAN), doubled)
    return drawn, len(pool)


def _excluded_reason(git: GitRungResult, pair: Pair, exclude_reason: str | None) -> str | None:
    if git.status == "clean":
        return CLEAN_REASON
    if pair.trap_dir is not None:
        return TRAP_REASON
    return exclude_reason


def _post_weave_runs(layout: Layout, pair_id: str) -> list[PlannedRun]:
    weave = read_optional(layout.result_file(pair_id, "rung-weave"), StructuralResult)
    if weave is None:
        raise RefusedError(
            f"no weave rung result for {pair_id}; run `ladder rung structural --tool weave` first"
        )
    return [POST_WEAVE_RUN] if weave.status == "conflicted" else []
