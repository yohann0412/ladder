"""Draw the supplementary pairs (DECISIONS.md D15) from the vendored candidates, offline."""

import random
from pathlib import Path

from ladder.extracts import (
    SOURCES_JSON,
    SUPPLEMENTARY_CANDIDATES,
    CandidatePr,
    SupplementaryCandidate,
    read_rows,
)
from ladder.pairload import build_pair_set
from ladder.schemas import Pair, PairSet, PullRequest, SourceFile


def sample_supplementary(source_dir: Path, seed: int) -> list[Pair]:
    """Return one pair per candidate repository: sorted by full name, then shuffled by seed."""
    candidates = read_rows(source_dir / SUPPLEMENTARY_CANDIDATES, SupplementaryCandidate)
    ordered = sorted(candidates, key=lambda candidate: candidate.repo)
    random.Random(seed).shuffle(ordered)
    return [_pair(candidate) for candidate in ordered]


def with_supplementary(existing: PairSet | None, pairs: list[Pair], source_dir: Path) -> PairSet:
    """Replace the supplementary pairs of existing with pairs, after the pairs of other origins.

    Without an existing pair set, a new one takes its sources from the vendored sources.json.
    """
    if existing is None:
        return build_pair_set(read_rows(source_dir / SOURCES_JSON, SourceFile), pairs)
    kept = [pair for pair in existing.pairs if pair.origin != "supplementary"]
    return build_pair_set(existing.sources, [*kept, *pairs])


def _pair(candidate: SupplementaryCandidate) -> Pair:
    a, b = candidate.a, candidate.b
    return Pair(
        pair_id=f"{candidate.repo.replace('/', '__')}__{a.number}-{b.number}",
        origin="supplementary",
        stratum=candidate.stratum,
        repo=candidate.repo,
        clone_url=f"https://github.com/{candidate.repo}.git",
        a=_pull_request(a),
        b=_pull_request(b),
        paper=None,
        refs=None,
    )


def _pull_request(pr: CandidatePr) -> PullRequest:
    return PullRequest(
        number=pr.number,
        agent=pr.agent,
        title=pr.title,
        body=pr.body,
        state=pr.state,
        created_at=pr.created_at,
        closed_at=pr.closed_at,
        merged_at=pr.merged_at,
    )
