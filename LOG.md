# LOG

Running log of what was tried, what failed, and what was learned, in order.

## 1. Environment reconnaissance (before planning)

- Toolchains present: Python 3.12 (`/usr/bin/python3.12`), uv, ruff, pyright, Node 22,
  npm, cargo 1.97, Go 1.24, git 2.43. `just` was missing; installed with
  `uv tool install rust-just` (1.58.0).
- Outbound HTTPS goes through an egress proxy. `github.com` web pages and
  `api.github.com` return 403 (policy). `git ls-remote` / `git fetch` over HTTPS to
  public GitHub repositories work. Zenodo, Hugging Face, npm, PyPI, crates.io work.

## 2. Pair dataset (kill assumption 1)

- GitHub mirror `Quantum535/concurrent-agentic-prsreplication`: 403 (web) and
  `git ls-remote` asks for credentials (repository not public, or absent).
- Zenodo record 21186464 is reachable: one file, `replication_package.zip`
  (302,847 bytes, md5 59a99c9cf58793957806a7fa5e712f8f). Contents: README, five scripts,
  `rq3_merge_replay_full.csv` (747 rows), `rq3_rates_full.csv`, `rq3_taxonomy_full.csv`,
  four figures.
- The CSV has stratum, repo, PR numbers, agents, label, conflicted files and conflict
  types. It has **no** head SHAs, merge bases or merge commits. The replay script shows
  how labels were made: shallow fetch (depth 80, retry 600) of `refs/pull/N/head`, then
  `git merge-tree --write-tree` of the two heads. Merge commits were never consulted.
- Recomputed from the CSV: same 119/601 = 19.8%, cross 48/115 = 41.7%; conflict
  messages 1,652: content 952 (57.6%), modify/delete 442 (26.8%), add/add 249 (15.1%),
  rename/delete 6, file location 2, distinct types 1. Conflicted files: 1,646, median 1
  per pair, max 905.
- AIDev v4 (`hao-li/AIDev`, main) is reachable: `pull_request.parquet` (71,677 PRs),
  `repository.parquet`, `pr_commits.parquet`. 727 of 747 pairs match on
  (repo, number); agent labels match the CSV for all 727. 20 pairs are missing from v4.
- Of the 167 CONFLICT pairs, only 23 have both PRs merged (5 cross, 18 same).
  Human resolutions can exist only for those.

## 3. Leak-proof workspace from a real repository (kill assumption 2)

- `Rello/analytics` PRs 517/518: blob-less bare clone, `git fetch` of both
  `refs/pull/N/head` works. Copying only the three trees' objects with
  `rev-list --objects | pack-objects | index-pack` into a fresh repo and creating three
  synthetic commits gives `git rev-list --all` = 3, `git remote -v` empty, and the
  merge reproduces the paper's conflict in `CHANGELOG.md`.
- Missing blobs in a blob-less clone are fetched explicitly by SHA
  (`git fetch origin <sha>...`): 1,241 blobs in under 2 s.

## 4. Contaminated heads (new finding)

- For the 23 both-merged conflicting pairs, merge commits were located by matching
  committer time to AIDev `merged_at` (exact to the second where found): 18 of 23
  located for both PRs.
- In 17 of those 18, the PR merged second has a final head that descends from the
  first PR's merge commit ("Merge branch 'master' into ..."). In 13, the final head's
  tree is identical to the tree of the human merge on the default branch. Replaying
  final heads would give the resolver the human resolution as one side.
- Rewinding the contaminated head along its first-parent chain to the last commit that
  does not contain the other PR's merge: 4 pairs were rebased (rewind lands on the
  default branch: unrecoverable), 6 still conflict, 8 merge cleanly, plus
  vscode-mssql (below). The paper's conflict label is an artifact of the absorbed
  merge for those 8.

## 5. A reconciliation discrepancy seen early

- `microsoft/vscode-mssql` 19567/19577: paper CONFLICT (1 file), today the two final
  heads merge cleanly; single merge base 6 and 7 commits away. To be classified in F3.

## 6. Structural drivers and resolver plumbing

- weave: `npm install @ataraxy-labs/weave@0.5.2` works, `weave --version` = 0.5.2.
- mergiraf: `cargo install --locked mergiraf@0.20.0` works.
- A tool-restricted subagent type defined after session start is not loaded
  ("Agent type not found"), at user or project level. A general-purpose subagent's
  transcript (tool calls with inputs, token usage, timestamps) is written to disk and
  can be audited after the run. Decision D6.
