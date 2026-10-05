# Protocol review before Phase 4 (Claim C)

Claim C asks how often two agent PRs that merge with no textual conflict each pass the test
suite alone but fail it together. The rule is in PLAN 5.5: A passes, B passes, the clean
merge fails, after the flaky rule (`claimc.judge`). This review lists every way the rate
could come out wrong in either direction, and fixes the run order before any Claim C
result exists.

## Population and order (D19)

- Population: every pair whose git rung at replay heads is `clean`. There are 918 such
  pairs (paper and supplementary sample S) in 795 repositories. No pair has a runnability
  or Claim C record yet.
- Order: pairs are sorted by `sha256("42:" + pair_id)` and written to
  `data/claimc-order.txt` before the first Claim C run. Pairs are attempted strictly in
  that order, in waves through `ladder run <pairs> --prune`.
- Stopping: Claim C is first in the cut order. If it is cut, it stops at a wave boundary for
  a resource reason (disk, attempts), never because of a rate. The stopping index goes
  into `LOG.md` with the reason, so the attempted pairs are a seeded random prefix of the
  population. Pairs after the stop are listed as `not attempted: cut`.

## Ways the rate could be too high

| # | Mechanism | What the protocol does |
|---|-----------|------------------------|
| H1 | Flaky tests: the merge run fails by chance | A failing run is re-run once; a pass on the retry marks the run `flaky` and excludes the pair (`testrun.run_suite`) |
| H2 | Network or registry state changes between the A, B and merge runs (tests and installs have network through the proxy) | The base environment is reused for every tree whose manifests match base, so most runs install nothing. A merge that installs again because of new manifests is labeled in the detail. Every positive is read by hand and its failing tests are listed in the report |
| H3 | Order effects: the merge runs last, in a warm or dirty environment | Each tree is exported fresh into its own directory; only the dependency environment is shared, and it is shared by A and B too |
| H4 | A test file added by one PR fails on the other PR's code | Counted as a positive. That is the semantic conflict the claim is about, not an artifact |

## Ways the rate could be too low

| # | Mechanism | What the protocol does |
|---|-----------|------------------------|
| L1 | Only repositories the adapters can run (Python, Node, Go, Rust; no services, secrets or GPUs) enter the denominator | Runnability rate and reasons reported for the whole attempted set; a bias table compares runnable and attempted pairs by language and change size |
| L2 | A repository whose suite already fails at A or B is excluded ("fails alone") | Counted and reported. The definition is pre-registered and stays as written; a per-test variant is not computed |
| L3 | A merge that breaks dependency installation (for example, two inconsistent lockfile edits) is recorded as `error` at merge and excluded | Reported as a separate count, "merge breaks install while A and B install", next to the rate and never added into it |
| L4 | Suites capped at 600 s or installs capped at 900 s are excluded | Counted by cause |
| L5 | Weak test suites cannot detect a semantic conflict | Not closable. The rate is a lower bound on semantic conflicts and measures only what a merge queue running the same suite would catch |
| L6 | Replay heads were rewound for contaminated pairs, so the tested trees are earlier versions of the PRs | Same heads as Claims A and B; the rewound count is reported |

## Comparing with the human base rate

The base rates in the task (about 1% for small teams, up to 12.5% for large teams) count
merges that broke the build after passing CI alone. Our unit is a concurrent pair that
merges cleanly, so the comparison is rough. The report states the rate, its Wilson 95%
interval and its denominator. If the rate is at or above the base rate, the report says
that a merge queue already catches these failures, so only automatic repair is left open.
If the rate is 0 with an upper bound below 1%, the claim is reported as falsified as a
problem worth solving (PLAN section 1).

## Safety

Claim C runs untrusted repository code (installers and tests) inside this container with
network access. That is acceptable in a disposable container. `HOW_TO_RUN_LOCALLY.md` must
say so plainly and recommend a VM or container.

Tests run with the container's own `HOME`, so a suite can write anywhere this user can,
including the folder that holds resolver transcripts. Claim C runs while resolver waves are
still in progress. A suite that changed a transcript would make that run fail the audit
(malformed or violating), which counts against the LLM rung, never for it. Every wave's
transcripts are collected and audited as soon as the wave settles.
