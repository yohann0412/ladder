# Review: F4 structural rungs

Diff read in full: `drivers.py`, `structural.py`, `filecheck.py`, the `rung structural`
command. Acceptance re-run by the main model on the merged tree:
`uv run pytest e2e/test_structural.py -q` -> passed. Observed on the fixture: weave and
mergiraf resolve fx01, fx02, fx08 (parseable) and leave fx03, fx04, fx05, fx07 conflicted.

## What could be wrong

- **Crash looks like a conflict.** git treats any non-zero driver exit as a conflict and
  keeps side A's text without markers, so a crashed driver would read as "conflicted, no
  markers" and the file would look clean. The subagent wraps each driver call in
  `timeout -k 10 120` and logs exits above 1; any log entry makes the rung `error`. Tested
  with fake drivers (exit 101; hang killed at 120 s). Good catch, beyond the spec.
- **Labels.** git 2.43 does not expand `%S/%X/%Y`, so mergiraf's markers carry generic
  labels. Cosmetic; the resolver is told which side is which by the template.
- **Markers already present in the source** (a file that legitimately contains a line
  starting with `<<<<<<<`, e.g. test data for a merge tool) would make every rung
  non-mergeable for that file. Rare; to be checked in the real data by counting
  conflicted files whose base or sides already contain marker lines.
- **Per-file time limit of 120 s** may cut a driver on a very large file; recorded as
  `error`, not as a conflict. The whole merge is capped at 1,800 s.

## What was not tested

- Drivers on languages other than Python (the fixture is Python). The real run is the test.
- add/add handled by the drivers (git passes an empty base).

## What was assumed

- `has_markers` ignores a bare `=======` line outside marker regions (Markdown underlines).
- `parses` is None when the path has no grammar, False when a file with a grammar is absent.
