"""Fetch every pair source and write the vendored extracts that `pairs load` reads offline."""

from dataclasses import dataclass
from pathlib import Path

from ladder.aidev import (
    DATASET,
    FALLBACK_REVISIONS,
    TABLES,
    Revision,
    resolve_revision,
    select_prs,
    select_repos,
    table_url,
)
from ladder.attribution import render_sources_md
from ladder.download import download
from ladder.extracts import (
    AIDEV_PRS,
    AIDEV_REPOS,
    SOURCES_JSON,
    SOURCES_MD,
    AidevPr,
    AidevRepo,
    PrKey,
    missing_pr,
    missing_repo,
    write_rows,
)
from ladder.replaycsv import REPLAY_CSV, read_replay
from ladder.schemas import SourceFile
from ladder.zenodo import fetch_replication_package


@dataclass(frozen=True)
class FetchResult:
    """What fetch-sources downloaded and what it vendored."""

    files: list[SourceFile]
    revisions: list[Revision]
    prs: list[AidevPr]
    repos: list[AidevRepo]


def fetch_sources(out: Path, downloads: Path) -> FetchResult:
    """Download the replication package and the AIDev tables, then write the extracts into out."""
    files = [fetch_replication_package(downloads, out)]
    rows = read_replay(out / REPLAY_CSV)
    pr_keys = {key for row in rows for key in row.keys}
    repo_names = {row.repo for row in rows}
    prs: dict[PrKey, AidevPr] = {}
    repos: dict[str, AidevRepo] = {}
    revisions: list[Revision] = []
    for name in FALLBACK_REVISIONS:
        if pr_keys <= prs.keys() and repo_names <= repos.keys():
            break
        revision = resolve_revision(name)
        tables = downloads / "aidev" / revision.sha
        files += [_fetch_table(revision, table, tables) for table in TABLES]
        prs.update((pr.key, pr) for pr in select_prs(tables, revision, pr_keys - prs.keys()))
        new_repos = select_repos(tables, revision, repo_names - repos.keys())
        repos.update((repo.full_name, repo) for repo in new_repos)
        revisions.append(revision)
    prs.update((key, missing_pr(key)) for key in pr_keys - prs.keys())
    repos.update((name, missing_repo(name)) for name in repo_names - repos.keys())
    result = FetchResult(
        files=sorted(files, key=lambda file: file.name),
        revisions=revisions,
        prs=[prs[key] for key in sorted(prs)],
        repos=[repos[name] for name in sorted(repos)],
    )
    _write(out, result)
    return result


def _fetch_table(revision: Revision, table: str, tables: Path) -> SourceFile:
    url = table_url(revision, table)
    md5 = download(url, tables / table)
    return SourceFile(name=f"{DATASET}@{revision.name}/{table}", url=url, md5=md5)


def _write(out: Path, result: FetchResult) -> None:
    write_rows(out / AIDEV_PRS, result.prs)
    write_rows(out / AIDEV_REPOS, result.repos)
    write_rows(out / SOURCES_JSON, result.files)
    (out / SOURCES_MD).write_text(render_sources_md(result.files, result.revisions), "utf-8")
