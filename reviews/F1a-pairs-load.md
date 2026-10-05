# Review: F1a pair loader

Diff read in full (`aidev.py`, `extracts.py`, `sources.py`, `pairload.py`, `replaycsv.py`,
`parquet.py`, `pairsummary.py`, `pairs_view.py`, `download.py`, `zenodo.py`,
`attribution.py`, the two-line `cli.py` registration) plus the vendored `data/source/`.
Acceptance re-run by the main model on the merged tree:
`uv run pytest e2e/test_pairs_load.py -q` -> `1 passed`. No protected file touched.

One round sent back: PRs whose repository was renamed were taken from the stale v3 snapshot
although revision main has them under the new name. Fixed by looking up the PR id in v3 and
taking main's row by id (27 of 38 moved to main; both-merged counts unchanged: 220 of 747,
24 of 167 CONFLICT).

## What could be wrong

- **11 PRs come from v3** because main has no row at all for them; their state may be stale.
  The both-merged count (24 conflicting pairs, one more than the 23 in `LOG.md` entry 2)
  includes `sam-goodwin__alchemy__239-240` from v3 data.
- **AIDev `merged_at` is a snapshot**: main and v3 disagree on state or merged_at for 113 of
  1,431 shared PRs, so a PR closed at snapshot time may have merged later. F1b's merge-commit
  locator uses git history, not AIDev, for the commit, but uses AIDev's `merged_at` for time.
- **pyright relaxations** in `parquet.py` (pyarrow has no stubs). Contained to one file whose
  output is validated with pydantic.
- **No retry** on downloads; an interrupted Hugging Face download (seen once) fails the
  command. Acceptable because the extracts are vendored.

## What was not tested

- `fetch-sources` end to end inside the test (network); it was run once by the subagent and
  once more to check byte-identical output.
- `--fixture` mode is only exercised through later tests' `fx` fixture.

## What was assumed

- The CSV's repository names are the keys; the current name is kept in `repo_now`.
- Fixture PR `state` is "closed" when the manifest gives a close or merge time.
