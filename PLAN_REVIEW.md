# PLAN_REVIEW

A hostile review of `PLAN.md` v1. The reviewer's goal is to find the flaw that
invalidates the results. Every answer names the mechanism that closes the hole and the
acceptance test or audit that proves it. Items marked **[revise]** changed `PLAN.md`.

Evidence used here comes from reconnaissance recorded in `LOG.md` (entries 1-6):
the Zenodo package, AIDev v4, and blob-less clones of the 22 repositories behind the
paper's 23 conflicting pairs in which both PRs merged.

## 1. How could the resolver see the human resolution?

| Path | Is it real? | What closes it | Proof |
|------|-------------|----------------|-------|
| Git history in the workspace | Real if the workspace were a clone or bundle: every later commit, including the merge, would be one `git log --all` away. | D5: the workspace holds three synthetic commits built from three trees; no original commit object is copied. | F2: `git rev-list --all` prints exactly 3 SHAs. **[revise]** F2 also asserts that every object in the store is reachable from those 3 commits (`git cat-file --batch-all-objects --batch-check` count equals `git rev-list --objects --all` count), so an unreachable blob of the resolution cannot hide in a pack. |
| Remote | Real if `origin` were configured; one `git fetch` away. | No remote, no `FETCH_HEAD`, no `objects/info/alternates`. | F2: `git remote -v` empty. **[revise]** F2 also asserts `objects/info/alternates`, `FETCH_HEAD` and `logs/` are absent. An alternates file pointing at the cache would expose every object in it; `git clone --shared` would create exactly that. |
| A file we forgot to strip | Real: the fixture origin has `resolved/<n>` branches; a cache clone holds them. | Workspace is built from trees, not refs. | F2 greps `git log --all -p` and the working tree for a marker string that exists only in `resolved/1`. |
| **The dataset itself: the PR head already contains the resolution** | **Real and common.** In 17 of 18 locatable both-merged conflicting pairs the later PR's final head descends from the earlier PR's merge; in 13 its tree is byte-identical to the human resolution. A resolver that keeps "side b" would score human-equivalent. | D3 rewind. | F1b on fixture scenario 8 (contaminated head) asserts the replay head is the pre-absorption commit and the workspace's `b` tree is not the resolution tree. **[revise]** add a per-pair check in `workspace build`: refuse if the `a` or `b` tree equals the truth commit's tree, recorded as `leak: head equals truth` (run after truth exists, as a post-hoc audit over all pairs). |
| Other pairs' workspaces in the same repository | **Real.** `theopenco/llmgateway` has two pairs; the later pair's base tree contains the earlier pair's merged resolution. | **[revise]** The transcript audit treats any Read, Glob or Grep outside the run's two allowed roots (task dir, workspace snapshot) as a hard violation, not a soft flag. Canonical workspaces live outside every snapshot. | `resolve finalize` e2e uses a recorded transcript with one out-of-root Read and asserts the run is recorded as `protocol_violation`. |
| truth/ | Real if truth extraction ran first. | Truth is extracted only after all planned resolver runs for the pair are finalized; `resolve prepare` refuses when `truth/<pair>` exists. | F6 acceptance (fails loudly before resolver output exists); F5 prepare refuses when truth exists. |
| The repository cache | Weak: Read/Grep on a bare repo sees zlib-compressed objects and ref names, not file content. | Bare, blob-less, outside the allowed roots; any access is a hard audit violation. | Audit rule above; canary strings (R2) planted into three real caches' future history and searched in every resolver output. |
| Network | Real for a general-purpose subagent (it has web tools and a shell). | Instruction plus audit: WebFetch, WebSearch and Bash are hard violations. | Audit e2e (recorded transcript containing a Bash call is rejected). |
| The orchestrator | Real if the main model put anything but the fixed line into the subagent call, or used a context-inheriting fork. | Fixed one-line spawn instruction; never the fork agent type; `prepare` prints the exact line to use. | `LOG.md` records the spawn line once; the audit checks the first user message of each transcript equals the rendered line. **[revise]** |
| PR bodies | Real but narrow: AIDev's body is the body at collection time, after merge, and could mention how conflicts were resolved. | Cannot be stripped without editing the PR's intent. | **[revise]** `prepare` flags pairs whose title or body mentions "conflict", "rebase" or "merge main/master"; reported as a sensitivity cut. |
| Model memory | Real and not closable: public repositories may be in the resolver model's training data, including the merged result. | None possible. | Stated as a limitation in `RESULTS.md`. |

