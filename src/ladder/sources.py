"""Fetch every pair source and write the vendored extracts that `pairs load` reads offline."""

from dataclasses import dataclass
from pathlib import Path

from ladder.aidev import (
    COMMIT_DETAILS_TABLE,
    DATASET,
    FALLBACK_REVISION,
    PRIMARY_REVISION,
    TABLES,
    Revision,
    recover_prs,
    recover_repos,
    resolve_commit,
    select_prs,
    select_repos,
    table_url,
)
from ladder.attribution import render_sources_md
from ladder.candidates import Candidates, find_candidates, paper_pairs
from ladder.download import download
from ladder.extracts import (
    AIDEV_PRS,
    AIDEV_REPOS,
    SOURCES_JSON,
    SOURCES_MD,
    SUPPLEMENTARY_CANDIDATES,
    AidevPr,
    AidevRepo,
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
    candidates: Candidates


def fetch_sources(out: Path, downloads: Path) -> FetchResult:
    """Download the replication package and the AIDev tables, then write the extracts into out.

    Rows come from the primary revision by name. A PR or repository it lacks under the
    replay CSV's name is looked up in the fallback revision to learn its id, and the primary
    revision's row with that id is used when there is one (the repository was renamed);
    otherwise the fallback row is kept. The supplementary candidates come from the primary
    revision alone.
    """
    files = [fetch_replication_package(downloads, out)]
    rows = read_replay(out / REPLAY_CSV)
    pr_keys = {key for row in rows for key in row.keys}
    repo_names = {row.repo for row in rows}
    primary, primary_files = _fetch_revision(
        PRIMARY_REVISION, downloads, (*TABLES, COMMIT_DETAILS_TABLE)
    )
    files += primary_files
    revisions = [primary]
    prs = {pr.key: pr for pr in select_prs(primary, pr_keys)}
    repos = {repo.full_name: repo for repo in select_repos(primary, repo_names)}
    if not (pr_keys <= prs.keys() and repo_names <= repos.keys()):
        fallback, fallback_files = _fetch_revision(FALLBACK_REVISION, downloads, TABLES)
        files += fallback_files
        revisions.append(fallback)
        recovered_prs = recover_prs(primary, fallback, pr_keys - prs.keys())
        recovered_repos = recover_repos(primary, fallback, repo_names - repos.keys())
        prs.update((pr.key, pr) for pr in recovered_prs)
        repos.update((repo.full_name, repo) for repo in recovered_repos)
    prs.update((key, missing_pr(key)) for key in pr_keys - prs.keys())
    repos.update((name, missing_repo(name)) for name in repo_names - repos.keys())
    result = FetchResult(
        files=sorted(files, key=lambda file: file.name),
        revisions=revisions,
        prs=[prs[key] for key in sorted(prs)],
        repos=[repos[name] for name in sorted(repos)],
        candidates=find_candidates(primary, paper_pairs(rows, prs)),
    )
    _write(out, result)
    return result


def _fetch_revision(
    name: str, downloads: Path, tables: tuple[str, ...]
) -> tuple[Revision, list[SourceFile]]:
    sha = resolve_commit(name)
    revision = Revision(name=name, sha=sha, tables=downloads / "aidev" / sha)
    files: list[SourceFile] = []
    for table in tables:
        url = table_url(revision, table)
        md5 = download(url, revision.tables / table)
        files.append(SourceFile(name=f"{DATASET}@{name}/{table}", url=url, md5=md5))
    return revision, files


def _write(out: Path, result: FetchResult) -> None:
    write_rows(out / AIDEV_PRS, result.prs)
    write_rows(out / AIDEV_REPOS, result.repos)
    write_rows(out / SUPPLEMENTARY_CANDIDATES, result.candidates.first)
    write_rows(out / SOURCES_JSON, result.files)
    (out / SOURCES_MD).write_text(render_sources_md(result.files, result.revisions), "utf-8")
