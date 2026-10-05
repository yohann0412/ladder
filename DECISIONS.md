# DECISIONS

Short architecture decision records. Each: problem, options, choice, reason.
Newest at the bottom.

## D1. Fixture language

- Problem: the fixture project needs a real test suite and a tree-sitter grammar.
- Options: Python with pytest; TypeScript with vitest.
- Choice: Python package with pytest.
- Reason: Python and pytest are already the harness toolchain, so the fixture's suite
  runs without a Node install step, and the Python grammar is the best-tested
  tree-sitter pack. TypeScript coverage comes from the real data instead.

## D2. Pair source

- Problem: F1 names the GitHub mirror `Quantum535/concurrent-agentic-prsreplication`
  first and Zenodo second.
- Options: GitHub mirror; Zenodo record 21186464; derive from AIDev.
- Choice: Zenodo record 21186464 (`replication_package.zip`, md5
  `59a99c9cf58793957806a7fa5e712f8f`). Titles, bodies, states and `merged_at` come from
  AIDev v4 (`hao-li/AIDev`, `pull_request.parquet`, `repository.parquet`).
- Reason: the GitHub web host and REST API return 403 from this environment's egress
  policy, Zenodo returns 200. The package has PR numbers but no SHAs, merge bases or
  merge commits, so those are derived by fetching `refs/pull/N/head` over git, which
  the proxy allows. Both sources are CC-BY-4.0; small extracts are vendored under
  `data/source/` with attribution so `ladder pairs load` and its test run offline.

## D3. Replay at rewound heads, not at final heads

- Problem: reconnaissance on the paper's 23 conflicting pairs where both PRs merged:
  for 18 the merge commits could be located, and in 17 of those the later-merged PR's
  final head already contains the earlier PR's merge (the agent or human merged the
  default branch into the PR). In 13 of them the final head's tree is byte-identical to
  the human resolution. Replaying final heads would hand the resolver the answer as
  "side b" (or "side a").
- Options: replay final heads (as the paper did); drop contaminated pairs; rewind the
  contaminated head to its last commit before the absorption.
- Choice: rewind (definition in `PLAN.md` 5.1). The git rung runs on final heads only to
  reconcile with the paper; every ladder metric uses replay heads.
- Reason: dropping would leave about one both-merged pair. Rewinding reconstructs the
  conflict the human actually resolved. Rebased PRs cannot be rewound and leave the
  set with a recorded reason.

## D4. Truth commit

- Problem: the spec says "PR B's merge commit, or the first default-branch commit after
  both merged, whichever the replay study used". The replay study used neither; it
  never looked at merge commits.
- Choice: for a rewound pair, the absorption merge commit on the later PR's branch; for
  a non-rewound pair, the later PR's merge commit on the default branch (rule in
  `PLAN.md` 5.1).
- Reason: the absorption commit is where the resolution was actually typed, so it
  carries the fewest unrelated edits. Using the default-branch merge commit for a
  rewound pair would add every later commit on that PR to the truth.

## D5. Workspace from synthetic commits

- Problem: the resolver must see exactly base, a and b.
- Options: `git bundle` of the three commits (drags their ancestry along); re-create
  three commits from the three trees.
- Choice: copy only the tree and blob objects of the three trees with
  `git rev-list --objects | git pack-objects | git index-pack`, then create three new
  commits with fixed author, committer, date and messages `base`, `pr-a`, `pr-b`.
- Reason: no original commit object, message, author or parent reaches the workspace,
  so there is no history to walk. `git rev-list --all` must print exactly 3 SHAs.
  Submodule gitlinks are preserved as tree entries. Missing blobs in the partial-clone
  cache are fetched explicitly by SHA before packing.

## D6. Resolver isolation is enforced by audit, not by tool restriction

- Problem: the resolver must have read-only access to one workspace, no network, no
  shell. A tool-restricted agent definition is not loaded by the running orchestrator
  (verified: an agent type defined after session start is "not found").
- Options: a restricted agent type (unavailable mid-session); an unrestricted
  general-purpose subagent with instructions only; instructions plus a mandatory
  post-run audit of the subagent's tool-call transcript.
