"""Render SOURCES.md: attribution and provenance of the vendored pair sources."""

from ladder.aidev import DATASET, FALLBACK_REVISION, PRIMARY_REVISION, Revision
from ladder.extracts import AIDEV_PRS, AIDEV_REPOS
from ladder.replaycsv import REPLAY_CSV
from ladder.schemas import SourceFile
from ladder.zenodo import PACKAGE_README, RECORD_ID

HEADER = f"""# Pair sources

Written by `ladder pairs fetch-sources`; `ladder pairs load --source <this directory>` reads
these files offline. Both upstream datasets are licensed CC-BY-4.0
(https://creativecommons.org/licenses/by/4.0/). What was changed is listed per dataset.

## Replay study replication package (Zenodo record {RECORD_ID})

- Paper: *Concurrent AI-Agent Pull Requests on GitHub: Prevalence, Composition, and Merge
  Conflict Rates*.
- Record: *Replication Package: AI Agent Pull Requests on GitHub*, by George (Harvard Medical
  School) and Arjun (MIT Computer Science and Artificial Intelligence Laboratory),
  https://doi.org/10.5281/zenodo.{RECORD_ID}.
- License: CC-BY-4.0.
- Vendored unchanged: `{REPLAY_CSV}`, and the package's `README.md` as
  `{PACKAGE_README}`.

## AIDev (`{DATASET}` on Hugging Face)

- Authors: Hao Li, Haoxiang Zhang and Ahmed E. Hassan.
- Papers: *The Rise of AI Teammates in Software Engineering (SE) 3.0: How Autonomous Coding
  Agents Are Reshaping Software Engineering* (arXiv:2507.15003); *AIDev: Studying AI Coding
  Agents on GitHub* (arXiv:2602.09185, MSR 2026). The pairs come from its AIDev-pop subset.
- License: CC-BY-4.0. Content that originates in GitHub repositories keeps the license of
  its repository.
- Changed: kept only the rows of the pull requests and repositories the replay CSV names and
  only the columns below; joined `repository.full_name` to each PR through
  `pull_request.repo_id`; wrote null titles and bodies as empty strings; added the columns
  `revision` and `revision_sha` naming the dataset revision a row came from. A PR or
  repository that no revision has is kept with `revision: null`, empty text and null values.
  - `{AIDEV_PRS}`: repo (the replay CSV's name), repo_now (the name in the row's revision),
    number, id, agent, title, body, state, created_at, closed_at, merged_at, html_url.
  - `{AIDEV_REPOS}`: full_name (the replay CSV's name), full_name_now (the name in the row's
    revision), id, stars, forks, language, license.
- Row selection: `{PRIMARY_REVISION}` by (repository name, PR number). What it lacks under the
  replay CSV's name is looked up in `{FALLBACK_REVISION}` to learn its id; the
  `{PRIMARY_REVISION}` row with that id is used when there is one (the repository was renamed),
  otherwise the `{FALLBACK_REVISION}` row.
"""


def render_sources_md(files: list[SourceFile], revisions: list[Revision]) -> str:
    """Return the attribution note naming every dataset revision, download URL and md5."""
    lines = [HEADER.rstrip("\n"), "- Revisions:"]
    lines += [f"  - `{revision.name}` = commit `{revision.sha}`" for revision in revisions]
    lines += ["", "## Downloaded files", "", "| name | md5 | url |", "| --- | --- | --- |"]
    lines += [f"| `{file.name}` | `{file.md5}` | {file.url} |" for file in files]
    return "\n".join(lines) + "\n"
