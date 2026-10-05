# Review: F8 runnability classifier, test adapters, Claim C runner

Diff read in full (2,124 lines: `adapters/{base,python,node,go,rust}.py`, `detect.py`,
`manifests.py`, `procrun.py`, `reasons.py`, `runnable.py`, `runtime.py`, `testreports.py`,
`testrun.py`, `trees.py`, `pairsuite.py`, `claimc.py`, `suites_cli.py`, `suites_view.py`).
Acceptance re-run by the main model on the merged tree:
`uv run pytest e2e/test_runnable.py e2e/test_claim_c.py -q` -> `2 passed`.
Real repositories tried by the subagent: jest (yarn 4), vitest (pnpm), mocha (npm), Go x2,
Python (uv), Rust all runnable; cobra fails at base as root, tomlkit build fails, a
`node --test` project has no supported runner.

## What could be wrong

- **Untrusted code runs as root with network access.** Install scripts and test suites of
  real repositories execute on this machine. Inherent to F8's spec; mitigated only by caps
  and process-group kills. Stated in `HOW_TO_RUN_LOCALLY.md` as a warning.
- **Root-only failures** (e.g. permission tests) make some suites fail at base; classified
  `other: suite fails at base`, which is honest but means the runnable subset excludes
  repositories that would pass as a normal user.
- **Runner coverage.** Only jest, vitest, mocha (Node), pytest, `go test`, `cargo test`.
  `node --test`, ava, tap, karma, unittest-only Python projects are "other".
- **Environment reuse** keys on byte-identical dependency manifests vs base; a lockfile-only
  change triggers a full reinstall (more `error` outcomes if installs fail on a side).
- **Wrong holder directory** (`rung_dir(pair, "git")` instead of `"git-replay"`) and
  missing-workspace errors deep in git: sent back as a follow-up.
- **Flaky base counts as runnable**; flaky later runs are excluded from metrics.

## What was not tested

- Monorepos with workspaces (npm/pnpm/yarn workspaces) beyond the hand checks.
- Python projects needing a different interpreter version than the default.
- Suites that need a display, a browser or GPU.

## What was assumed

- Caps: install 900 s per step, suite 600 s (`timeout_s`), kill grace 10 s.
- Fallback attempt per ecosystem as listed in the subagent's report (non-editable or
  unpinned Python; `--legacy-peer-deps` npm; unfrozen pnpm/yarn; `GOFLAGS=-mod=mod`;
  `cargo update`).
