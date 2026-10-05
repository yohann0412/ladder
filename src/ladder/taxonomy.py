"""Where conflicts come from: label transitions, file categories, agent pairs, resolve facts."""

from collections import Counter

from ladder.collect import PairRecords
from ladder.schemas import GitRungResult, Rate
from ladder.stats import share

ABSENT = "absent"


def _status(result: GitRungResult | None) -> str:
    return ABSENT if result is None else result.status


def transitions(pairs: list[PairRecords]) -> list[tuple[str, str, str, int]]:
    """Count pairs per (paper label, final-head git status, replay-head git status)."""
    counts = Counter(
        (
            ABSENT if pair.pair.paper is None else pair.pair.paper.label,
            _status(pair.git_final),
            _status(pair.git),
        )
        for pair in pairs
    )
    return [(*key, count) for key, count in sorted(counts.items())]


def files_by_category(pairs: list[PairRecords]) -> dict[str, int]:
    """Count conflicted files of ladder pairs by file category, most frequent first."""
    counts = Counter(
        file.category for pair in pairs if pair.git and pair.in_ladder for file in pair.git.files
    )
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def agent_pair_label(pair: PairRecords) -> str:
    """Return `agent A / agent B` for a pair."""
    return f"{pair.pair.a.agent} / {pair.pair.b.agent}"


def agent_pairs(pairs: list[PairRecords]) -> list[tuple[str, Rate]]:
    """Return per agent pair the share of replay-evaluable pairs that conflict, largest first."""
    evaluable = [pair for pair in pairs if pair.git is not None and pair.git.status != "error"]
    labels = sorted({agent_pair_label(pair) for pair in evaluable})
    rates = [
        (
            label,
            share(
                [pair for pair in evaluable if agent_pair_label(pair) == label],
                lambda pair: pair.in_ladder,
            ),
        )
        for label in labels
    ]
    return sorted(rates, key=lambda item: (-item[1].denominator, item[0]))


def resolve_facts(pairs: list[PairRecords]) -> list[tuple[str, int]]:
    """Return counts of contaminated, rewound and unrecoverable pairs and of truth states."""
    refs = [pair.pair.refs for pair in pairs if pair.pair.refs is not None]
    ladder = [pair for pair in pairs if pair.in_ladder]
    truth_commits = Counter(ref.truth_status for ref in refs)
    truth_records = Counter(ABSENT if pair.truth is None else pair.truth.status for pair in ladder)
    return [
        ("pairs with resolved refs", len(refs)),
        (
            "contaminated (either head)",
            sum(ref.a.contaminated or ref.b.contaminated for ref in refs),
        ),
        (
            "rewound (either head)",
            sum(ref.a.rewound_commits + ref.b.rewound_commits > 0 for ref in refs),
        ),
        ("unrecoverable: rebased", sum(ref.status == "unrecoverable_rebased" for ref in refs)),
        *((f"truth commit {status}", count) for status, count in sorted(truth_commits.items())),
        *(
            (f"ladder pairs with truth {status}", count)
            for status, count in sorted(truth_records.items())
        ),
    ]
