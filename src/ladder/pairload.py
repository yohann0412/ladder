"""Build a validated PairSet from the vendored paper sources or from a fixture build."""

from collections import Counter
from pathlib import Path

from ladder.extracts import AIDEV_PRS, SOURCES_JSON, AidevPr, PrKey, read_rows
from ladder.jsonio import read_record
from ladder.replaycsv import REPLAY_CSV, ReplayRow, read_replay
from ladder.schemas import (
    FixtureManifest,
    FixturePr,
    FixtureScenario,
    Pair,
    PairSet,
    PaperRecord,
    PullRequest,
    SourceFile,
)

FIXTURE_MANIFEST = "manifest.json"


class PairSourceError(RuntimeError):
    """The pair sources are inconsistent: an extract lacks a row, or two pairs share an id."""


def pairs_from_source(source_dir: Path) -> PairSet:
    """Join the replay CSV with the AIDev PR extract into one paper pair per CSV row."""
    prs = {pr.key: pr for pr in read_rows(source_dir / AIDEV_PRS, AidevPr)}
    pairs = [_paper_pair(row, prs) for row in read_replay(source_dir / REPLAY_CSV)]
    sources = read_rows(source_dir / SOURCES_JSON, SourceFile)
    return _pair_set(sources, pairs)


def pairs_from_fixture(fixture_dir: Path) -> PairSet:
    """Turn every scenario of a fixture build's manifest into a fixture pair."""
    manifest = read_record(fixture_dir / FIXTURE_MANIFEST, FixtureManifest)
    root = fixture_dir.resolve()
    pairs = [_fixture_pair(root, scenario) for scenario in manifest.scenarios]
    return _pair_set([], pairs)


def _pair_set(sources: list[SourceFile], pairs: list[Pair]) -> PairSet:
    counts = Counter(pair.pair_id for pair in pairs)
    duplicates = sorted(pair_id for pair_id, count in counts.items() if count > 1)
    if duplicates:
        raise PairSourceError(f"duplicate pair ids: {', '.join(duplicates)}")
    return PairSet(sources=sources, pairs=pairs)


def _paper_pair(row: ReplayRow, prs: dict[PrKey, AidevPr]) -> Pair:
    key_a, key_b = row.keys
    return Pair(
        pair_id=f"{row.repo.replace('/', '__')}__{row.pr_a}-{row.pr_b}",
        origin="paper",
        stratum=row.stratum,
        repo=row.repo,
        clone_url=f"https://github.com/{row.repo}.git",
        a=_paper_pr(_lookup(prs, key_a), row.agent_a),
        b=_paper_pr(_lookup(prs, key_b), row.agent_b),
        paper=PaperRecord(
            stratum=row.stratum,
            label=row.label,
            n_files=row.n_files,
            files=row.files,
            types=row.types,
        ),
        refs=None,
    )


def _lookup(prs: dict[PrKey, AidevPr], key: PrKey) -> AidevPr:
    if key not in prs:
        raise PairSourceError(f"{AIDEV_PRS} has no row for {key[0]}#{key[1]}")
    return prs[key]


def _paper_pr(pr: AidevPr, agent: str) -> PullRequest:
    return PullRequest(
        number=pr.number,
        agent=agent,
        title=pr.title,
        body=pr.body,
        state=pr.state,
        created_at=pr.created_at,
        closed_at=pr.closed_at,
        merged_at=pr.merged_at,
    )


def _fixture_pair(root: Path, scenario: FixtureScenario) -> Pair:
    return Pair(
        pair_id=scenario.pair_id,
        origin="fixture",
        stratum=scenario.stratum,
        repo=f"fixture/{scenario.pair_id}",
        clone_url=f"file://{root}/{scenario.origin}",
        a=_fixture_pr(scenario.a),
        b=_fixture_pr(scenario.b),
        paper=None,
        refs=None,
    )


def _fixture_pr(pr: FixturePr) -> PullRequest:
    closed = pr.closed_at is not None or pr.merged_at is not None
    return PullRequest(
        number=pr.number,
        agent=pr.agent,
        title=pr.title,
        body=pr.body,
        state="closed" if closed else "open",
        created_at=pr.created_at,
        closed_at=pr.closed_at,
        merged_at=pr.merged_at,
    )
