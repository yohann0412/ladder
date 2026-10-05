# Review: F9e, the Claim C statement says when the sample is too small to compare

Commits: a test, `e2e/test_report.py::test_report_says_a_small_claim_c_sample_cannot_be_compared`,
and a one-branch change to `verdicts.claim_c`. Both are mine. Given the size, the
implementation lane was not used, the same as for F8d.

## Why

The final report said "0/6 … clean pairs pass alone and fail together, below the 1% human
small-team base rate". The point estimate is below 1%, but the interval reaches 39%. D25
requires the report to say that a decided count this small cannot be compared with the
human base rate. The old code handled two cases: at or above 1%, and zero positives with
an upper bound below 1%. It had nothing for zero or few positives with a wide interval.

## The change

When the interval's upper end is at or above the 1% base rate (and the point estimate is
below it), the statement adds: "With N decided pairs the interval reaches X%, which covers
the human base rates (1% for small teams, up to 12.5% for large ones), so the rate cannot
be told apart from them." `LARGE_TEAM_BASE_RATE = 12.5` sits next to `HUMAN_BASE_RATE`.
The other branches are unchanged.

## How it was checked

The new test rewrites fx06's Claim C record to pass together. That gives 0/2 with an
interval reaching 65.8%. The test failed on the old text, and after the change all 6 tests
of `e2e/test_report.py` pass (222 s). ruff and pyright strict are clean. The real report
now reads: "… With 6 decided pairs the interval reaches 39.0%, which covers the human base
rates (1% for small teams, up to 12.5% for large ones), so the rate cannot be told apart
from them."
