# Review of the results

This is the adversarial review of `RESULTS.md`. For each claim it says what the numbers
are and what could make them wrong. It also covers what went wrong while the numbers were
being produced. Numbers are those of the final `ladder report`. Where a number below is
marked *(final)*, it was checked against `data/results/summary.json` at the end.

## The verdicts in one paragraph

**Claim A** (the ladder resolves at least 90% of conflicting agent-PR pairs the way the
maintainers did) is **falsified**:

- The practical ladder's accepted output is human-equivalent for 22 of 78 pairs with a
  located human resolution: 28.2%, 95% CI 19.4% to 39.0%.
- Under the best-case bound of D20 and D21 it reaches 31/78 (39.7%).
- The oracle ladder, which picks the best rung after the fact, reaches 28/78 (35.9%).
- No sensitivity cut comes near 90%. The highest is 41.5%, without truths the
  maintainers rewrote, with an upper bound of 56.6%.

**Claim B** (the LLM silently drops one PR's intent in at least 15% of pairs) **holds by
the pre-registered rule**: 59/165 llm-raw outputs (35.8%). But calibration does not
support it. The reviewer agreed with 0 of 6 intent-dropped verdicts on LLM outputs. At
the upper end of that agreement's interval, the rate would be 14.0%, below the
threshold (D24).

**Claim C** (pairs that pass alone and fail together) is reported as a rate over too
few decided pairs to compare with the human base rate. See its section.

## Claim A: what could be wrong

- **Only 78 of 224 conflicting pairs have a located human resolution.**
  - In 138 pairs only one of the two PRs was merged (`not_both_merged`), so no merge of
    both exists to compare with.
  - In 8 pairs the merge could not be located.

  So Claim A rests on the pairs whose maintainers merged both PRs. Those may well be
  easier conflicts than the rest, since a maintainer who sees a hard conflict can close
  one PR. If so, the true rate over all conflicting pairs is lower still, and the
  falsification stands either way.
- **Human-equivalence is strict.** It means equal syntax trees after normalization, or
  equal tokens for files without a grammar. Calibration confirmed all 20 sampled positive
  verdicts (20/20; 18/18 on LLM outputs). Negatives were not sampled: PLAN 5.6 draws only
  "human-equivalent" verdicts. So an output that does the same as the maintainers' merge
  but is written differently counts against the ladder, and how often that happens was
  not measured. This is the largest open threat to the size of the Claim A number. It
  cannot rescue the claim: the oracle ladder would need to rise from 28 to 71 of 78.
- **LLM failures count as not resolved.**
  - 79 resolver runs were refused at the input cap, because the conflicted files were too
    large for the fixed budget.
  - 41 runs failed the transcript audit: 35 only for reading their own output (D20), 4
    with a cut-off transcript (D21) and 2 for other violations.

  The best-case bound counts the D20 and D21 cases as successes. The input cap is a design
  choice of this harness. A resolver with a larger budget might resolve some of those
  pairs, but the truth-located subset is where Claim A is decided, and the bound already
  shows how much room the audit failures leave.
- **Truth rewrites.** 37 of the 78 truths came from maintainers who also changed the
  conflicted files beyond the conflict. Without them the practical ladder reaches 17/41
  (41.5%). Still falsified.
- **Truth located by absorption**: the merge commit is found by the PR's changes, not by
  a merge parent. Its correctness was reviewed in `reviews/F6-truth.md`, and calibration
  saw no case where the truth looked wrong.

## Claim B: what could be wrong

- **The intent metric over-reports drops on LLM outputs.** The calibration
  (`data/results/calibration.json`) read 6 intent-dropped verdicts on LLM outputs and
  agreed with none:
  - two PRs implemented the same change differently and the merge kept one (3 cases);
  - the merge combined both sides correctly, for example applying A's version bump to
    B's new file (1);
  - the other side's text was a near-identical rewrite of the flagged lines, such as a
    typo fix or a reformatted condition (2).

  The metric asks whether each PR's added lines and changed definitions survive. That is
  a fair proxy when nobody rewrites the code and a poor one when the resolution merges by
  rewriting. With 0/6, the interval for the metric's precision on LLM outputs is 0% to 39%.
  Claim B's 35.8% could therefore be anywhere from 0% to about 14%. That is why the report
  says calibration does not support the verdict. The pre-registered verdict is left
  unchanged, as D24 decided before the final report.
- **On git and structural outputs the metric does what it says** (12/14 agreed). There a
  flagged change almost always sat inside an unresolved conflict, so it was not in effect.
  When the output has conflict markers it does not parse, and the entity names in
  the drop list can be wrong even when the verdict is right. Two disagreements came from
  this: one where only a semicolon was unresolved, and one about build-cache binaries.
- **Denominator.** PLAN section 1 says "of conflicting pairs", but the code divides by
  llm-raw outputs that exist (165 of 224). Over all conflicting pairs the rate is 59/224
  = 26.3%, also above 15% (D24 records this).
- **Tests pass but intent dropped** could be measured on only 6 llm-raw outputs, because
  few repositories have a suite this harness can run at base (next section). 0/6 says
  little.

## Runnability and the tests-based cells

Of the repositories checked, only about one in twenty has a suite this harness can
install and run green at base. The main reasons:

- Node projects without jest, vitest or mocha;
- suites that already fail at base;
- missing toolchains (PHP, Java, .NET);
- installs past the time cap.

Every tests-based cell therefore has a tiny denominator, and every "tests pass" number
in the report should be read as anecdotal. The adapters are scoped in
`reviews/F8-runnability.md`. Widening them was out of scope.

## Claim C

*(final numbers after the Claim C waves)*

## What went wrong while producing the numbers, and whether it touches them

- **Disk.** The 40 GB disk filled several times (LOG 17 to 21):
  - The causes were shared package caches (uv, Go, npm, pnpm, cargo), leftovers in
    `/tmp` from suites killed at their caps, and the two largest pairs running at the
    same time.
  - Fixes F8b to F8f added a disk floor, completion marks, the removal of a deadlocking
    wait, and per-pair temporary and cache directories.
  - Test runs stopped by the floor were recorded honestly as stopped. D23 then redid all
    20 such pairs once (110 records), with a rule decided before any redo result. The
    report counts them.
- **Container restarts.** Two restarts (about 10:00 and 10:33) killed the running processes. Every record is
  written atomically and working copies carry completion marks, so a restart costs time,
  not records.
- **A cache janitor race.** It deleted repository caches under four running truth steps.
  Those steps failed without writing a record and were simply run again. A "pruned" log
  line had been taken as "done", which dropped one failed pair from a restart. Completeness
  is now judged from the records, and a final sweep confirmed 224/224 conflicting pairs
  with truth and a git score.
- **Resolver protocol** (D20, D21). 35 runs read their own output and 4 transcripts were
  cut off. All of them stay failed, and the best-case bound shows what they could change.
- **Suites inherit the harness's `PWD`.** One suite wrote a 19-byte file into the
  repository root. No result depends on it.

## Variance

The double run (30 pairs, seed 42) gives llm-raw run-to-run agreement of 19/22 (86.4%) on
pairs where both runs finished. So about one pair in seven resolves differently on a
second try. Claim A's interval is wider than this effect, and its verdict does not move.

## What was not done

- Negative human-equivalence verdicts were not calibrated (see Claim A).
- The intent metric was not re-tuned after calibration. Doing so would be a forking path.
  A semantic intent check is the obvious next step.
- Only one resolver model and one fixed prompt were used. The LLM rung's numbers describe
  this resolver, not LLM merging in general.
- Claim C was cut, as D19 allows. See its section.
