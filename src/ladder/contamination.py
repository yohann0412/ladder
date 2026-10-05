"""Decide whether a PR's head absorbed the other PR's merge, and rewind it to before that."""

from bisect import bisect_left
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ladder.gitgraph import ChainCommit, first_parents, is_ancestor
from ladder.mergecommits import TIME_TOLERANCE_S


@dataclass(frozen=True)
class Rewind:
    """Where a PR's replay starts: its replay head, the commits skipped, the absorption commit."""

    contaminated: bool
    replay_head: str | None
    rewound: int
    absorption: str | None


def uncontaminated(head: str) -> Rewind:
    """Return the rewind of a PR whose final head is its replay head."""
    return Rewind(contaminated=False, replay_head=head, rewound=0, absorption=None)


def markers(
    chain: Sequence[ChainCommit], merge_commit: str | None, merged_at: datetime
) -> list[str]:
    """Return the commits whose presence in a PR's history means it absorbed a merged PR F.

    They are F's located merge commit and the oldest commit, in chain order, of the default
    branch's first-parent chain whose committer time is at least T_F - 5 s. The chain is
    linear, so a head reaching any later such commit also reaches that one.
    """
    threshold = merged_at.timestamp() - TIME_TOLERANCE_S
    late = [commit.sha for commit in chain if commit.time >= threshold]
    located = [merge_commit] if merge_commit is not None else []
    return located + late[-1:]


def rewind(repo: Path, head: str, found: Sequence[str], main: Collection[str]) -> Rewind:
    """Walk a PR's first-parent chain back to its first commit that reaches no marker.

    A commit that reaches a marker makes every descendant reach it, so the contaminated
    commits are a prefix of the chain and a binary search finds the first clean one. A clean
    commit on the default branch's first-parent chain means the PR has no commit of its own
    from before the absorption (it was rebased): no replay head.
    """

    def clean(commit: str) -> bool:
        return not any(is_ancestor(repo, marker, commit) for marker in found)

    if clean(head):
        return uncontaminated(head)
    chain = first_parents(repo, head)
    index = bisect_left(chain, True, lo=1, key=clean)
    if index == len(chain) or chain[index] in main:
        return Rewind(contaminated=True, replay_head=None, rewound=index, absorption=None)
    return Rewind(
        contaminated=True, replay_head=chain[index], rewound=index, absorption=chain[index - 1]
    )