## 2. How could the ladder look better than it is?

1. **Contaminated heads** (above). Without D3, Claim A would be close to 100% for free.
2. **Structural drivers that keep both sides.** A driver can emit both versions of a
   function: it parses, has no markers, and is nonsense. The mergeable rule counts
   duplicate definitions (any name more frequent in the output than in base, A or B is
   not mergeable). Human-equivalence and intent catch the rest. **[revise]** The report
   prints "mergeable but not human-equivalent" per rung so the gap is visible.
3. **Truth that equals one side.** If the human simply took one side, a resolver that
   does the same is "human-equivalent" while dropping the other PR. The report
   cross-tabulates human-equivalent by intent-dropped.
4. **Weak tests.** Claim A never uses tests. Claim B's cell exists to measure exactly
   this. The report counts PR-added test files and assertions per pair.
5. **Failed resolver runs leaving the denominator.** Every failure mode (protocol
   violation, input above cap, no output, malformed rationale) is "LLM: failed" and
   stays in the denominator as not resolved.
6. **Choosing the best rung after the fact.** The oracle ladder (best of all rungs) is
   an upper bound. **[revise]** The decision rule for Claim A uses the practical ladder
   only: git, then weave, then mergiraf, accepting the first mergeable output, else
   llm-post-weave. The oracle ladder is printed next to it, labeled.
7. **Both-merged subset is the easy subset.** Conflicts that were hard may be exactly the
   ones where a PR was abandoned. Claim A's denominator is both-merged by construction.
   **[revise]** The report compares conflicted-file count, type mix and file category for
   the both-merged subset against the whole ladder set, and states the bias.
8. **Lenient equivalence.** Dropping comments counts as equivalent. Accepted: comments
   do not change behavior; stated in the definitions.

## 3. How could the ladder look worse than it is?

1. **Formatting.** AST normalization removes whitespace and comments; token mode removes
   whitespace. **[revise]** Line endings are normalized to LF before any comparison.
2. **Definition order.** A resolver that places two new functions in the opposite order
   from the human is not AST-equal. **[revise]** A secondary metric, "human-equivalent up
   to definition order" (multiset of top-level entities plus equal non-entity remainder),
   is reported beside the strict one. The decision rule uses the strict one.
3. **Human follow-up edits in the truth.** D4 picks the absorption commit to minimise
   them; the rewrite flags (a) and (b) catch the rest; results are shown with and
   without rewrite pairs.
4. **Resolver can only write conflicted files.** When the right resolution needs an edit
   elsewhere (fixture scenario 4), no conflicted-files-only answer can preserve both
   intents. **[revise]** The intent record notes whether the losing side's change lives
   in an entity whose file is not conflicted, and the report counts those separately.
5. **Generated files.** Humans regenerate lockfiles and snapshots; a resolver cannot.
   **[revise]** Every metric is also broken down by the paper's file categories (source,
   config/CI, manifest/lockfile, docs, other).
6. **Flaky tests.** One retry; pass on retry is flaky and excluded with the reason.
7. **Input cap.** Pairs above the cap fail the LLM rung. **[revise]** Cap failures are
   counted and shown separately so a reader can recompute without them.

## 4. Is the runnable subset biased toward small, simple repositories?

