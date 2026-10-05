"""The vendored AIDev extracts: their schemas and their deterministic JSON files."""

import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from ladder.schemas import Record, Stratum

AIDEV_PRS = "aidev_prs.json"
AIDEV_REPOS = "aidev_repos.json"
SUPPLEMENTARY_CANDIDATES = "supplementary_candidates.json"
SOURCES_JSON = "sources.json"
SOURCES_MD = "SOURCES.md"

PrKey = tuple[str, int]


class AidevPr(Record):
    """One AIDev pull request a paper pair names; revision None means no revision had it.

    `repo` is the replay CSV's repository name (the lookup key); `repo_now` is the
    repository's full name in the revision the row came from, which differs after a rename.
    """

    repo: str
    repo_now: str | None
    number: int
    id: int | None
    agent: str | None
    title: str
    body: str
    state: str | None
    created_at: datetime | None
    closed_at: datetime | None
    merged_at: datetime | None
    html_url: str | None
    revision: str | None
    revision_sha: str | None

    @property
    def key(self) -> PrKey:
        """Return the (repository, number) pair that identifies this PR."""
        return (self.repo, self.number)


class AidevRepo(Record):
    """One AIDev repository a paper pair lives in; revision None means no revision had it.

    `full_name` is the replay CSV's name (the lookup key); `full_name_now` is the name in the
    revision the row came from, which differs after a rename.
    """

    full_name: str
    full_name_now: str | None
    id: int | None
    stars: int | None
    forks: int | None
    language: str | None
    license: str | None
    revision: str | None
    revision_sha: str | None


class CandidatePr(Record):
    """One merged AIDev pull request of a supplementary candidate pair."""

    repo: str
    number: int
    id: int
    agent: str
    title: str
    body: str
    state: str
    created_at: datetime
    closed_at: datetime | None
    merged_at: datetime
    html_url: str | None


class SupplementaryCandidate(Record):
    """The candidate pair DECISIONS.md D15 takes from one repository; PR A was created first."""

    repo: str
    a: CandidatePr
    b: CandidatePr

    @property
    def stratum(self) -> Stratum:
        """Return `same` when one agent opened both PRs, otherwise `cross`."""
        return "same" if self.a.agent == self.b.agent else "cross"


def missing_pr(key: PrKey) -> AidevPr:
    """Return the placeholder row of a PR that no dataset revision has."""
    return AidevPr(
        repo=key[0],
        repo_now=None,
        number=key[1],
        id=None,
        agent=None,
        title="",
        body="",
        state=None,
        created_at=None,
        closed_at=None,
        merged_at=None,
        html_url=None,
        revision=None,
        revision_sha=None,
    )


def missing_repo(full_name: str) -> AidevRepo:
    """Return the placeholder row of a repository that no dataset revision has."""
    return AidevRepo(
        full_name=full_name,
        full_name_now=None,
        id=None,
        stars=None,
        forks=None,
        language=None,
        license=None,
        revision=None,
        revision_sha=None,
    )


def write_rows(path: Path, rows: Sequence[BaseModel]) -> None:
    """Write records as one JSON list with sorted keys, keeping the given row order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [row.model_dump(mode="json") for row in rows]
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")


def read_rows[T: BaseModel](path: Path, model: type[T]) -> list[T]:
    """Read and validate a JSON list of records."""
    return TypeAdapter(list[model]).validate_json(path.read_text(encoding="utf-8"))
