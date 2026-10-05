# Pair sources

Written by `ladder pairs fetch-sources`; `ladder pairs load --source <this directory>` and
`ladder pairs sample-supplementary --source <this directory>` read these files offline. Both
upstream datasets are licensed CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/). What
was changed is listed per dataset.

## Replay study replication package (Zenodo record 21186464)

- Paper: *Concurrent AI-Agent Pull Requests on GitHub: Prevalence, Composition, and Merge
  Conflict Rates*.
- Record: *Replication Package: AI Agent Pull Requests on GitHub*, by George (Harvard Medical
  School) and Arjun (MIT Computer Science and Artificial Intelligence Laboratory),
  https://doi.org/10.5281/zenodo.21186464.
- License: CC-BY-4.0.
- Vendored unchanged: `rq3_merge_replay_full.csv`, and the package's `README.md` as
  `replication_README.md`.

## AIDev (`hao-li/AIDev` on Hugging Face)

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
  - `aidev_prs.json`: repo (the replay CSV's name), repo_now (the name in the row's revision),
    number, id, agent, title, body, state, created_at, closed_at, merged_at, html_url.
  - `aidev_repos.json`: full_name (the replay CSV's name), full_name_now (the name in the row's
    revision), id, stars, forks, language, license.
- Row selection: `main` by (repository name, PR number). What it lacks under the
  replay CSV's name is looked up in `v3` to learn its id; the
  `main` row with that id is used when there is one (the repository was renamed),
  otherwise the `v3` row.
- `supplementary_candidates.json` (DECISIONS.md D15, rules 1, 2 and 5): derived from the
  `main` revision's `pull_request.parquet`, `repository.parquet` and `pr_commit_details.parquet`
  (only its `pr_id` and `filename` columns). A candidate is two PRs of one repository, both
  with `merged_at`, whose [created_at, merged_at] intervals overlap, whose changed-file sets
  (union of `filename` over the PR's rows) intersect, and which are not a pair of the replay
  CSV. Per repository only the first candidate by (later PR's created_at, smaller number,
  larger number) is kept. One entry per repository, sorted by full name: repo (the full name
  in `main`), PR a (created first) and PR b, each with repo, number, id, agent,
  title, body, state, created_at, closed_at, merged_at, html_url; null titles and bodies are
  written as empty strings.
- Revisions:
  - `main` = commit `c63c8a57a2de34fc03fa83722412824af4d8753b`
  - `v3` = commit `68ed5f4b80d27a9e057fc57567f38bd322ac73ec`

## Downloaded files

| name | md5 | url |
| --- | --- | --- |
| `hao-li/AIDev@main/pr_commit_details.parquet` | `a73d2b8d180ce6a20b7db0b48167cb3c` | https://huggingface.co/datasets/hao-li/AIDev/resolve/c63c8a57a2de34fc03fa83722412824af4d8753b/pr_commit_details.parquet |
| `hao-li/AIDev@main/pull_request.parquet` | `e35155c6ac4c94fbb81eb88f3f2f38f6` | https://huggingface.co/datasets/hao-li/AIDev/resolve/c63c8a57a2de34fc03fa83722412824af4d8753b/pull_request.parquet |
| `hao-li/AIDev@main/repository.parquet` | `a233a6d7aa6470884915423c908318bb` | https://huggingface.co/datasets/hao-li/AIDev/resolve/c63c8a57a2de34fc03fa83722412824af4d8753b/repository.parquet |
| `hao-li/AIDev@v3/pull_request.parquet` | `c070361e71ee941b3450d53fcdd07b32` | https://huggingface.co/datasets/hao-li/AIDev/resolve/68ed5f4b80d27a9e057fc57567f38bd322ac73ec/pull_request.parquet |
| `hao-li/AIDev@v3/repository.parquet` | `ce7feeddb10a99ce558518305d3be391` | https://huggingface.co/datasets/hao-li/AIDev/resolve/68ed5f4b80d27a9e057fc57567f38bd322ac73ec/repository.parquet |
| `zenodo-21186464/replication_package.zip` | `59a99c9cf58793957806a7fa5e712f8f` | https://zenodo.org/api/records/21186464/files/replication_package.zip/content |
