# Review: F9d, calibration split by output family and the Claim B calibration note (D24)

Commits:
- the test, and a fix to its setup that finalizes both of fx03's resolver runs (mine);
- the feature (cherry-picked from the implementation lane's worktree);
- one follow-up line (mine).

## What the diff does

- `Summary.calibration_agreement` maps a metric to a family (`llm` for rungs starting
  with `llm`, `structural` for the rest) and each family to the reviewer agreement, as a
  Wilson `Rate`. Families with no verdict are left out. Without a record the dict is
  empty.
- `verdicts.claim_b` keeps the pre-registered statement unchanged. When calibration has
  at least one LLM intent-dropped verdict, it appends:
  - the agreement, with its interval;
  - the adjusted rate: the interval's upper end times the llm-raw intent-dropped
    percentage, rounded to one decimal before it is compared with the threshold;
  - whether calibration supports the verdict.
- The calibration section of RESULTS.md adds a table by metric and output family. It keeps
  the per-metric table and the list of disagreements with their notes.

## My follow-up

As the lane wrote it, the support clause looked only at the adjusted rate. A Claim B
already below 15% on intent dropped would then read "calibration does not support this
verdict", even though low precision strengthens a falsification. Now calibration
"is consistent with" the verdict when the adjusted rate is on the same side of the
threshold as the computed rate, and "does not support" it otherwise. With the real data
(59/165, agreement 0/6) the text is unchanged: the adjusted rate is 14.0%, below 15%,
so calibration does not support "holds".

## What could be wrong

- **The adjustment is a bound.** "Precision at the interval's upper end" is a deliberately
  generous bound, not an estimate. The point estimate of precision on LLM outputs is 0/6.
  The adjusted rate would then be 0%, but six verdicts cannot support that number.
- **Family boundary.** The trap rung counts as structural. No calibration verdict came
  from it.
- **Tests-pass cell.** The note covers only the intent-dropped part of Claim B. The
  "tests pass but intent dropped" cell has its own small denominator, and calibration was
  not drawn for it.

## How it was checked

- The lane ran 4 of the 5 tests. It could not bring in my setup fix, because the
  permission system denied the cherry-pick in its worktree.
- After merging, I ran `e2e/test_report.py` myself: 5 passed. ruff and pyright strict are
  clean.
- I rendered the real records (the 14:06 snapshot plus `calibration.json`) and read the
  Claim B statement and the calibration section.
