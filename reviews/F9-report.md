# Review: F9 report

Diff read: `stats.py`, `collect.py`, `ladder_metrics.py`, `metrics.py`, `verdicts.py`,
`agreement.py`, `cuts.py`, `taxonomy.py`, `pair_table.py`, `plots.py`, `report_*.py`,
`md.py`, `ratefmt.py` (1,665 lines; the main model read `stats`, `ladder_metrics`,
`verdicts` line by line and the rest for structure). The acceptance test
(`e2e/test_report.py`) needs `ladder run --all --no-llm`, built later; it is run at
integration of the orchestration lane. Until then the subagent's checks are on 12
hand-made pairs built through the schemas (every number hand-counted). Lint, format and
pyright strict pass on the merged tree.

One round sent back: the practical ladder gave up when weave's status was `resolved` but
its output was not mergeable; fixed so the LLM step falls to llm-raw (f020146). On the
12-pair set only that pair changed (practical ladder 2/5 -> 3/5).

Process note: this lane deleted its own worktree with a scratch script (`LOG.md` entry
10); restored from git; no data affected.

## What could be wrong

- **Denominator choices are mine, not the spec's** (stated in the F9 prompt and printed in
  the report): mergeable and human-equivalent over applicable pairs, failures counted as
  not resolved; intent and tests over available outputs. A reader who prefers "failures
  count as intent preserved" can recompute from the per-pair table.
- **Claim B uses llm-raw only.** llm-post-weave has its own row but does not enter the
  verdict; stated in the verdict sentence.
- **Claim A "inconclusive"** when fewer than 10 judged pairs or the Wilson interval
  straddles 90%. This is stricter than "the point estimate decides" in PLAN 1; it follows
  PLAN_REVIEW item 6.3(c). Both the point estimate and the interval are printed.
- **matplotlib typing** relaxed for `plots.py` only.

## What was not tested

- The full acceptance test (pending orchestration).
- Real-data scale (hundreds of pairs) for speed.

## What was assumed

- Practical ladder: any accepted output must be mergeable, LLM included.
- Input-cap tasks count as failures once (task without a run record).
- Per-category breakdowns are per conflicted file.
