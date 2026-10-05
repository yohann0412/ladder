# fixtures

`make-fixture.py` builds the `textkit` fixture from scratch with Python's standard
library and git plumbing only:

```
python fixtures/make-fixture.py OUTDIR            # build, then check ids against pairs.json
python fixtures/make-fixture.py OUTDIR --record   # build, then rewrite pairs.json
```

Every git call runs with no user or system configuration, fixed identities and fixed
per-commit dates, so two builds give the same id for every ref.

## Output

- `OUTDIR/repo`: branch `base`, and per scenario n = 1..10 `a/<n>`, `b/<n>` (PR heads),
  `main/<n>` (emulated default branch), `resolved/<n>` (the human resolution, absent for
  fx06), `b-pre/<n>` (B's head before it absorbed or was rebased onto main, fx08 and fx10).
- `OUTDIR/origins/fxNN.git`: a bare origin per scenario that looks like GitHub:
  `refs/heads/main`, `refs/pull/<N>/head`, the PRs' agent-style branch names, and
  `uploadpack.allowFilter` / `uploadpack.allowAnySHA1InWant` for blob-less clones and
  fetch by id over `file://`.
- `OUTDIR/traps/fx07`: a planted wrong resolution (PR A's `textkit/core.py`) and its
  `rationale.json`.
- `OUTDIR/manifest.json`: the same content as `pairs.json`.

`pairs.json` validates against `ladder.schemas.FixtureManifest`; `expected.json` is the
expected outcomes table.

## Scenarios

| id | PRs | merge style | git outcome |
|----|-----|-------------|-------------|
| fx01 | #1/#2 | merge commits | content conflict, core.py (insertions in one gap) |
| fx02 | #3/#4 | merge commits | content conflict, core.py (compatible edits) |
| fx03 | #5/#6 | merge commits | content conflict, core.py (rename vs rewrite) |
| fx04 | #7/#8 | merge commits | modify/delete, helpers.py |
| fx05 | #9/#10 | merge commits | add/add, utils/retry.py |
| fx06 | #11/#12 | merge commits | clean; the merge fails B's test |
| fx07 | #13/#14 | merge commits | content conflict, core.py (intent-drop trap) |
| fx08 | #15/#16 | squash; B merges main first | content conflict, core.py (B's head contaminated) |
| fx09 | #17/#18 | merge commits | clean control |
| fx10 | #19/#20 | squash; B rebased onto main | clean at final heads (rebased, unrecoverable) |