Almost certainly: install success falls with repository size and service dependencies.
The report shows, side by side for the runnable subset and the full ladder set:
language, stars, files in the tree, conflicted files per pair, and test count. Every
test-based number carries its own denominator and the sentence "runnable subset only".
AST-based metrics never depend on runnability.

## 5. Can an implementation subagent report success without the test passing?

Ways it could: weaken or skip the e2e test; special-case fixture ids in harness code;
report output from a different tree; hard-code expected numbers; leave the test
passing because it asserts nothing. What closes each:

- Implementation subagents may not touch `e2e/` or `fixtures/expected.json`; the main
  model checks `git diff --stat` for those paths before reading anything else.
- The main model greps the diff for `fx0`, `skip`, `xfail` and literal expected numbers.
- The main model re-runs the acceptance test itself on the merged tree and pastes the
  output into `reviews/<feature>.md`.
- Acceptance tests are written first, committed, and shown failing before delegation;
  each asserts on concrete values, not on "exit code 0" alone.
- The expected outcomes table is written by the main model before the fixture exists;
  for cells that depend on third-party tool behavior (structural drivers) the table
  holds a prediction, and any mismatch is logged in `LOG.md` with both values before the
  table is updated. LLM cells are asserted only where the spec asserts them (scenario 3).

## 6. Which assumption, if wrong, kills the sprint? Verify it first.

1. **The dataset is reachable and carries what F1 needs.** Verified before this review:
   Zenodo reachable, PR numbers present, SHAs derivable over git (23 of 23 probed pairs
   fetched). Remaining: run F1b over all 747 pairs first in Phase 3 and report
   availability.
2. **A leak-proof workspace can be built from a real repository.** Verified on
   `Rello/analytics` 517/518: 3 commits, no remote, conflict reproduced.
3. **New killer found by this review: Claim A may have almost no denominator.** After
   rewinding, only 6 of the 18 locatable both-merged conflicting pairs still conflict;
   4 were rebased, 8 merge cleanly once the absorbed resolution is removed. Claim A on
   the paper set alone is therefore about 6 pairs, which cannot support any verdict.
   **[revise]** (a) F1b runs over all 747 pairs, not only the paper's conflicts, because
   rewinding can also turn a paper-CLEAN pair into a real conflict; the ladder set is
   defined at replay heads. (b) The supplementary sample S moves up: it is cut second
   (after Claim C), not first. (c) `RESULTS.md` must report Claim A as inconclusive if
   the denominator cannot distinguish 90% from the observed rate.
4. **Reconciliation may fail for a reason that is not ours.** `microsoft/vscode-mssql`
   19567/19577 is CONFLICT in the paper but clean at today's final heads with a single
   merge base 6-7 commits away. Either a head moved or the paper's depth-80 shallow
   fetch saw a different base. F3 reconciliation must classify every disagreement
   (head moved, shallow-base artifact, ours wrong) rather than report a net rate only.

## 7. Other weaknesses found

- **Rebased PRs leave the set.** That removes the pairs whose authors linearized history,
  a possibly different population. Count reported.
- **Default-branch assumption.** A PR into a non-default branch gets no truth commit by
  rule (2)/(3). Recorded as "truth unlocated", not guessed.
- **First-parent assumption.** If a PR merged main with main as the first parent
  (`git pull` on main then push), the rewind walks the wrong chain. **[revise]** The
  rewind requires the replay head to be reachable from the PR's final head without
  passing through the default branch's first-parent chain; otherwise "unrecoverable".
- **Time tolerance.** 5 s between `merged_at` and the committer time. Recorded per pair;
  a match outside 2 s is flagged.
- **Truth for the absorption commit includes other default-branch commits** absorbed in
  the same merge. Rewrite flag (b) catches edits outside conflict regions; the report
  shows rates with and without.
- **The paper's unit for type percentages is the `CONFLICT (...)` message, not the marker
  region.** Reconciliation compares messages; marker regions are reported separately.
