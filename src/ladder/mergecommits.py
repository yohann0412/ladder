"""Locate a merged PR's merge commit on the default branch's first-parent chain."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from ladder.gitgraph import ChainCommit
from ladder.schemas import MergeLocator

TIME_TOLERANCE_S = 5


@dataclass(frozen=True)
class MergeCommit:
    """A located merge commit, how it was found, and its distance from merged_at."""

    sha: str
    method: MergeLocator
    delta_s: float


def locate_merge(
    chain: Sequence[ChainCommit], head: str, number: int, merged_at: datetime
) -> MergeCommit | None:
    """Find a PR's merge commit: by parent, else by subject and time, else by a unique time."""
    merged = merged_at.timestamp()

    def delta(commit: ChainCommit) -> float:
        return abs(commit.time - merged)

    by_parent = [commit for commit in chain if head in commit.parents]
    if by_parent:
        best = min(by_parent, key=delta)
        return MergeCommit(best.sha, "merge_parent", delta(best))
    near = [commit for commit in chain if delta(commit) <= TIME_TOLERANCE_S]
    mention = re.compile(rf"#{number}(?!\d)")
    by_subject = [commit for commit in near if mention.search(commit.subject)]
    if by_subject:
        best = min(by_subject, key=delta)
        return MergeCommit(best.sha, "subject_time", delta(best))
    if len(near) == 1:
        return MergeCommit(near[0].sha, "time_only", delta(near[0]))
    return None
