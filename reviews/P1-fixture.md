# Review: P1 fixture repository

Diff read in full: `fixtures/make-fixture.py` (1,327 lines), `fixtures/pairs.json`,
`fixtures/README.md`. Acceptance re-run by the main model on the merged tree:
`uv run pytest e2e/test_fixture.py -q` -> `1 passed in 9.24s`. No protected file touched.

## What could be wrong

- **Fixture shaped around the tools.** To meet the spec's "fx01 resolves under both
  drivers; fx03 stays conflicted under both", the builder changed the edits until the
  pinned tool versions behaved that way (fx01: B's new function renamed so both tools
  emit the human's definition order; fx03: B's body uses `replace(";", ",")` because
  mergiraf otherwise resolved it correctly). The scenarios still mean what the spec says,
  but they encode tool behavior of weave 0.5.2 / mergiraf 0.20.0. A version bump may flip
  them; the expected table will then fail loudly, which is the right failure.
- **Predictions that were wrong.** weave resolves fx02 (predicted conflicted) and both tools
  resolve fx08 at replay heads (predicted conflicted). Logged in `LOG.md` entry 8 with both
  values before `expected.json` was updated; basis set to `observed`.
- **fx06/fx09 truth.** `resolved_branch` is null for fx06 although the harness will locate
  a truth commit (B's merge commit). The F1b test compared truth to `resolved`; corrected to
  compare non-rewound truth to B's located merge commit.
- **Agent-style branch refs** exist in every origin, which is what exercises the
  "default-branch first-parent" contamination rule. Without the fix in `PLAN.md`
  (revision 10), fx01-style true merges of PR commits made after the other PR merged would
  have been mis-flagged; the fixture does not contain such a case (B's commits predate A's
  merge in every merge-flow scenario). Not tested by the fixture: noted below.

## What was not tested

- A true-merged PR with own commits after the other PR merged (the false-contamination case
  the rule revision addresses).
- A PR targeting a non-default branch; criss-cross histories; submodules; binary files;
  CRLF files.
- `--record` overwriting a committed manifest that differs (exercised once by the builder).

## What was assumed

- Python 3.10+ for the fixture package; pytest is supplied by the harness venv.
- Each PR's tests live in new files so tests never add conflicts of their own.
- `resolved/10` points at B's squash commit (the commit the subject_time rule finds).
