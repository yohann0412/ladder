"""Sensitivity cuts, per-category rates and the runnable subset against the ladder set."""

from collections import Counter

from ladder.categories import categorize
from ladder.collect import PairRecords
from ladder.ladder_metrics import (
    applicable,
    oracle_human_equivalent,
    practical_human_equivalent,
    rung_row,
)
from ladder.schemas import FileScore, Rate, RungScore
from ladder.stats import share

CATEGORIES = ("source", "config_ci", "manifest_lockfile", "docs_text", "other")
FILE_COUNT_BUCKETS = ("1", "2-5", "6 or more")
UNKNOWN_LANGUAGE = "unknown"


def rewrite_truth(pair: PairRecords) -> bool:
    """Return whether the pair's human resolution is a rewrite."""
    return pair.truth is not None and pair.truth.rewrite


def pr_text_flagged(pair: PairRecords) -> bool:
    """Return whether any resolver task of the pair flagged its PR text."""
    return any(task.pr_text_flags for task in pair.tasks.values())


def sensitivity(pairs: list[PairRecords], rungs: list[str]) -> list[tuple[str, list[Rate]]]:
    """Return human-equivalent rates: all pairs, without rewrite truth, without flagged PR text."""
    cuts = [
        pairs,
        [pair for pair in pairs if not rewrite_truth(pair)],
        [pair for pair in pairs if not pr_text_flagged(pair)],
    ]
    rows = [(rung, [rung_row(rung, cut).human_equivalent for cut in cuts]) for rung in rungs]
    rows.append(("practical ladder", [practical_human_equivalent(cut) for cut in cuts]))
    rows.append(("oracle ladder", [oracle_human_equivalent(cut) for cut in cuts]))
    return rows


def _scored_files(
    pairs: list[PairRecords], rung: str, *, located_only: bool
) -> list[tuple[FileScore, RungScore]]:
    return [
        (file, score)
        for pair in applicable(rung, pairs)
        if pair.truth_located or not located_only
        for score in [pair.score(rung)]
        if score is not None and score.available
        for file in score.files
    ]


def human_equivalent_by_category(pairs: list[PairRecords], rung: str) -> dict[str, Rate]:
    """Return per file category the share of scored files equivalent to the human resolution."""
    files = _scored_files(pairs, rung, located_only=True)
    return {
        category: share(
            [file for file, _ in files if categorize(file.path) == category],
            lambda file: file.human_equivalent is True,
        )
        for category in CATEGORIES
    }


def intent_dropped_by_category(pairs: list[PairRecords], rung: str) -> dict[str, Rate]:
    """Return per file category the share of scored files on which a PR's intent was dropped."""
    files = _scored_files(pairs, rung, located_only=False)
    return {
        category: share(
            [(file, score) for file, score in files if categorize(file.path) == category],
            lambda item: any(drop.path == item[0].path for drop in item[1].intent_drops),
        )
        for category in CATEGORIES
    }


def _bucket(count: int) -> str:
    if count <= 1:
        return FILE_COUNT_BUCKETS[0]
    return FILE_COUNT_BUCKETS[1] if count <= 5 else FILE_COUNT_BUCKETS[2]


def _profile(pairs: list[PairRecords]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for pair in pairs:
        language = None if pair.runnability is None else pair.runnability.language
        counts[f"language: {language or UNKNOWN_LANGUAGE}"] += 1
        counts[f"conflicted files: {_bucket(len(pair.conflicted_paths))}"] += 1
    return counts


def runnable(pair: PairRecords) -> bool:
    """Return whether the pair's test suite runs, with or without modifications."""
    return pair.runnability is not None and pair.runnability.status != "unrunnable"


def subset_profile(pairs: list[PairRecords]) -> list[tuple[str, int, int]]:
    """Return (characteristic, runnable ladder pairs, all ladder pairs) rows."""
    ladder = [pair for pair in pairs if pair.in_ladder]
    subset = [pair for pair in ladder if runnable(pair)]
    whole, part = _profile(ladder), _profile(subset)
    languages = sorted(key for key in whole if key.startswith("language: "))
    buckets = [f"conflicted files: {bucket}" for bucket in FILE_COUNT_BUCKETS]
    total = "conflicted files (total)"
    rows = [("pairs", len(subset), len(ladder))]
    rows += [(key, part[key], whole[key]) for key in [*languages, *buckets]]
    rows.append(
        (
            total,
            sum(len(pair.conflicted_paths) for pair in subset),
            sum(len(pair.conflicted_paths) for pair in ladder),
        )
    )
    return rows