- Choice: general-purpose subagent, fixed instructions, and `ladder resolve finalize`
  audits the transcript: any tool other than Read, Glob, Grep, Write (plus the
  hand-back call) is a hard violation; any path under the cache, truth, the canonical
  workspace or another pair is a hard violation; a hard violation records the run as
  "LLM: failed (protocol violation)" with no re-run. A resolver agent definition for
  harnesses that support restriction is kept at `resolver/AGENT.md`.
- Reason: the audit makes the rule checkable after the fact; no API key is involved.

## D7. Resolver inputs are files, the prompt is a rendered template

- Problem: the spec puts base, A, B and marker versions of every conflicted file in the
  prompt. Some pairs have dozens of conflicted files; the orchestrator would have to
  re-type megabytes into each subagent call.
- Choice: `ladder resolve prepare` renders `resolver/PROMPT.md` into
  `<task>/PROMPT.md` with the PR titles and bodies and the file list inline, and writes
  the four versions of each file next to it; the orchestrator spawns the subagent with
  one fixed line: "Read <task>/PROMPT.md and follow it exactly." The template text and
  the line never vary per pair.
- Reason: identical information, no transcription by the orchestrator, no per-pair
  variation.

## D8. Resolver model

- Choice: the orchestrator's default subagent model, the same for every run. The model
  identifier is not written into repository artifacts.
- Reason: one fixed model across the run; the protocol is about the rung, not a model
  comparison.

## D9. Third-party code is not committed

- Problem: workspaces, truth and resolutions contain code from repositories under
  many licenses.
- Choice: they live under `work/` (git-ignored). Committed results contain metrics,
  paths, entity names, SHAs and content hashes only.
- Reason: licensing; hashes still let anyone check a reproduction.

## D10. Git configuration isolation

- Choice: every local git operation runs with `GIT_CONFIG_GLOBAL=/dev/null`,
  `GIT_CONFIG_NOSYSTEM=1`, `commit.gpgsign=false` and explicit identity and dates.
  Network operations (clone, fetch) keep the user's configuration so proxies work.
- Reason: this environment's global config signs commits through a helper; signatures
  and user config would make fixture hashes and merges machine-dependent.

## D11. Structural driver versions

- Choice: weave 0.5.2 via the npm wrapper `@ataraxy-labs/weave` (fallback `cargo install
  weave-cli`); mergiraf 0.20.0 via `cargo install --locked` (fallback GitHub release
  binary). Installed into `.tools/` by `just tools`.
- Reason: both install paths were verified in this environment before planning.

## D12. Post-structural LLM input comes from weave

- Choice: llm-post-weave runs on weave's partial output for pairs weave leaves
  conflicted. No llm-post-mergiraf.
- Reason: weave is the structural rung the cut order keeps; one post-structural
  condition keeps the resolver budget for the double run and the supplementary set.

## D13. Conflict style

- Choice: `merge.conflictStyle=diff3` for every marker file.
- Reason: the base section is what a careful human reads; the resolver also gets the
  base file in full, so the choice adds no information it would not otherwise have.

## D14. CLI and test framework

- Choice: `typer` CLI with `rich` output; e2e tests are pytest functions that call the
  installed `ladder` executable through `subprocess.run`.
- Reason: pytest is only the runner; no test imports harness code.

## D15. Supplementary sample S (pre-registered before any ladder result exists)

- Problem: after rewinding, the paper set yields about 6 conflicting pairs with a human
  resolution; Claim A's 90% rule cannot be evaluated on 6 pairs.
