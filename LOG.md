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

## 7. Supplementary pool size (feasibility only, no outcomes looked at)

- AIDev v4 `pr_commit_details.parquet` (1,325,541,903 bytes; first download cut off by an
  HTTP/2 stream reset, resumed with a range request): 1,775,765 rows, file names for
  69,654 PRs. 48,451 PRs in `pull_request.parquet` are merged.
- Under the D15 rule, 931 repositories have at least one candidate pair (17,348 candidate
  pairs in total). Enough to reach 60 conflicting pairs with truth unless the conflict
  yield at replay heads is below about 7%.

## 8. Fixture built; structural predictions vs. observed (before updating expected.json)

The fixture subagent ran weave 0.5.2 and mergiraf 0.20.0 as git merge drivers on every
conflicting scenario. Cells of `fixtures/expected.json` with basis `prediction`:

| scenario | rung | predicted | observed |
|---|---|---|---|
| fx02 | weave | conflicted | **resolved**, equal to resolved/2 |
| fx02 | mergiraf | resolved, equivalent | resolved, equivalent (held) |
| fx04 | weave, mergiraf | conflicted | conflicted (held) |
| fx05 | weave, mergiraf | conflicted | conflicted (held) |
| fx08 (replay heads) | weave | conflicted | **resolved**, equal to resolved/8 |
| fx08 (replay heads) | mergiraf | conflicted | **resolved**, equal to resolved/8 |

Design cells held (fx01 resolved by both; fx03 and fx07 conflicted under both), after the
builder adjusted fx01 and fx03 edits so the pinned tools behave as the spec requires
(`reviews/P1-fixture.md`). 2 of the 6 predicted structural rows were wrong: structural
drivers resolved more than I predicted. `expected.json` updated with basis `observed` for
the three wrong cells; llm-post-weave becomes `absent` for fx02 and fx08 since weave
resolves them.

Contamination rule flaw found while reviewing the fixture: rule (b) in `PLAN.md` 5.1 used
"reachable from the default branch", but a true-merged PR's own commits are reachable from
the default branch (second parent of its merge), so PR commits made after the other PR
merged would be mis-flagged as contamination. Revised to the default branch's
first-parent chain (PLAN.md revision 10).

## 9. Phase 3 step 1: ref resolution over all 747 paper pairs

`uv run ladder pairs load --source data/source` then
`uv run ladder pairs resolve --all --jobs 8` (8 min 50 s wall; blob-less caches 12 GB).

| status | pairs |
|---|---|
| ok | 707 |
| unrecoverable_rebased | 25 |
| fetch_failed | 14 |
| no_merge_base | 1 |

- All 14 fetch failures are among the paper's 25 `UNAVAIL_fetch` pairs; the other 11
  `UNAVAIL_fetch` pairs and 5 of the 6 `UNAVAIL_nobase` pairs resolve today (full history
  instead of the paper's depth-80 shallow fetch).
- Contamination: 105 pairs have a contaminated head (63 on side a, 42 on side b): 75 of the
  paper's CLEAN pairs and 30 of its CONFLICT pairs. 80 were rewound to a PR commit; 25 were
  rebased onto the other PR's merge and cannot be replayed (15 paper-CLEAN, 10 paper-CONFLICT).
- Truth: 196 pairs have both PRs merged and a located truth commit (absorption 66,
  merge_parent 54, subject_time 66, time_only 10); 24 both-merged pairs have no locatable
  truth commit; 527 are not both merged.
- Disk: the blob-less caches took 12 GB, so workspaces and rung copies are deleted after
  each git rung unless the pair conflicts at replay heads (rebuilt on demand; builds are
  deterministic).

## 10. Process incident: a subagent deleted its own worktree

The report lane's scratch script ran `shutil.rmtree(sys.argv[1])` with its worktree path,
wiping that worktree's working tree (70 tracked files and `.venv`). Its four commits and
the branch were intact; the main checkout, the repository caches under `work/`, and the
other lanes' worktrees were checked and untouched. The main model restored the worktree
with `git checkout -- .`. No experiment data was affected. Subagent prompts now forbid
scratch scripts that delete directories outside /tmp.

## 11. Disk exhaustion during reconciliation, and the streaming policy

The first reconciliation pass (6 parallel workers) kept the replay workspace and the git
rung's copy for every conflicting pair, and every workspace build back-fills the three
trees' blobs into the repository cache. After 120 of 747 pairs the session's disk
allowance was exhausted (caches 16 GB, kept copies 10 GB for 37 conflicting pairs, plus
in-flight builds of pytorch and vcpkg). The run was stopped before any git failure was
written as a result: no rung record has status `error` (checked), and records are written
atomically after a successful step.

Policy from here on:
- Reconciliation keeps result records only: every workspace and rung copy is deleted
  right after its git rung; the repository cache is deleted once a pair is known not to
  conflict at replay heads (unless another pair shares the repository). A pair waits while
  less than 5 GB is free. Three workers.
- The ladder stage streams pairs: rebuild the pair's workspace (deterministic: same
  synthetic SHAs), run the structural rungs, prepare and run resolvers, extract truth,
  score, then delete the pair's working copies. The double-run sample is drawn before any
  truth is extracted.
