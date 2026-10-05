# Review: F8d, no disk wait between building a pair and scoring it

Commit: the one that adds this file. One line removed from `orchestrate._Runner.group`.

## What was wrong

`ladder run --min-free-gb N` is documented as "wait before each pair while less is free".
`group` also waited again inside each repository group: after the pair's workspace and rung
copies were built and before truth and scoring. Most pairs are small, so the second wait
did no harm. The mlflow pair's copies take about 4 GB (workspace about 1 GB, three rung
copies about 1 GB each). After they were built, free disk fell to 3.7 GiB against a 5 GiB
floor. Nothing else was running that could free space, and the pair's own copies are only
pruned after it is scored. So the wait could never end. It cleared only because I deleted
other files by hand (the Go module cache and a scratch clone).

## The change

The wait before scoring is gone. The wait before each pair starts is kept. Scoring runs
installers and suites under the 3 GiB floor of `LADDER_MIN_FREE_GIB`. Low disk there stops
the step, and the step is recorded as `capped` or `exceeds_cap`, so a run no longer hangs.

## What could be wrong

- With several pairs in one repository, all of them are built before any is scored. Their
  copies add up, and only the per-pair start wait bounds them. On a small disk a suite can
  then hit the 3 GiB floor more often. The result is visible as `capped` by cause, not
  hidden.
- There is no failing acceptance test first. Reproducing the deadlock needs a pair whose own
  copies cross the floor on the real disk, and the fixture's copies are kilobytes. The
  regression checks were `e2e/test_interrupted.py` (a full `ladder run` of fx01 with prune
  and rebuild), ruff and pyright. All are clean.
