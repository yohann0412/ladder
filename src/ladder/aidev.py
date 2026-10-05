"""Select the AIDev rows the paper's pairs need from one revision of the Hugging Face dataset."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from ladder.download import fetch_bytes
from ladder.extracts import AidevPr, AidevRepo, PrKey
from ladder.parquet import read_matching

DATASET = "hao-li/AIDev"
FALLBACK_REVISIONS = ("main", "v3")
PR_TABLE = "pull_request.parquet"
REPO_TABLE = "repository.parquet"
TABLES = (PR_TABLE, REPO_TABLE)


@dataclass(frozen=True)
class Revision:
    """A named dataset revision and the commit it resolved to."""

    name: str
    sha: str


class _RevisionInfo(BaseModel):
    sha: str


class _RepoRow(BaseModel):
    id: int
    full_name: str
    stars: int | None
    forks: int | None
    language: str | None
    license: str | None


class _PrRow(BaseModel):
    id: int
    number: int
    repo_id: int
    agent: str | None
    title: str | None
    body: str | None
    state: str | None
    created_at: datetime | None
    closed_at: datetime | None
    merged_at: datetime | None
    html_url: str | None


def resolve_revision(name: str) -> Revision:
    """Return the commit a dataset branch or tag points to now."""
    url = f"https://huggingface.co/api/datasets/{DATASET}/revision/{name}"
    return Revision(name=name, sha=_RevisionInfo.model_validate_json(fetch_bytes(url)).sha)


def table_url(revision: Revision, table: str) -> str:
    """Return the download URL of one table, pinned to the revision's commit."""
    return f"https://huggingface.co/datasets/{DATASET}/resolve/{revision.sha}/{table}"


def select_repos(tables: Path, revision: Revision, names: set[str]) -> list[AidevRepo]:
    """Return the repository rows of one revision whose full name is in names."""
    return [
        AidevRepo(
            full_name=row.full_name,
            stars=row.stars,
            forks=row.forks,
            language=row.language,
            license=row.license,
            revision=revision.name,
            revision_sha=revision.sha,
        )
        for row in _repo_rows(tables, names)
    ]


def select_prs(tables: Path, revision: Revision, keys: set[PrKey]) -> list[AidevPr]:
    """Return the PR rows of one revision whose (repository full name, number) is in keys."""
    names = {row.id: row.full_name for row in _repo_rows(tables, {repo for repo, _ in keys})}
    columns = list(_PrRow.model_fields)
    rows = read_matching(tables / PR_TABLE, columns, "repo_id", set(names))
    selected: list[AidevPr] = []
    for row in (_PrRow.model_validate(raw) for raw in rows):
        repo = names[row.repo_id]
        if (repo, row.number) in keys:
            selected.append(_vendored_pr(repo, row, revision))
    return selected


def _repo_rows(tables: Path, names: set[str]) -> list[_RepoRow]:
    columns = list(_RepoRow.model_fields)
    rows = read_matching(tables / REPO_TABLE, columns, "full_name", names)
    return [_RepoRow.model_validate(raw) for raw in rows]


def _vendored_pr(repo: str, row: _PrRow, revision: Revision) -> AidevPr:
    return AidevPr(
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
        revision=revision.name,
        revision_sha=revision.sha,
    )
