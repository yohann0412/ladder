# Review: F9b, Claim C exclusions by cause, the merge-breaks-install count, and the cut

Commits: the test (mine), the feature (cherry-picked from the implementation lane's
worktree), and a one-line type annotation in the test, which pyright strict asked for. The
acceptance test is `e2e/test_report.py::test_report_groups_claim_c_exclusions_and_cut`.

## Why

A draft report on the real records grouped Claim C exclusions by their raw reason. That
reason includes installer and test-runner output, so with hundreds of pairs every row
would be different. D19 also asks for two numbers the report did not give: merges that
break dependency installation while A and B install, reported on their own, and pairs
never attempted, reported as `not attempted: cut`.

## What the diff does

- `claimc_causes.claim_c_cause` maps one record to one short cause. The first rule that
  matches wins:
  1. `unrunnable: <reason>`;
  2. `suite unavailable`;
  3. `stopped at the free-disk floor`;
  4. `merge breaks dependency installation`;
  5. `a or b fails alone`;
  6. `error or not run`;
  7. `capped`;
  8. `flaky`;
  9. `other`.

  Rules 3 to 9 read the structured outcomes (`a`, `b`, `merge`), not the reason string. The
  phrases it looks for in `detail` (`install failed`, `timed out after`, the free-disk
  phrase) are now named constants in the modules that write them. Those modules still
  write byte-identical strings.
- A merge install that hit its time cap counts as `capped`, not as a merge that breaks
  installation. A and B count as installed when their suite ran: passed, failed, flaky or
  capped.
- `Summary` gains four fields:
  - `claim_c_clean_pairs`: replay-head git `clean`;
  - `claim_c_attempted`;
  - `claim_c_not_attempted`;
  - `claim_c_exclusions`: cause to pairs.
- The Claim C section of the report gives:
  - the pool, attempted and cut counts;
  - the table by cause;
  - the merge-breaks-install count, as its own sentence.

  The per-pair table keeps the raw reasons, and a clean pair with no record now reads
  `Claim C not attempted: cut`.

## What could be wrong

- **Text matching.** Detecting an install failure depends on the text
  `; install failed: ` in the merge's detail. A test run whose output tail contains that
  exact text would be misread. This is unlikely, but nothing structured records the
  failing step.
- **Missing installer.** A merge whose installer is missing (`not found`) while A and B
  installed counts as merge-breaks-install. A and B used the same toolchain, so this
  cannot happen unless the merge changes the manager.
- **Pool wording.** The pool sentence always says "in D19 order", including for the
  fixture, which has no order file.
- **One cause per pair.** A pair excluded for two reasons shows only the first. The full
  reasons are in the per-pair table.

## How it was checked

The lane ran `e2e/test_report.py` (3 passed) with the main checkout's pinned tools, plus
ruff and pyright on `src`. I read the full diff and ran ruff, ruff format and pyright
strict on everything: all clean after the annotation. I also re-ran `e2e/test_report.py`
myself; the result is in LOG.md.
