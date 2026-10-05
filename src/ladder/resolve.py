"""Resolve each pair's commits: heads, merge bases, merge commits, contamination, truth commit."""

from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ladder.cache import ensure_clone, fetch_pr
from ladder.contamination import Rewind, markers, rewind, uncontaminated
from ladder.gitgraph import ChainCommit, chain_log, default_branch, merge_bases
from ladder.gitio import GitError
from ladder.layout import Layout
from ladder.mergecommits import MergeCommit, locate_merge
from ladder.schemas import (
    Pair,
    PairRefs,
    PairSet,
    PrRefs,
    PullRequest,
    ResolveStatus,
    Side,
    TruthLocator,
    TruthStatus,
)


@dataclass(frozen=True)
class Mainline:
    """The default branch: its name, its first-parent chain, and the commits on that chain."""

    branch: str
    chain: list[ChainCommit]
    shas: frozenset[str]


@dataclass(frozen=True)
class Resolved:
    """What resolving found for one PR of a pair."""

    head: str
    merge: MergeCommit | None
    rewind: Rewind


@dataclass(frozen=True)
class Truth:
    """The commit holding the human resolution of a pair, and how it was found."""

    commit: str | None
    method: TruthLocator | None
    status: TruthStatus


def resolve_pairs(
    layout: Layout,
    pairs: Sequence[Pair],
    *,
    jobs: int,
    refresh: bool,
    done: Callable[[str, PairRefs], None],
) -> None:
    """Resolve pairs in parallel, one worker per repository cache, reporting each pair."""
    groups: dict[Path, list[Pair]] = {}
    for pair in pairs:
        groups.setdefault(layout.cache_dir(pair.repo), []).append(pair)
    pool = ThreadPoolExecutor(max_workers=jobs)
    try:
        futures = [
            pool.submit(_resolve_repo, cache, group, refresh) for cache, group in groups.items()
        ]
        for future in as_completed(futures):
            for pair_id, refs in future.result():
                done(pair_id, refs)
    finally:
        pool.shutdown(cancel_futures=True)


def with_refs(pair_set: PairSet, refs: Mapping[str, PairRefs]) -> PairSet:
    """Return the pair set with the resolved refs filled in for the pairs that have them."""
    pairs = [
        pair.model_copy(update={"refs": refs[pair.pair_id]}) if pair.pair_id in refs else pair
        for pair in pair_set.pairs
    ]
    return pair_set.model_copy(update={"pairs": pairs})


def _resolve_repo(cache: Path, pairs: list[Pair], refresh: bool) -> list[tuple[str, PairRefs]]:
    try:
        ensure_clone(pairs[0].clone_url, cache, refresh=refresh)
        mainline = _mainline(cache)
    except GitError as error:
        failed = datetime.now(UTC)
        return [(pair.pair_id, _fetch_failed(pair, str(error), failed, None, {})) for pair in pairs]
    return [(pair.pair_id, _resolve_pair(cache, pair, mainline)) for pair in pairs]


def _mainline(cache: Path) -> Mainline:
    branch = default_branch(cache)
    chain = chain_log(cache, f"refs/heads/{branch}")
    return Mainline(branch, chain, frozenset(commit.sha for commit in chain))


def _resolve_pair(cache: Path, pair: Pair, mainline: Mainline) -> PairRefs:
    fetched_at = datetime.now(UTC)
    heads: dict[Side, str] = {}
    errors: list[str] = []
    for side, pr in _prs(pair):
        try:
            heads[side] = fetch_pr(cache, pr.number)
        except GitError as error:
            errors.append(f"#{pr.number}: {error}")
    if errors:
        return _fetch_failed(pair, "; ".join(errors), fetched_at, mainline.branch, heads)
    try:
        return _relate(cache, pair, mainline, heads, fetched_at)
    except GitError as error:
        return _fetch_failed(pair, str(error), fetched_at, mainline.branch, heads)