- Claim C (first in the cut order) rebuilds workspaces, re-cloning caches when needed.

## 12. Supplementary candidates: 896 repositories, not 931

Applying D15 exactly (rule 1 excludes the paper's own pairs) leaves 896 repositories with a
candidate (880 same-agent, 16 cross-agent; 17,348 candidate pairs before the exclusion,
matching entry 7). 35 repositories had only paper pairs as candidates. The acceptance test's
lower bound of 900 was my estimate from entry 7's 931, made before the exclusion; it was
lowered to 890. The rule itself is unchanged.

## 13. Phase 3 step 2: git rung reconciliation with the replay study

All 747 paper pairs went through `ladder rung git --in-cache` at final heads (the study's
method: merge-tree on the two PR heads, git's own merge base) and at replay heads (with the
recorded replay merge base). No record has status `error`. Final heads exist for 732 pairs.

| stratum | paper | this harness, final heads (95% Wilson) |
|---|---|---|
| same-agent | 119/601 = 19.8% | 113/612 = 18.5% [15.6, 21.7] |
| cross-agent | 48/115 = 41.7% | 50/120 = 41.7% [33.2, 50.6] |
| pooled | 167/716 = 23.3% | 163/732 = 22.3% [19.4, 25.4] |

Within 5 points in both strata, as F3 requires. Conflict types at final heads: content 56.5%
(paper 57.6%), modify/delete 32.1% (26.8%), add/add 11.2% (15.1%), of 1,325 messages (paper
1,652).

Every disagreement was classified by re-running the study's own procedure
(`run_replay.py`: fetch both PR refs at depth 80, `git merge-tree`) today, and again with full
history:

| pair | paper | study's method today (depth 80) | full history |
|---|---|---|---|
| microsoft/vscode-mssql 19567-19577 | CONFLICT, 1 | conflict, 1 message | clean |
| static-frame/static-frame 1068-1069 | CONFLICT, 1 | conflict, 1 | clean |
| microsoft/typescript-go 1086-1093 | CONFLICT, 4 | conflict, 4 | clean |
| microsoft/vscode-python 25103-25156 | CONFLICT, 10 | conflict, 10 | clean |
| microsoft/onnxruntime 24931-24947 | CONFLICT, 29 | conflict, 29 | clean |
| MetaMask/metamask-extension 34098-34489 | CONFLICT, 23 | conflict, 23 | clean |
| Azure/azure-container-networking 3671-3672 | CONFLICT, 1 | **clean** | clean |
| google-gemini/gemini-cli 3417-4286 | 37 messages | 37 | 1 |
| Significant-Gravitas/AutoGPT 9958-10340 | 241 messages | 241 | 12 |

- 8 of 9 disagreements are artifacts of the study's depth-80 shallow fetch: with truncated
  history, merge-tree sees a different merge base or merge-base set and reports conflicts
  that the full history does not have (the study's method reproduces its own numbers exactly
  today). These 8 also explain the type-share gap (AutoGPT alone accounts for 229 of the 327
  missing messages, most of them add/add).
- 1 pair (azure-container-networking) is clean even with the study's own method today:
  unexplained; possibly a transient fetch problem at the study's run.
- No paper-CLEAN pair conflicts at final heads. 16 pairs the study could not evaluate are
  evaluable here (11 UNAVAIL_fetch, 5 UNAVAIL_nobase): 3 of them conflict.

Transition table, paper label x final heads x replay heads (pairs):

| paper | final | replay | n |
|---|---|---|---|
| CLEAN | clean | clean | 525 |
| CLEAN | clean | **conflicted** | 9 |
| CLEAN | clean | unrecoverable | 15 |
| CONFLICT | clean | clean | 6 |
| CONFLICT | clean | unrecoverable | 1 |
| CONFLICT | conflicted | **clean** | 7 |
| CONFLICT | conflicted | conflicted | 144 |
| CONFLICT | conflicted | unrecoverable | 9 |
| UNAVAIL_fetch | clean / conflicted / unavailable | same | 10 / 1 / 14 |
| UNAVAIL_nobase | clean / conflicted / unavailable | same | 3 / 2 / 1 |

Rewinding contaminated heads changes the label of 16 pairs: 9 paper-CLEAN pairs conflict
once the absorbed resolution is removed (their final heads merge cleanly because one side
already contains the resolution), and 7 paper-CONFLICT pairs merge cleanly. The paper-set
ladder set (conflicting at replay heads) is 156 pairs.

## 14. Supplementary sample S: stopping point

`ladder pairs sample-supplementary --source data/source --seed 42` appended the 896 candidates
in their pre-registered order. They were resolved and git-runged in order in batches of 150
(`pairs resolve --pair ... --jobs 8`, then `rung git --in-cache` at both heads). One batch
first crashed on a repository whose tag shares its default branch's name (fixed, `LOG.md`/
`reviews/F1b-resolve.md` follow-up) and was re-run before counting.

