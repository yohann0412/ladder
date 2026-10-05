# Review: F8b, free-disk floor for installers and test runners

Commits: `85868c2` (test, mine), `89f1be6` (implementation, cherry-picked from the
implementation lane's worktree). The acceptance test is the new block at the end of
`e2e/test_claim_c.py`. I ran it myself after the merge (1 passed), along with ruff and
pyright (clean).

## What the diff does

- `diskfloor.py` reads `LADDER_MIN_FREE_GIB`, which defaults to 3. A value that is not a
  finite positive float is an error.
- `procrun.Runner.run` now:
  - refuses to start a step when free space under its `cwd` is already below the floor;
  - otherwise starts `timeout` in a new session and polls free space every 2 s;
  - when free space drops below the floor, sends SIGTERM to the process group, waits
    `KILL_GRACE_S`, then sends SIGKILL.
  The time cap behaves as before. A disk-stopped step has no exit code, so it is never `ok`.
- How a disk stop is recorded:
  - `testrun` records a disk-stopped suite as `capped` with "free disk" in the detail, and
    does not retry it (capped runs are never retried);
  - `reasons` maps a disk-stopped install step, or a disk-capped suite, to `exceeds_cap` and
    keeps the floor message;
  - `runnable` stops trying more install strategies after a disk stop.

## What could be wrong

- **A disk-capped suite is told apart from a time-capped one by a phrase in its detail**
  (`FREE_DISK` in `reasons._limits`). If the detail wording changes, a disk stop is reported
  as a time cap, but still as `exceeds_cap`. The counts by cause would shift; the rates would
  not.
- **The floor is global.** Any process filling the disk, including resolver preparation running
  at the same time, can stop an unrelated suite. Claim C then records that pair as
  `capped`, which excludes it. D21 already says preparation and test running are not
  interleaved; the exclusion is visible by cause either way.
- **Phase B tests on ladder pairs go through the same runner.** If disk is low there, rung
  tests are recorded as `capped`, so tests-based cells shrink their denominator rather than
  record a pass or fail.
- **The final SIGKILL to the process group** goes out even after `timeout` has exited, so in
  principle it could hit a reused process group id. In practice this is negligible.

## What was not tested

- The e2e test covers only the "not started" path. The mid-run stop and the SIGTERM-to-SIGKILL
  escalation were checked by the lane with throwaway scripts, not by a committed test.
- A floor value that is invalid (empty, negative, `inf`) raises `ValueError` inside the
  runner. I did not check how `ladder run` reports that; it should be a loud failure of the
  first step.

## What was assumed

- The free space under a step's `cwd` is the free space that matters. All runtimes live under
  `work/`, on the same file system as the resolver outputs.
- 3 GiB is enough headroom for resolver writes and records while a suite runs.