def _relate(
    cache: Path, pair: Pair, mainline: Mainline, heads: dict[Side, str], fetched_at: datetime
) -> PairRefs:
    merges = {side: _merge_commit(mainline, heads[side], pr) for side, pr in _prs(pair)}
    rewind_a = _rewind(cache, mainline, heads["a"], merges["b"], pair.b)
    rewind_b = _rewind(cache, mainline, heads["b"], merges["a"], pair.a)
    a = Resolved(heads["a"], merges["a"], rewind_a)
    b = Resolved(heads["b"], merges["b"], rewind_b)
    final_bases = merge_bases(cache, a.head, b.head)
    replay_bases = (
        merge_bases(cache, a.rewind.replay_head, b.rewind.replay_head)
        if a.rewind.replay_head is not None and b.rewind.replay_head is not None
        else []
    )
    status, detail = _status(a, b, final_bases, replay_bases)
    truth = _truth(pair, a, b)
    return PairRefs(
        status=status,
        detail=detail,
        fetched_at=fetched_at,
        default_branch=mainline.branch,
        final_merge_base=next(iter(final_bases), None),
        final_merge_base_count=len(final_bases),
        replay_merge_base=next(iter(replay_bases), None),
        replay_merge_base_count=len(replay_bases),
        a=_pr_refs(a),
        b=_pr_refs(b),
        truth_commit=truth.commit,
        truth_method=truth.method,
        truth_status=truth.status,
    )


def _merge_commit(mainline: Mainline, head: str, pr: PullRequest) -> MergeCommit | None:
    if pr.merged_at is None:
        return None
    return locate_merge(mainline.chain, head, pr.number, pr.merged_at)


def _rewind(
    cache: Path, mainline: Mainline, head: str, other_merge: MergeCommit | None, other: PullRequest
) -> Rewind:
    if other.merged_at is None:
        return uncontaminated(head)
    merge_sha = None if other_merge is None else other_merge.sha
    found = markers(mainline.chain, merge_sha, other.merged_at)
    return rewind(cache, head, found, mainline.shas)


def _status(
    a: Resolved, b: Resolved, final_bases: list[str], replay_bases: list[str]
) -> tuple[ResolveStatus, str]:
    rebased = [
        f"{side} rewound {pr.rewind.rewound} commits onto the default branch"
        for side, pr in (("a", a), ("b", b))
        if pr.rewind.replay_head is None
    ]
    if rebased:
        return "unrecoverable_rebased", "no PR commit before the absorption: " + "; ".join(rebased)
    if not final_bases:
        return "no_merge_base", "the final heads share no history"
    if not replay_bases:
        return "no_merge_base", "the replay heads share no history"
    return "ok", ""


def _truth(pair: Pair, a: Resolved, b: Resolved) -> Truth:
    if pair.a.merged_at is None or pair.b.merged_at is None:
        return Truth(None, None, "not_both_merged")
    later = a if pair.a.merged_at > pair.b.merged_at else b
    if later.rewind.absorption is not None:
        return Truth(later.rewind.absorption, "absorption", "located")
    if later.merge is not None:
        return Truth(later.merge.sha, later.merge.method, "located")
    return Truth(None, None, "unlocated")


def _pr_refs(resolved: Resolved) -> PrRefs:
    merge = resolved.merge
    return PrRefs(
        final_head=resolved.head,
        replay_head=resolved.rewind.replay_head,
        rewound_commits=resolved.rewind.rewound,
        contaminated=resolved.rewind.contaminated,
        merge_commit=None if merge is None else merge.sha,
        merge_commit_method=None if merge is None else merge.method,
        merge_time_delta_s=None if merge is None else merge.delta_s,
    )


def _fetch_failed(
    pair: Pair, detail: str, fetched_at: datetime, branch: str | None, heads: dict[Side, str]
) -> PairRefs:
    both_merged = pair.a.merged_at is not None and pair.b.merged_at is not None
    return PairRefs(
        status="fetch_failed",
        detail=detail,
        fetched_at=fetched_at,
        default_branch=branch,
        final_merge_base=None,
        final_merge_base_count=0,
        replay_merge_base=None,
        replay_merge_base_count=0,
        a=_unresolved(heads.get("a")),
        b=_unresolved(heads.get("b")),
        truth_commit=None,
        truth_method=None,
        truth_status="unlocated" if both_merged else "not_both_merged",
    )


def _unresolved(head: str | None) -> PrRefs:
    return PrRefs(
        final_head=head,
        replay_head=None,
        rewound_commits=0,
        contaminated=False,
        merge_commit=None,
        merge_commit_method=None,
        merge_time_delta_s=None,
    )


def _prs(pair: Pair) -> list[tuple[Side, PullRequest]]:
    return [("a", pair.a), ("b", pair.b)]