The 60th pair that conflicts at replay heads with a located truth commit is at position 502
(index 501) of the ordered list, so S is the first 502 candidates. The 98 pairs processed
after it (an artifact of batching) are not part of S per D15; they were removed from
`data/pairs.json` and their records moved to `work/beyond-stop/` (not reported).

S outcomes (502 pairs): ok and clean 367 (320 with a located truth), ok and conflicting 68
(60 with a located truth, 8 without), unrecoverable (rebased) 58, fetch failed 9.
Contamination is as common as in the paper set: in the first 150, 97 pairs had a contaminated
head.

## 15. Phase 1 acceptance with real resolvers (fixture pilot)

`just ladder --fixture` first stopped with exit 3 and 8 pending resolver tasks (llm-raw for
fx01, fx02, fx03, fx04, fx05, fx08; llm-post-weave for fx03, fx05). Eight fresh-context
resolver subagents were spawned in parallel, each with only its spawn line;
`ladder resolve collect --transcripts <subagent transcript dir>` finalized 7 of them; fx03
llm-raw matched two transcripts (the earlier recorded run used the same task path) and was
finalized explicitly with the new one.

**Audit false positive found in the pilot.** fx05 llm-raw was recorded as
`protocol_violation: Glob without a path`. Its transcript shows two Glob calls with no
`path` argument but an absolute `pattern` inside its own task directory (for example
`<task>/files/**/*`), which is exactly what the prompt asks for ("an absolute path that starts
with" the task directory). The audit implemented "must name a path" as "must pass the `path`
parameter". Fixed in `audit.py` (a48a6d2): a Glob without `path` passes only when its pattern
is absolute, has no `..`, and its fixed prefix is inside the task directory; Grep and Read
rules unchanged (DECISIONS D18). The fx05 transcript was then re-audited (its run record
moved aside, the same transcript finalized again: `ok`). The resolver was not re-run. This
happened on the fixture, before any real resolver run.

`just ladder --fixture` then exited 0: **180 cells checked, 0 mismatches, 0 LLM cells
skipped**. Actual outcomes (M = mergeable, HE = human-equivalent):

| scenario | git final / replay | weave | mergiraf | llm-raw | llm-post-weave | trap | Claim C |
|---|---|---|---|---|---|---|---|
| fx01 | conflicted / conflicted | resolved; M, HE, intent ok, passed | resolved; M, HE, intent ok, passed | M, HE, intent ok, passed | n/a | - | - |
| fx02 | conflicted / conflicted | resolved; M, HE, intent ok, passed | resolved; M, HE, intent ok, passed | M, HE, intent ok, passed | n/a | - | - |
| fx03 | conflicted / conflicted | conflicted; not M, not HE, intent ok, no tests | conflicted; not M, not HE, intent ok, no tests | M, HE, intent ok, passed | M, HE, intent ok, passed | - | - |
| fx04 | conflicted / conflicted | conflicted; not M, not HE, drops b, no tests | conflicted; not M, not HE, drops b, no tests | M, HE, drops a, failed | M, HE, drops a, failed | - | - |
| fx05 | conflicted / conflicted | conflicted; not M, not HE, intent ok, no tests | conflicted; not M, not HE, intent ok, no tests | M, not HE, intent ok, passed | M, not HE, intent ok, passed | - | - |
| fx06 | clean / clean | - | - | - | - | - | fails together |
| fx07 | conflicted / conflicted | conflicted; not M, not HE, intent ok, no tests | conflicted; not M, not HE, intent ok, no tests | n/a | n/a | M, not HE, drops b, passed | - |
| fx08 | conflicted / conflicted | resolved; M, HE, intent ok, passed | resolved; M, HE, intent ok, passed | M, HE, intent ok, passed | n/a | - | - |
| fx09 | clean / clean | - | - | - | - | - | passes together |
| fx10 | clean / unrecoverable | - | - | - | - | - | - |

Readings: the LLM resolved fx03 (the LLM-only scenario) human-equivalently, both raw and after
weave. fx04 shows the protocol's limit: deleting `helpers.py` matches the human on the
conflicted file, but A's whitespace change is dropped because the needed edit is in
`core.py`, which the resolver may not write (A's test fails); weave and mergiraf keep the file
B deleted and drop B instead. fx05's LLM merge of two `retry` modules is mergeable and keeps
both intents but is not the human's text. The trap scores tests-pass and intent-dropped (B).

## 16. Phase 3 resolver waves, self-output reads, and the first Claim C disk incident

- Resolver runs go in waves of 20 ladder pairs, smallest first (`work/ladder-order.txt`).
  Each wave is prepared with `ladder run <pairs> --stop-before-truth --prune --skip-claim-c`.
  One general-purpose subagent is spawned per pending task with the fixed spawn line, at
  most 20 at a time. No truth file exists while waves run.
- Transcripts are collected only for subagents that have handed back. `resolve collect`
  matches every pending task that has a transcript, so a still-running resolver would have
  been finalized half-done. Collection now goes through a directory that holds only
  transcripts containing a hand-back tool call. This was caught before the first collection.
- After waves 1 and 2, 8 of 60 finalized runs had failed the audit, all for reading files in
  their own output directory after writing them. More appeared in wave 3, together with one
  run that used Bash (CravateRouge__bloodyAD__81-82 llm-post-weave). All stay
  `failed: protocol_violation`, and the reporting rule is D20.
- Claim C wave c01 started alongside resolver waves. Its first runnable pair,
  PRQL__prql__5286-5287 (Rust), built three cargo targets into one runtime and took free
  disk from 9 GB to 1.6 GB. I stopped the run and deleted that pair's runtime. No resolver
  write failed. PRQL has no Claim C record and keeps its place in the order. Claim C is
  paused until every resolver wave has settled and a free-disk floor exists for installers
  and test runners (acceptance test committed; implementation in progress). The floor is a
  resource rule, fixed before any Claim C outcome other than one exclusion
  (`bmander__graphserver__32-34`, unrunnable: no manifest). `ladder run` groups a wave by
  repository, so its order inside a wave differs from `data/claimc-order.txt`. That is
  harmless, because D19 only stops at wave boundaries; wave c01 is rerun in full.

## 17. Disk full during wave 5 (four resolver runs lost)

- Wave 6 preparation ran while wave 5 resolvers were still running. One pair,
  Unity-Technologies__com.unity.toonshader__492-497, has a 1.6 GB workspace (Unity assets),
  and the git rung, weave, and mergiraf each copy it. The mergiraf copy filled the disk to
  0 bytes. `wait_for_disk` checks only before a pair starts, so it did not catch a single
  pair this large.
- Effects:
  - Four resolver runs could not write their output, and their transcripts were cut off
    mid-line: synth-inc__onit__184-186 (llm-raw, llm-post-weave) and
    wandb__openui__235-237 (llm-raw, llm-post-weave). They are finalized as failed
    (`audit_impossible` or malformed output); see D21.
  - Wave 6 preparation stopped at the Unity pair with an error. No mergiraf record was
    written, so the step will run again.
  - The disk-floor implementation lane could not run its tests.
- Recovery:
  - Deleted the Unity pair's working copies.
  - Pruned the copies of settled pairs from waves 4 and 5.
  - Deleted 219 repository caches (5.6 GiB) of repositories that have no conflicting pair.
    The three canary caches were kept. Claim C clones those repositories again when it
    needs them.
  - Free space went from 0 to 16 GiB.
- From now on, preparation runs only while no resolver is running, with a 10 GiB floor, and
  the Unity pair is prepared last, alone.

## 18. Transcript line splitting, waves 6 to 8, and an interrupted prune

- **Transcripts that could not be parsed.** Both moonbitlang__core__2267-2422 transcripts quote
  U+2028 and U+2029 from a test file. `str.splitlines()` splits on those characters, so the
  audit reported both transcripts as unparseable. Test `7d2e1eb`, fix `347541d`: JSON Lines
  are now split on `\n` only. Both runs were then recorded as `ok`. No other record changed.
- **Waves 6 to 8.** 93 resolver runs, prepared one wave at a time and only while no resolver
  was running (D21). Failures are recorded as failed. Three resolvers read outside their
  task directory in a way D20 does not cover: one used Bash, one read a harness spill file,
  and one Grep-checked its own output twice and said so in its report. All three stay
  `failed: protocol_violation` and none is re-run.
- **Interrupted prune.** A worker restart killed `ladder run --prune` while it was rebuilding
  theopenco__llmgateway__208-354. `run` rebuilds any pruned working copy before going on,
  and trusts any directory that exists. A copy cut off part-way would therefore have been
  read later as if it were complete. The pair's copies were deleted by hand before the next
  run. Test `1a10d1e` reproduces the case: each working copy must carry a completion mark,
  and a directory without one is rebuilt. The fix is in progress.
- **Wasted rebuilds.** Pruning a pair that was already pruned rebuilds its workspace first
  and then deletes it again. This happened for about 20 wave-8 pairs. It costs time only,
  because records are never rewritten when they exist.

## 19. Preparation overlapped running resolvers once

- The background step that waits for resolvers, then collects and prepares, decided whether
  a resolver had handed back by searching its transcript for the bare tool name. That name
  also appears in the tool list each transcript records at its start (checked), so every running resolver
  looked finished. Collection was not fooled: it uses the stricter pattern and transcripts
  older than two minutes, so it finalized only the two runs that had really finished. But
  preparation then ran while six resolvers were still working. That breaks the D21 rule.
- Effect: two pairs (WorkflowAI__WorkflowAI__371-449, nodetool-ai__nodetool__86-157) were
  prepared while those resolvers ran. Free disk stayed above 9.6 GiB. No resolver write
  failed, and every transcript of that batch parses. No record is affected.
- Fix: the wait step now uses the same strict hand-back pattern as collection.

## 20. All first resolver runs settled; double-run sample drawn

- All 224 conflicting pairs have a resolver plan. 409 run-1 tasks were prepared:
  - 327 went to a subagent;
  - 75 were refused because their input was over the input cap (recorded as
    `failed: input_cap`);
  - 7 post-weave runs had input identical to the raw run (`identical_input`; no separate
    run).
- Of the 327 runs:
  - 289 are `ok`;
  - 32 failed the audit only for reading their own output (D20);
  - 2 failed for other violations (Bash; a harness spill file);
  - 4 were lost to the full disk (D21).
  None was re-run.
- The variance sample of PLAN 5.6 was drawn with `ladder resolve sample-double --n 30
  --seed 42` from all 224 pairs whose plan has llm-raw run 1. No truth existed when it was
  drawn. The 30 pairs are in `work/double-pairs.txt`; their plans now include llm-raw run 2.

## 21. Final pass and Claim C, run side by side

- Truth extraction and scoring start with the 190 conflicting pairs whose repositories hold
  no double-run pair (`work/final-first.txt`). The other 34 (`work/final-later.txt`) follow
  once the double run has been collected: the truth guard holds a whole repository until
  every resolver run in it has settled.
- Claim C waves of 20 (D19 order, starting again at c01) run at the same time as the final
  pass. On this 4-core machine both are mostly bound by dependency installs. Running them
  together can push more suites past their time caps. A capped suite is recorded as capped
  and leaves its pair out of the rate, so the report states those counts by cause.
- Background commands of the agent tool are killed after two hours. So both passes run as
  detached scripts that resume where they stopped: a pair is skipped once it is pruned
  (final pass) or has a `claim-c` record (Claim C). Records are written atomically and
  working copies carry completion marks, so stopping at any point is safe. They were
  stopped and restarted once, at 09:47, for this reason.
- Double run settled: 30 run-2 tasks prepared. 4 were refused at the input cap and 26 went
  to a subagent. Of those 26, 23 are `ok` and 3 failed the audit only for reading their
  own output (D20). D22 allowed preparation and these resolvers to overlap.
- From 09:47 to about 10:00 both passes waited without making progress: free disk was
  9.6 GiB against a 10 GiB floor before each pair. A container restart then stopped
  everything. Settled task snapshots (3 GB), the Go build cache and part of the uv cache
  were deleted, which left 14 GB free. Both passes were restarted at 10:04 with lower
  floors: 5 GiB before each pair for the final pass, and 8 GiB for Claim C, so Claim C
  backs off first. The 3 GiB floor inside each suite is unchanged. A watchdog now reports
  a stall within five minutes.
- At 10:20 Claim C was waiting again (7.2 GiB free against its 8 GiB floor). Deleted
  leftovers of earlier checks (an F8 trial clone, pytest temp directories, old tool builds
  in the scratchpad), cleared the Go build cache and pruned the pnpm store. That left
  10 GiB free, and both passes went on without a restart.
- One Claim C pair was lost to disk while free space was low after the restart.
  `PRQL__prql__5286-5287` (c01) is recorded with `error at a: … install failed: build:
  stopped, free disk below the 3 GiB floor`. The guard worked as designed. The pair stays
  excluded and is reported under that cause. It is not run again: re-running only the
  pairs whose outcome was a failure would be a choice made after seeing outcomes.
- 10:26: Claim C paused after wave c01 (stop file checked between waves). Claim C is
  first in the cut order and the final pass is never cut. On 4 cores the two passes
  slowed each other: load average 6 to 7, about 3 minutes per pair. Running them together
  also pushes more suites past their wall-clock caps. The final pass now runs alone.
  Claim C resumes at c02 in the same D19 order once it is done. This is a pause, not a
  cut: no pair is skipped.
- About 10:33 the container restarted again. It stopped the final pass, the autocommit loop,
  the watchdog and a fresh-clone check of HOW_TO_RUN_LOCALLY. That check had passed `just
  setup`, `just tools` and `just check` and was inside `just e2e`. Claim C was already
  stopping at the c01 boundary. Free disk was 5.1 GiB. Cleared the uv and npm download
  caches (3.5 GB), which left 7.8 GiB, and restarted the final pass at 10:38 with 182 pairs
  left. One pair's workspace record, deleted mid-rebuild, is rebuilt by the run.
- A test suite of some pair wrote `tmp/testutil-filelock.txt` (19 bytes) into the
  repository root at 10:24. Suites run in their own tree but inherit `PWD` from `ladder`.
  The file was deleted. Running untrusted suites only in a disposable machine (README,
  HOW_TO_RUN_LOCALLY) covers this. No result depends on it.
- 10:45: the final pass hung on `mlflow__mlflow__16057-16442`. Its own working copies (about
  4 GB) put free disk under the 5 GiB floor, and a second wait between building and scoring
  a pair could not end (reviews/F8d-disk-wait-deadlock.md). Deleting the Go module cache and
  a scratch clone freed the space. The second wait was removed, and the pass was restarted
  so the fix applies to the remaining pairs.
- 10:55: the single final pass had pruned 10 of 224 conflicting pairs, about 10 minutes
  per pair over the last hour. That pace counts the giant mautic and mlflow pairs and two
  restarts. With Claim C paused, load average was about 1.7 on 4 cores: most of each pair
  is spent on clones, dependency downloads and single-threaded suites. At the next pair
  boundary the single pass is replaced by three parallel `ladder run` processes. Each
  takes a disjoint set of repositories (`work/final-shard-*.txt`, balanced by pair count)
  and waits for 6 GiB free before each pair. All resolver runs are settled, so the 34
  pairs of `work/final-later.txt` join now. Records do not depend on how pairs are spread
  across processes. Contention can push more suites past their caps, which is recorded as
  `capped` and reported by cause.
- 11:02: the final pass waited again at 3.4 GiB free. The shared Go build cache had grown to
  4.1 GB in 40 minutes and the module cache to 1.7 GB. Both were cleared once no `go`
  process was running (9.1 GiB free). Go builds now use a cache inside each pair's runtime
  directory, which is deleted with the pair (reviews/F8e-go-cache.md). The sharded pass
  starts with this change.
- 11:03: the sharded pass started with 213 pairs (71 per shard). Shard 0 began 8 s before
  the per-pair Go cache change was saved, so it was restarted at 11:05 with the change.
  By 11:14 all three shards were waiting at 4.1 GiB free. Two airbyte pairs held about
  5 GB, and 9.1 GB of repository caches were kept for pairs not yet started. A janitor
  (`cache_janitor.py` in the session scratchpad) now runs beside the shards. When free
  disk drops below 8 GiB, it deletes the largest repository caches that no shard is on
  or about to reach (each shard's current pair and the next three), up to 10 GiB free.
  The first round deleted 31 caches. A pair whose cache is gone clones it again, which
  costs time, not records.
- 11:25: `e2e/test_report.py` re-run on the main checkout after merging F9b: 3 passed in
  252 s (slow because the three shards were running). An earlier run with a 900 s limit
  was cut off by that limit after two tests passed. It was a time limit, not a failure.
- 11:44: all three shards waited at 5.4 GiB free. `/tmp` held 8.6 GB of suite leftovers
  (bruin's unpacked Python environments, a killed Go test's build directory), the shared
  uv cache 6.5 GB and the Go module cache 3.0 GB. The named `/tmp` leftovers were deleted
  once no Go process was running (14 GiB free). Every install and suite step now gets
  `TMPDIR`, `UV_CACHE_DIR` and `GOMODCACHE` inside the pair's runtime, which is deleted
  when the pair is pruned (reviews/F8f-pair-scratch.md). `e2e/test_runnable.py`,
  `test_claim_c.py` and `test_score.py`: 3 passed. Each shard is restarted after its next
  pruned pair so the change applies.
- 11:52: free disk fell to 2.6 GiB within minutes. Shards 0 and 2 still ran the old code,
  and a Go pair (`berachain__beacon-kit`) filled the shared module cache again. Both were
  restarted at once on the per-pair scratch code (11:53), each losing the pair it was on.
  The shared uv cache (6.4 GB) and Go module cache were then cleared (20 GiB free). 18
  records in 8 pairs had been stopped by the free-disk floor. D23 decides, before any redo,
  that all of them are redone once after the final pass.
- 12:26: 80 of 213 sharded pairs done. Free disk was 4.6 GiB, from a Go pair's runtime
  (kanister, 5.6 GB, legitimate) and the shared Node caches (pnpm store 4.5 GB, npm 1.9 GB).
  With no Node process running, the npm cache was cleared and the pnpm store pruned
  (7.4 GiB free). Node, yarn, puppeteer and XDG caches now also live in each pair's scratch
  directory (reviews/F8f-pair-scratch.md, follow-up). Shards restart at their next pair
  boundary.
- 12:51: 114 of 213 sharded pairs done. Shards 2 (12:36) and 1 (12:41) restarted on the
  Node-cache code. Shard 0 is still on kanister, a large Go pair, and restarts after it.
  The two largest pairs ran at the same time: Unity toonshader (6.4 GB of working copies,
  the pair D21 already set apart) and kanister (5.2 GB of Go runtime). Free disk fell to
  4.0 GiB, and suites in other shards hit the floor. Records carrying the floor phrase rose
  from 18 to 35 (13 pairs). D23 redoes all of them. The poetry and puppeteer caches were
  cleared with no process using them (6.5 GiB free).
- 13:31: shard 2 finished (39 done, 3 failed); shard 1 is at 64 of 71 and shard 0 at 35 of 71.
  The three failures and one older one were caused by the janitor. It decided which
  repositories were "about to be reached" by list order, but `ladder run` takes
  repositories in the pairs file's order. So it deleted caches under running truth steps.
  The failed steps wrote no record. The janitor now deletes a cache only when every
  conflicting pair of that repository has truth and a git score. A "pruned" log line was
  also wrong as a sign that a pair is done, because failed pairs are pruned too. Shard
  restarts that relied on it dropped `Rello__audioplayer__626-627`. Completeness is now
  judged from the records (`truth.json` and `score-git.json`). The 4 orphaned pairs run in
  a fourth process (`work/final-sweep.log`), and a final sweep over all 224 pairs follows
  the shards.
- 13:50: final pass at 189 of 224. The orphan sweep completed its 4 pairs. Shard 1 finished,
  and shard 0's last 35 pairs run as two processes (`final-shard-0a`, `0b`). Every process
  now uses per-pair scratch, so the shared pnpm store (3 GB) was removed with no pnpm
  running. Claim C resumes from wave c02 in D19 order, since two processes leave CPU free.
  It is paused again at a wave boundary before the D23 redo, which runs alone.
- 14:06: final pass complete. All 224 conflicting pairs have truth and a git score. Claim C
  was paused mid-wave c02 at 14:08 (recorded pairs are kept and skipped when it resumes).
  The shared Rust caches were cleared: the cargo registry (6.4 GB) and four toolchains
  that Rust pairs had pinned (3 GB). That left 20 GiB free, as D23 requires.
- 14:10: D23 redo started, alone. 20 pairs carried the free-disk floor phrase: 17
  conflicting pairs and the Claim C pairs `PRQL__prql__5286-5287`,
  `bruin-data__bruin__733-735` and `evergreen-ci__evergreen__9033-9034`. 110 records were
  deleted (runnability, scores including run-2 scores, Claim C). The list is in
  `data/results/redo-d23.json`. Each pair runs once more (`work/d23-redo.log`).
- 14:20 to 14:45: calibration (PLAN 5.6). 20 intent-dropped and 20 human-equivalent verdicts
  were drawn with seed 42 from the scores as they stood at 14:06, before the D23 redo
  deleted some. Those verdicts do not depend on test runs, so the redo cannot change them.
  Each verdict was read against base, A, B and the maintainers' resolution, fetched by SHA
  into a scratch clone. Structural outputs were regenerated with the pinned drivers. The
  rubric is whether the output lacks the PR's behaviour change; exact lines are not
  required.
  - Human-equivalent: 20 of 20 agree. Most are identical once whitespace is normalized.
    One differs by line wrapping, and four are modify/delete pairs that both deleted.
  - Intent-dropped: 12 of 20 agree. 12 of 14 on git and structural outputs: the change
    sat in an unresolved conflict. 0 of 6 on LLM outputs: competing or combined
    implementations, near-identical lines such as typo fixes, or an applied rename that
    line containment misses. Entity-level drops on unparseable outputs (conflict markers)
    are often artifacts, though other changes in the same output are really unresolved.
  - `data/results/calibration.json` holds every verdict with a note. D24 records how the
    report presents this next to Claim B.
- 14:44: the D23 redo split into two processes after its first pair (flyctl, now
  runnable). By 14:51 free disk was 3.9 GiB. The Go process was on flow-go (6.0 GB of
  runtime). The other process was on `PRQL__prql__5286-5287`, a Rust Claim C pair with
  6.9 GB of runtime. Splitting by language had wrongly assumed only the Go pairs were
  large. Three leftovers no process used were deleted:
  - kanister's 3.5 GB runtime, left by the final pass (that pair is in the redo and gets
    rebuilt);
  - the cal.com copies, left by the Claim C wave paused at 14:08;
  - my own pytest temp directories and the shared uv cache.
  That brought free disk back to 6.2 GiB. A monitor now reports any drop below 4.5 GiB.
  Any redo record that stops at the floor again stays, as D23 says.
- 14:57: the redo's Claim C record for `PRQL__prql__5286-5287` stopped at the floor again.
  Its own Rust rebuilds for A and the merge took the runtime to 11 GB while flow-go
  (7.5 GB) ran in the other process. B passed (504 tests). The record stays (D23). The
  "rest" process was stopped right after that record was written, before its next pair,
  and PRQL's copies were deleted (24 GiB free). The other eight "rest" pairs run alone
  after the Go process (`work/d23-rest2.txt`).
- 15:06: both bruin pairs stopped at the floor again in the redo, and the records stay
  (D23). `bruin-data__bruin__733-735` (Claim C) ran its own suite until its runtime held
  20 GB. Bruin's tests unpack a ~431 MB embedded Python environment per test into
  `TMPDIR`, which is now inside the pair's scratch directory. The first run had passed
  118 tests before the stop. `bruin-data__bruin__760-818` then could not install at the
  floor. With the Go-heavy group running alone, this repository's suite needs more disk
  than this 40 GB machine has, so `exceeds_cap` by free disk is the honest record.
- 16:24: the Go-heavy redo group finished, and the other eight pairs started alone. Four of
  the 20 redone pairs still carry a floor-stopped record, and they stay (D23):
  - `onflow__flow-go__7551-7555`: its runnability build stopped at 14:57:23;
  - `PRQL__prql__5286-5287`: its Claim C record, from the same minute.

  Both came from the window when two redo processes ran together (second amendment) and
  PRQL's Rust builds filled the disk. The two bruin pairs stopped for their own suite's
  disk use (see 15:06). So the second amendment cost two redone records. Running alone
  would probably have avoided that, and the results review says so.
- 17:13: `block__goose__2620-2621` (Rust) ran alone in the redo, and its suite still stopped
  at the floor. Its runtime reached 14 GB, plus 2.7 GB of rung copies, on a disk with
  about 22 GiB free when the pair started. Like bruin, its suite needs more disk than this
  machine has. The records stay (D23).
- 17:16: the D23 redo is done. All 20 pairs were run again once. Five still carry 11
  floor-stopped records, and those stay (D23):
  - goose and both bruin pairs: their suites need more disk than this machine has, even
    alone;
  - flow-go and PRQL: stopped while two redo processes ran together, under the second
    amendment.
- 17:17: Claim C resumed under D25 with three workers. No new wave starts after 19:17.
- 17:31: HOW_TO_RUN_LOCALLY verified from a fresh clone of the pushed branch (run at nice 19
  beside the Claim C workers):
  - `just setup`, `just tools` (weave 0.5.2, mergiraf 0.20.0) and `just check` (ruff,
    format, pyright): all clean;
  - `just e2e`: 20 passed in 598 s;
  - `just fixture`, then `just ladder --fixture --no-llm`: 177 cells checked, 0
    mismatches, 3 LLM cells skipped.

  Steps 4 (resolver subagents) and 5 (the real experiment) were not rerun from the clone.
  Their commands and flags were checked to exist with `--help`, and this session ran them.
- 17:40: Claim C pairs pushed free disk to 5.2 GiB (sentry-javascript 7.3 GB, cal.com
  3.7 GB). The shared cargo registry, the one cache still outside per-pair scratch, was
  cleared with no cargo or rustc running (11 GiB free).
