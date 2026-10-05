"""Select the AIDev rows the paper's pairs need from revisions of the Hugging Face dataset."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from ladder.download import fetch_bytes
from ladder.extracts import AidevPr, AidevRepo, PrKey
from ladder.parquet import read_matching

DATASET = "hao-li/AIDev"
PRIMARY_REVISION = "main"
FALLBACK_REVISION = "v3"
PR_TABLE = "pull_request.parquet"
REPO_TABLE = "repository.parquet"
TABLES = (PR_TABLE, REPO_TABLE)


@dataclass(frozen=True)
class Revision:
    """A named dataset revision, the commit it resolved to, and where its tables were saved."""

    name: str
    sha: str
    tables: Path


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


def resolve_commit(name: str) -> str:
    """Return the commit a dataset branch or tag points to now."""
    url = f"https://huggingface.co/api/datasets/{DATASET}/revision/{name}"
    return _RevisionInfo.model_validate_json(fetch_bytes(url)).sha


def table_url(revision: Revision, table: str) -> str:
    """Return the download URL of one table, pinned to the revision's commit."""
    return f"https://huggingface.co/datasets/{DATASET}/resolve/{revision.sha}/{table}"


def select_repos(revision: Revision, names: set[str]) -> list[AidevRepo]:
    """Return the repository rows whose full name is in names."""
    rows = _repo_rows(revision, "full_name", names)
    return [_vendored_repo(row.full_name, row, revision) for row in rows]


def select_prs(revision: Revision, keys: set[PrKey]) -> list[AidevPr]:
    """Return the PR rows whose (repository full name, number) is in keys."""
    names = _repo_names(revision, "full_name", {repo for repo, _ in keys})
    rows = _pr_rows(revision, "repo_id", set(names))
    return [
        _vendored_pr((names[row.repo_id], row.number), names[row.repo_id], row, revision)
        for row in rows
        if (names[row.repo_id], row.number) in keys
    ]


def recover_repos(primary: Revision, fallback: Revision, names: set[str]) -> list[AidevRepo]:
    """Find repositories by name in fallback, then prefer primary's row with the same id."""
    old = select_repos(fallback, names)
    ids = {repo.id: repo.full_name for repo in old if repo.id is not None}
    rows = _repo_rows(primary, "id", set(ids))
    fresh = {ids[row.id]: _vendored_repo(ids[row.id], row, primary) for row in rows}
    return [fresh.get(repo.full_name, repo) for repo in old]


def recover_prs(primary: Revision, fallback: Revision, keys: set[PrKey]) -> list[AidevPr]:
    """Find PRs by (repository, number) in fallback, then prefer primary's row with the same id."""
    old = select_prs(fallback, keys)
    ids = {pr.id: pr.key for pr in old if pr.id is not None}
    rows = _pr_rows(primary, "id", set(ids))
    names = _repo_names(primary, "id", {row.repo_id for row in rows})
    fresh = {
        ids[row.id]: _vendored_pr(ids[row.id], names[row.repo_id], row, primary) for row in rows
    }
    return [fresh.get(pr.key, pr) for pr in old]


def _repo_rows(revision: Revision, column: str, values: set[str] | set[int]) -> list[_RepoRow]:
    columns = list(_RepoRow.model_fields)
    rows = read_matching(revision.tables / REPO_TABLE, columns, column, values)
    return [_RepoRow.model_validate(raw) for raw in rows]


def _repo_names(revision: Revision, column: str, values: set[str] | set[int]) -> dict[int, str]:
    return {row.id: row.full_name for row in _repo_rows(revision, column, values)}


def _pr_rows(revision: Revision, column: str, values: set[int]) -> list[_PrRow]:
    columns = list(_PrRow.model_fields)
    rows = read_matching(revision.tables / PR_TABLE, columns, column, values)
    return [_PrRow.model_validate(raw) for raw in rows]


def _vendored_repo(full_name: str, row: _RepoRow, revision: Revision) -> AidevRepo:
    return AidevRepo(
        full_name=full_name,
        full_name_now=row.full_name,
        id=row.id,
        stars=row.stars,
        forks=row.forks,
        language=row.language,
        license=row.license,
        revision=revision.name,
        revision_sha=revision.sha,
    )


def _vendored_pr(key: PrKey, repo_now: str, row: _PrRow, revision: Revision) -> AidevPr:
    return AidevPr(
        repo=key[0],
        repo_now=repo_now,
        number=key[1],
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
