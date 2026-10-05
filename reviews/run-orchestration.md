# Review: `ladder run` orchestration and `resolve collect`

Diff read: `orchestrate.py` (in full), `pairsteps.py`, `prune.py`, `diskspace.py`,
`runlog.py`, `expect.py`, `expect_view.py`, `run_cli.py`, `run_view.py`,
`resolver_collect.py`, the `build_recorded` extraction in `workspace.py`, the justfile.
Acceptance re-run by the main model on the merged tree: `just e2e -q` -> `15 passed`
(every acceptance test, including `test_run_fixture.py` and `test_report.py`); ruff and
pyright clean. On the fixture without resolvers: 177 cells checked, 0 mismatches, 3 LLM
cells skipped.

## What could be wrong

- **Ordering vs. the Phase 3 protocol.** Without `--stop-before-truth`, a pair whose runs are
  settled proceeds to truth while other repositories' pairs still have pending runs. That is
  safe for leakage (truth waits while a same-repository pair is pending, and `prepare`
  refuses after any same-repository truth), but the Phase 3 protocol commits to all
  resolver runs before any truth; the real run uses `--stop-before-truth` for that.
- **Error records are not retried** (a git rung `error` counts as present). Reconciliation
  had none; the real run will be checked for `error` records before scoring.
- **Rebuilt copies are compared with their records**; a disagreement fails the step rather
  than silently overwriting a record. Good.
- **Records outside `schemas.py`**: `RunLog`, `ExpectationReport` (and earlier lanes'
  `TaskManifest`, `CanaryLog`, vendored-extract rows) are module-owned formats. Decided to
  keep them with their modules (DECISIONS D17); CONTRIBUTING amended.

## What was not tested

- `--jobs` greater than 1 on real repositories under disk pressure.
- `resolve collect` with transcripts from more than one session directory.

## What was assumed

- A cache is deleted only when no pair of that repository is in the ladder set.
- `--expect` is skipped while resolver runs are pending.
