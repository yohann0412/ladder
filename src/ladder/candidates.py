"""Derive the supplementary candidate pairs of DECISIONS.md D15 from one AIDev revision."""

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, TypeAdapter

from ladder.aidev import COMMIT_DETAILS_TABLE, PR_TABLE, Revision, repo_names_by_id
from ladder.extracts import AidevPr, CandidatePr, PrKey, SupplementaryCandidate
from ladder.parquet import read_all, read_distinct, read_matching
from ladder.replaycsv import ReplayRow


class _Interval(BaseModel):
    id: int
    number: int
    repo_id: int
    created_at: datetime | None
    merged_at: datetime | None


@dataclass(frozen=True)
class _Merged:
    id: int
    number: int
    created_at: datetime
    merged_at: datetime


class _MergedRow(BaseModel):
    id: int
    number: int
    agent: str
    title: str | None
    body: str | None
    state: str
    created_at: datetime
    closed_at: datetime | None
    merged_at: datetime
    html_url: str | None


@dataclass(frozen=True)
class PaperPairs:
    """The paper's pairs, as unordered PR ids and as (repository name, unordered numbers)."""

    ids: frozenset[frozenset[int]]
    names: frozenset[tuple[str, frozenset[int]]]


@dataclass(frozen=True)
class Candidates:
    """The first candidate pair of every repository that has one, and all candidates counted."""

    first: list[SupplementaryCandidate]
    pairs: int


def paper_pairs(rows: list[ReplayRow], prs: dict[PrKey, AidevPr]) -> PaperPairs:
    """Return the keys that identify the paper's pairs, under every name their repository had."""
    ids: set[frozenset[int]] = set()
    names: set[tuple[str, frozenset[int]]] = set()
    for row in rows:
        found = [prs[key] for key in row.keys if key in prs]
        numbers = frozenset({row.pr_a, row.pr_b})
        names.add((row.repo, numbers))
        names.update((pr.repo_now, numbers) for pr in found if pr.repo_now is not None)
        pr_ids = frozenset(pr.id for pr in found if pr.id is not None)
        if len(pr_ids) == 2:
            ids.add(pr_ids)
    return PaperPairs(ids=frozenset(ids), names=frozenset(names))


def find_candidates(revision: Revision, paper: PaperPairs) -> Candidates:
    """Apply D15 rules 1, 2 and 5: each repository's first candidate pair, PR A created first.

    A candidate is two merged PRs of one repository whose [created_at, merged_at] intervals
    overlap, whose changed-file sets intersect, and which are not a paper pair. Candidates are
    ordered by (later PR's created_at, smaller number, larger number).
    """
    merged = _merged_by_repo(revision)
    names = repo_names_by_id(revision, set(merged))
    files = _changed_files(revision, {pr.id for prs in merged.values() for pr in prs})
    chosen: list[tuple[str, _Merged, _Merged]] = []
    total = 0
    for repo_id, prs in merged.items():
        name = names[repo_id]
        found = [
            (a, b)
            for a, b in _overlapping(prs)
            if files.get(a.id, set()) & files.get(b.id, set()) and not _is_paper(paper, name, a, b)
        ]
        total += len(found)
        if found:
            a, b = min(found, key=_rank)
            chosen.append((name, a, b))
    rows = _merged_rows(revision, {pr.id for _, a, b in chosen for pr in (a, b)})
    first = [_candidate(name, rows[a.id], rows[b.id]) for name, a, b in chosen]
    return Candidates(first=sorted(first, key=lambda candidate: candidate.repo), pairs=total)


def _merged_by_repo(revision: Revision) -> dict[int, list[_Merged]]:
    raw = read_all(revision.tables / PR_TABLE, list(_Interval.model_fields))
    merged: dict[int, list[_Merged]] = defaultdict(list)
    for row in (_Interval.model_validate(item) for item in raw):
        if row.created_at is not None and row.merged_at is not None:
            merged[row.repo_id].append(
                _Merged(
                    id=row.id, number=row.number, created_at=row.created_at, merged_at=row.merged_at
                )
            )
    return merged


def _changed_files(revision: Revision, pr_ids: set[int]) -> dict[int, set[str]]:
    columns = read_distinct(revision.tables / COMMIT_DETAILS_TABLE, ["pr_id", "filename"])
    ids = TypeAdapter(list[int]).validate_python(columns["pr_id"])
    filenames = TypeAdapter(list[str | None]).validate_python(columns["filename"])
    files: dict[int, set[str]] = defaultdict(set)
    for pr_id, filename in zip(ids, filenames, strict=True):
        if pr_id in pr_ids and filename is not None:
            files[pr_id].add(filename)
    return files


def _overlapping(prs: list[_Merged]) -> Iterator[tuple[_Merged, _Merged]]:
    """Yield every pair whose intervals overlap, the PR created first (then lower number) first."""
    ordered = sorted(prs, key=lambda pr: (pr.created_at, pr.number))
    for index, first in enumerate(ordered):
        for second in ordered[index + 1 :]:
            if second.created_at > first.merged_at:
                break
            if max(first.created_at, second.created_at) <= min(first.merged_at, second.merged_at):
                yield first, second


def _is_paper(paper: PaperPairs, repo: str, a: _Merged, b: _Merged) -> bool:
    numbers = frozenset({a.number, b.number})
    return frozenset({a.id, b.id}) in paper.ids or (repo, numbers) in paper.names


def _rank(pair: tuple[_Merged, _Merged]) -> tuple[datetime, int, int]:
    a, b = pair
    later = max(a.created_at, b.created_at)
    return (later, min(a.number, b.number), max(a.number, b.number))


def _merged_rows(revision: Revision, ids: set[int]) -> dict[int, _MergedRow]:
    raw = read_matching(revision.tables / PR_TABLE, list(_MergedRow.model_fields), "id", ids)
    rows = (_MergedRow.model_validate(item) for item in raw)
    return {row.id: row for row in rows}


def _candidate(repo: str, a: _MergedRow, b: _MergedRow) -> SupplementaryCandidate:
    return SupplementaryCandidate(repo=repo, a=_candidate_pr(repo, a), b=_candidate_pr(repo, b))


def _candidate_pr(repo: str, row: _MergedRow) -> CandidatePr:
    return CandidatePr(
        repo=repo,
        number=row.number,
        id=row.id,
        agent=row.agent,
        title=row.title or "",
        body=row.body or "",
        state=row.state,
        created_at=row.created_at,
        closed_at=row.closed_at,
        merged_at=row.merged_at,
        html_url=row.html_url,
    )
