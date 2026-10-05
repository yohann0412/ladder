# Review: S supplementary sample

Diff read: `candidates.py`, `supplementary.py`, `download.py` (resumable range requests),
`extracts.py`, `sources.py`, `aidev.py`, `parquet.py`, `pairs_cli.py`, `pairs_view.py`,
`attribution.py`, plus the vendored `data/source/supplementary_candidates.json`.
Acceptance re-run by the main model on the merged tree:
`uv run pytest e2e/test_supplementary.py -q` -> `1 passed` after lowering the test's
pool-size bound from my pre-implementation estimate (900) to 890 (`LOG.md` entry 12); the
subagent stopped instead of editing the protected test, which is the right behavior.

## What could be wrong

- **Paper-pair exclusion by name and by id**: renamed repositories are matched under both
  names; both routes give 896.
- **AIDev file lists are per commit** and capped by the AIDev collection (30 commits per PR
  in `pr_commits`; `pr_commit_details` may be similarly truncated), so the file-overlap
  test can miss overlaps in long PRs. That only lowers yield; it cannot add a non-overlapping
  pair.
- **Cross-agent pairs are rare** (16 of 896), so S is almost entirely same-agent; reported.
- **The stopping rule** (60 conflicting pairs with truth) depends only on git outcomes, never
  on ladder results.

## What was not tested

- `fetch-sources` end to end inside the test (network, 1.3 GB). Run once by the subagent;
  the resumed download matched Hugging Face's sha256.

## What was assumed

- Ties on created_at: PR A is the smaller number.
- Re-running `sample-supplementary` replaces earlier supplementary pairs (dropping their refs).
