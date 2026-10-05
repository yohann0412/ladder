# Protocol review before Phase 3 (Claims A and B)

Every way the Phase 3 numbers could come out wrong *in a claim's favor*, and what the
protocol does about each. Claim A is favored by anything that makes resolutions look
human-equivalent; Claim B by anything that makes intent loss look common. The two pull in
opposite directions, so both lists matter.

## In Claim A's favor (the ladder looks better than it is)

| # | Mechanism | What the protocol does | Where it is checked |
|---|-----------|------------------------|---------------------|
| A1 | PR head already contains the human resolution (17 of 18 locatable both-merged conflicting pairs in reconnaissance) | Replay heads rewound past the absorption (D3); post-hoc `leak_head_equals_truth` audit on every truth record; rate reported | F1b, F6, report |
| A2 | Resolver reads the human resolution from history, a remote, the cache, another pair's workspace in the same repository, or `truth/` | Three synthetic commits only; verify before every prepare; truth extracted only after all planned runs settle; transcript audit makes any out-of-root read a hard failure; canary strings in three real caches' future history, searched in every output | F2, F5, F6, canary |
| A3 | Human resolution equals one side, so a one-sided resolver "matches" while dropping the other PR | Intent is scored independently of truth; the report cross-tabulates human-equivalent by intent-dropped | F7, F9 |
| A4 | Structural drivers emit both sides (valid nonsense) | Mergeable requires no new duplicate definitions; "mergeable but not human-equivalent" printed per rung | F7, F9 |
| A5 | LLM failures dropped from the denominator | Failures (cap, violation, no output, malformed) stay in the denominator as not resolved; shown by cause | F5, F9 |
| A6 | Best rung picked after the fact | Decision rule uses the practical ladder only; oracle ladder labeled as an upper bound | F9 |
| A7 | Truth exists only for both-merged pairs, which may be the easy conflicts | Bias table: conflicted files, types and categories of the both-merged subset vs the whole ladder set | F9 |
| A8 | The resolver model saw the merged code in training (public repositories) | Not closable; stated as a limitation in `RESULTS.md` | report |
| A9 | PR bodies written after the fact describe the resolution | `pr_text_flags`; sensitivity cut without flagged pairs | F5, F9 |
| A10 | Supplementary sample tuned to easy pairs | Rule fixed in D15 before any result; stopping depends on git only | D15 |
| A11 | The orchestrator nudges or re-runs resolvers | One fixed spawn line, audited; no re-runs; outputs never edited | F5 audit, D6 |
| A12 | Lenient equivalence (comments ignored) | Accepted and stated; whitespace-only and comment-only differences are not behavior | PLAN 5.3 |

## In Claim B's favor (intent loss looks more common than it is)

| # | Mechanism | What the protocol does | Where it is checked |
|---|-----------|------------------------|---------------------|
| B1 | Containment uses normalized lines, so a resolver that re-wraps a statement across lines "loses" it | Calibration: the main model reads 20 random intent-dropped verdicts and records agreement before computing totals; agreement reported next to the rate | 5.6, calibration.json |
| B2 | Whole-file entity for files without a grammar (CHANGELOG, YAML) turns any rewording into a drop | Intent drops broken down by file category; calibration sample covers them | F9 |
| B3 | The resolver may write only conflicted files, so a needed edit elsewhere is impossible | Drops where the loser also changed non-conflicted files are counted separately | F7 |
| B4 | Tests pass because the runnable subset is small and easy | Tests-based cells only on runnable repositories, with their own denominators and a bias table | F8, F9 |
| B5 | Flaky tests turn passes into failures or the reverse | One retry; flaky outcomes excluded with the reason | F8 |
| B6 | Entity identity breaks on renames or duplicate names | Keys include occurrence index; renames show as delete+add and must match the renaming side | F7 |

## Ordering commitments for Phase 3

1. `pairs resolve --all` and both git rungs on all 747 paper pairs, then reconcile with the
   paper and log every disagreement class in `LOG.md` before any structural or LLM rung.
2. Structural rungs, then resolver plans for every ladder pair, then the double-run sample,
   then every resolver run. No `truth extract` before `resolve pending` is empty for all
   pairs of that sample.
3. Truth, runnability, scoring, calibration (verdicts recorded per item before any total is
   computed), report.
4. Supplementary sample S only after the paper set has gone through steps 1-2, using the
   same commands.
