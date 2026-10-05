"""Summarise the paper's pairs: conflict rates, agent pairs, conflict types, merge state."""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from ladder.extracts import AidevPr, PrKey
from ladder.schemas import Pair, PairSet, PaperRecord

EVALUABLE_LABELS = frozenset({"CLEAN", "CONFLICT"})
POOLED = "pooled"


@dataclass(frozen=True)
class ConflictRate:
    """Conflicting pairs among evaluable pairs of one group, and the group's unavailable pairs."""

    group: tuple[str, ...]
    conflicts: int
    evaluable: int
    unavailable: dict[str, int]

    @property
    def ratio(self) -> str:
        """Return `conflicts/evaluable`."""
        return f"{self.conflicts}/{self.evaluable}"

    @property
    def percent(self) -> float | None:
        """Return the conflict rate in percent, or None when nothing was evaluable."""
        return 100 * self.conflicts / self.evaluable if self.evaluable else None


@dataclass(frozen=True)
class PairSummary:
    """The headline numbers of a paper pair set."""

    pairs: int
    strata: list[ConflictRate]
    agent_pairs: list[ConflictRate]
    types: list[tuple[str, int]]
    conflicted_files: int
    both_merged: int
    both_merged_conflict: int
    conflict_pairs: int
    pr_revisions: dict[str | None, int]


def summarise(pair_set: PairSet, prs: list[AidevPr]) -> PairSummary:
    """Return the per-stratum, per-agent-pair, per-type and merge-state counts of paper pairs."""
    pairs = [(pair, pair.paper) for pair in pair_set.pairs if pair.paper is not None]
    by_stratum = _rates(pairs, lambda pair: (pair.stratum,))
    pooled = _rates(pairs, lambda _: (POOLED,))
    agent_pairs = _rates(pairs, lambda pair: (pair.a.agent, pair.b.agent))
    conflicts = [(pair, paper) for pair, paper in pairs if paper.label == "CONFLICT"]
    types = Counter(kind for _, paper in conflicts for kind in paper.types)
    by_key = {pr.key: pr for pr in prs}
    keys = {key for pair, _ in pairs for key in _keys(pair)}
    return PairSummary(
        pairs=len(pairs),
        strata=sorted(by_stratum, key=lambda rate: rate.group != ("same",)) + pooled,
        agent_pairs=sorted(agent_pairs, key=lambda rate: (-rate.evaluable, rate.group)),
        types=types.most_common(),
        conflicted_files=sum(len(paper.files) for _, paper in pairs),
        both_merged=sum(_both_merged(pair) for pair, _ in pairs),
        both_merged_conflict=sum(_both_merged(pair) for pair, _ in conflicts),
        conflict_pairs=len(conflicts),
        pr_revisions=dict(Counter(by_key[key].revision for key in keys)),
    )


def _rates(
    pairs: list[tuple[Pair, PaperRecord]], group_of: Callable[[Pair], tuple[str, ...]]
) -> list[ConflictRate]:
    labels: dict[tuple[str, ...], Counter[str]] = {}
    for pair, paper in pairs:
        labels.setdefault(group_of(pair), Counter())[paper.label] += 1
    return [
        ConflictRate(
            group=group,
            conflicts=counts["CONFLICT"],
            evaluable=sum(counts[label] for label in EVALUABLE_LABELS),
            unavailable={
                label: count
                for label, count in sorted(counts.items())
                if label not in EVALUABLE_LABELS
            },
        )
        for group, counts in labels.items()
    ]


def _keys(pair: Pair) -> tuple[PrKey, PrKey]:
    return ((pair.repo, pair.a.number), (pair.repo, pair.b.number))


def _both_merged(pair: Pair) -> bool:
    return pair.a.merged_at is not None and pair.b.merged_at is not None