- Choice: a supplementary sample drawn from AIDev v4 by this rule, fixed now:
  1. Candidate pair: two PRs of the same repository in `pull_request.parquet`, both with
     `merged_at`, whose intervals [created_at, merged_at] overlap, whose changed-file
     sets (union of `filename` over the PR's rows in `pr_commit_details.parquet`)
     intersect, and which are not already a pair of the paper set.
  2. Repositories are sorted by full name and shuffled with `random.Random(42)`. Within
     a repository, candidates are ordered by (later PR's created_at, smaller number,
     larger number); the first candidate is taken. One pair per repository.
  3. Pairs are processed in that order through `pairs resolve` and the git rung at
     replay heads. A pair enters S when it conflicts at replay heads and its truth
     commit is located. Processing stops at 60 such pairs or when repositories run out.
  4. Every attempted candidate and its outcome is recorded; the attrition is reported.
  5. PR A is the PR created first.
- Reason: same co-activity notion as the paper, plus file overlap to raise the conflict
  yield, plus the both-merged condition Claim A needs. Results on S are reported
  separately from the paper set and pooled.

## D16. Resolver input cap

- Problem: one paper pair has 905 conflicted files; a subagent cannot read and rewrite
  that much, and a few pairs have multi-megabyte generated files.
- Choice: a task is `input_cap` (an LLM failure, kept in denominators) when it has more
  than 20 conflicted files, any single file version above 200,000 bytes, or all versions
  together above 600,000 bytes.
- Reason: keeps every run within one subagent's working budget; the report counts cap
  failures separately so a reader can recompute without them.

## D17. Where record models live

- Problem: CONTRIBUTING said every on-disk record lives in `schemas.py`, but several lanes
  needed module-private formats (vendored AIDev rows, resolver task manifests, canary log,
  run log, expectation report) while `schemas.py` was protected from them.
- Choice: `schemas.py` holds the contracts between commands; module-owned formats stay with
  their module, still as pydantic models.
- Reason: a shared contract file that every format must pass through creates coupling with no
  benefit for formats only one module reads and writes.

## D18. Glob audit rule (pilot correction, before any real resolver run)

- Problem: the audit treated a Glob without a `path` parameter as a violation even when its
  pattern was an absolute path inside the task directory, which the prompt explicitly allows.
  Found on fixture fx05 (`LOG.md` entry 15).
- Choice: a pathless Glob passes when its pattern is absolute, contains no `..` (also inside
  braces), and its fixed prefix (before the first glob character) is inside the task
  directory, also after resolving symlinks. Everything else in PLAN.md section 8 is unchanged.
- Reason: the rule's intent is "every read names a place inside the task directory"; the
  pattern does. Fixed before the real runs, so every real run is audited by one rule.

## D19. Claim C run order (before any Claim C result)

- Problem: 918 pairs merge cleanly at replay heads, in 795 repositories. Classifying
  runnability and running three suites per pair may not finish for all of them, and Claim C
  is first in the cut order. A stopping point chosen after seeing results would bias the
  rate.
- Choice: pairs are attempted in the order of `sha256("42:" + pair_id)`, written to
  `data/claimc-order.txt` before the first Claim C run, in waves through
  `ladder run <pairs> --prune`. Stopping happens only at a wave boundary, only for a
  resource reason; the index and reason go into `LOG.md`. Pairs after it are reported as
  `not attempted: cut`. A merge that breaks dependency installation while A and B install
  is reported as its own count and is not part of the rate.
- Reason: a seeded random prefix is an unbiased sample of the population whatever its
  length, and the order is fixed before any outcome exists. Full argument in
  `reviews/protocol-phase4.md`.

## D20. Resolvers that read their own output (before any truth extraction)

- Problem: in waves 1 and 2, 8 of 60 finalized resolver runs failed the audit, every one
  for the same reason: after writing, the resolver used Read or Grep on a file in its own
  output directory to check what it wrote. The prompt forbids reads outside the task
  directory, the output directory is outside it, and the audit applies the written rule
  correctly. These reads cannot leak the human resolution, because the output directory
  holds only what the run itself wrote.
- Choice: the protocol stays as written. Those runs are `failed: protocol_violation` in
  every primary number, nothing is re-run, and the template does not change. The report
  states how many LLM runs failed only because of reads under their own output directory.
  It also gives the Claim A verdict under a best-case bound, where every such pair counts
  as human-equivalent. If the bound would change the verdict, the outputs of those runs
  (already ingested by `finalize`) are scored as a separately labeled sensitivity cut;
  otherwise the bound is enough.
- Reason: changing the rule after seeing which runs break it would be a post-hoc protocol
  change. Reporting the bound shows a reader how much the rule costs without letting it
  move the primary result. Decided before any truth file exists.

## D21. Resolver runs hit by a full disk

- Problem: during wave 6 preparation, one pair (Unity-Technologies__com.unity.toonshader__492-497,
  a 1.6 GB workspace copied once per rung) filled the disk while wave 5 resolvers were
  running. Four runs could not write their output, and their transcripts were cut off
  mid-line: synth-inc__onit__184-186 (both rungs) and wandb__openui__235-237 (both rungs).
- Choice: the four runs are finalized as written: `failed`, with `audit_impossible`
  (truncated transcript) or malformed output. None is re-run. The report lists them under
  their own cause, "infrastructure: disk full", taken mechanically from the truncated
  transcripts. As in D20, it also gives the Claim A verdict under a best-case bound in which
  both pairs count as human-equivalent. From now on, pairs are prepared one wave at a time,
  only while no resolver is running, with at least 10 GiB free. The oversized pair is
  prepared last, alone.
- Reason: the rule is that a failed resolver is recorded as failed. A re-run chosen after the
  fact would weaken that rule even when the cause is outside the resolver. These failures
  count against the LLM rung, so recording them can only make Claim A look worse, never
  better.

## D22. Overlapping preparation and resolvers for the double run

- Problem: preparing the 30 double-run pairs stops at the 10 GiB floor after a few pairs,
  and settled pairs can only be pruned once their run 2 is done. Keeping D21's "no
  preparation while a resolver runs" would mean one small batch at a time.
- Choice: for the double run only, resolvers are started as soon as their task is
  prepared, while preparation continues. The 10 GiB floor still applies before each pair.
  Each of these pairs takes about 1 GB of working copies.
- Reason: D21 protects resolver writes from a full disk. The floor checked before each
  pair, together with the small pairs, gives the same protection. Resolver outputs are
  kilobytes.

## D23. Test runs stopped by the free-disk floor are redone once (before any redo result)

- Problem: the shared caches and leftovers of other suites filled the disk several times
  (LOG 21). Some installs and suites were then stopped by the 3 GiB floor and recorded as
  `exceeds_cap`, or as an error with "free disk below the … floor" in their detail. That
  stop says nothing about the pair. It depends only on what else happened to be running.
  By 11:55, 18 records in 8 pairs carried it:
  - runnability and scores of 6 ladder pairs;
  - Claim C of `PRQL__prql__5286-5287` and `bruin-data__bruin__733-735`.
- Choice: every runnability, score or Claim C record whose stored outcome contains the
  free-disk floor phrase is an infrastructure failure. The rule is the same for every
  such record, whatever else it says.
  - When the final pass ends, for each such pair: delete its runnability record, all its
    score records and its Claim C record, then run the pair again with at least 20 GiB
    free and nothing else running.
  - Each pair is redone once. If the redo stops at the floor again, that record stays.
  - The redo also covers any record that stops at the floor later in this experiment.
  - The list of redone pairs goes in LOG.md. The report counts how many records the rule
    replaced.
  - This replaces the earlier LOG note that PRQL would not be run again. That note treated
    a disk stop as an outcome.
- Reason: what triggers a redo is the infrastructure phrase in a record, not whether its
  tests passed, failed or were runnable. So the redo cannot be steered toward an outcome.
  Leaving these records would drop pairs from the tests-based denominators and from Claim C
  for a cause that has nothing to do with them. Resolver runs are not covered: D20 and D21
  still apply to them.
- Amendment (14:20, before any redo result existed): the start condition is now 15 GiB free
  before each redone pair, not 20. At 14:10 the redo began with 20 GiB free, and its first
  pair waited because free space had drifted to 18.7 GiB. 15 GiB leaves 12 GiB above the
  3 GiB floor, more than twice the largest pair's runtime (kanister, about 5.6 GB). Still
  only one redo process runs, alone.

## D24. Reporting Claim B next to the calibration result (after calibration, before the final report)

- Problem: Claim B's fixed rule is computed from the harness's intent-dropped verdict on
  llm-raw outputs. The calibration of PLAN 5.6 read 20 intent-dropped verdicts (seed 42).
  The reviewer agreed with 12 of the 14 on git and structural outputs, where the flagged
  change sat in an unresolved conflict. On LLM outputs the reviewer agreed with 0 of 6. In
  each, the resolution combined both sides or kept an equivalent implementation of the
  same change, and exact line containment reported a drop. Claim B is about LLM outputs,
  and the plan does not say how calibration bears on a verdict.
- Choice:
  - The pre-registered verdict is reported exactly as computed.
  - The Claim B statement also gives the reviewer's agreement on LLM intent-dropped
    verdicts, with its Wilson interval. It then gives the intent-dropped rate that would
    remain if the metric's precision on LLM outputs were the upper end of that interval
    (the interval's upper end times the rate). If that rate is below the 15% threshold,
    the statement says calibration does not support the verdict.
  - The calibration section shows agreement separately for LLM and for git or structural
    outputs.
  - No record changes. The intent metric is not re-tuned after seeing the sample.
- Reason: changing the verdict rule after seeing results would add a forking path, and
  leaving out the calibration would overstate the claim. Reporting both lets a reader see
  that the verdict rests on a metric whose precision on LLM outputs was low in the only
  direct check made.
- Also recorded here: the code takes Claim B's intent-dropped share over llm-raw outputs
  that exist (59/165 before the D23 redo), while PLAN section 1 says "of conflicting
  pairs" (59/224). Both are above 15%, so the verdict does not depend on the choice. The
  report keeps the code's denominator and the results review states the difference.
- Second amendment (14:45, while the first redo pair was still running): up to two redo
  processes, on disjoint repositories. One takes the ten large Go pairs one at a time
  (`work/d23-go.txt`). The other takes the remaining nine (`work/d23-rest.txt`), so two of
  the largest pairs never run together. Each process still waits for 15 GiB free before
  each pair, and no other experiment process runs. Reason: time. One pair runs up to seven
  suites under ten-minute caps, so 20 pairs one after another would take most of a day.
  Since F8f, every temporary file and package cache of a pair lives in its runtime, so a
  pair's disk use is bounded and freed when it is pruned. The split depends only on
  language and size, not on any redo outcome.
- Note on the second amendment (14:58): it did not hold. The "rest" group included Rust
  pairs (PRQL, Cap, goose) whose builds are as large as the Go ones. While flow-go was
  running in the Go process, PRQL's Claim C redo stopped at the floor again at A and at
  the merge. As D23 says, that record stays, so PRQL remains excluded for the disk-floor
  cause. That second stop came partly from the concurrency this amendment allowed. From
  14:58 the remaining eight "rest" pairs run alone, after the Go process has finished.

## D25. Claim C time budget (before any Claim C result after wave c02)

- Problem: by 15:00, Claim C had attempted 26 pairs of 918 and decided none. Only about
  one repository in twenty has a suite this harness can run green at base. At one to two
  minutes per pair, the full order would take more than a day on this machine, and
  Claim C is first in the cut order (PLAN section 6).
- Choice:
  - Once the D23 redo has finished, Claim C waves resume from c02 in D19 order with three
    workers. Each worker takes the next wave in order and always finishes the wave it has
    started, so the completed waves form a prefix of the order.
  - No worker starts a new wave more than two hours after the resumption. When the last
    started wave is done, Claim C stops. The cut is the last wave of that prefix, and the
    reason is the time budget (a resource reason, as D19 requires).
  - Each pair still waits for 8 GiB free before it starts.
  - The cut index and the time go into LOG.md. Every later pair is reported as
    `not attempted: cut`.
- Reason: the budget is fixed before any further outcome exists, and the order was fixed
  before any Claim C result, so the attempted pairs remain a seeded random sample of the
  pool. A decided count this small means the rate cannot be compared with the human base
  rate, and the report must say so.
- Amendment to D25 (18:20, for disk, not for any outcome): three workers kept putting
  very large repositories on the disk at once (cal.com, openops, coder, tldraw, vector),
  and their records stopped at the free-disk floor. All workers were stopped at 18:20 and
  Claim C continues with one worker. The waves are still taken in D19 order, starting with
  the earliest incomplete wave, so the completed waves remain a prefix. Records already
  written are kept. Pairs that were interrupted had no record yet and are run by the
  single worker. The deadline is unchanged: no new wave after 19:17. Floor-stopped records
  are redone once, alone, under D23 after the waves stop.
