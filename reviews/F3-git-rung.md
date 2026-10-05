# Review: F3 git rung and conflict taxonomy

Diff read in full: `gitrung.py`, `conflicts.py`, `markers.py`, `mergework.py`, the `rung`
sub-app. Acceptance re-run by the main model on the merged tree:
`uv run pytest e2e/test_git_rung.py -q` -> passed (all 19 scenario/heads combinations).

## What could be wrong

- **Two merges, one answer.** Types come from `git merge-tree --messages` (the replay
  study's unit and method), the working state from `git merge` in the copy. If they ever
  disagree on clean vs conflicted the rung records `error` instead of guessing. Not seen on
  the fixture; to be watched in the real run.
- **Message-to-path mapping** uses a whole-word regex. Rename messages name two paths; a
  rename/delete message is attributed to every path it names. Paths with unusual
  characters are matched literally; git quotes paths with control characters, which
  would not match (they would get no type).
- **Synthetic commits vs. original commits.** The replay study merged the original PR
  heads; the git rung merges three synthetic commits with the same trees. For a single merge
  base the result is identical (ort only sees trees). For criss-cross histories the
  original merge would use a virtual base; the workspace uses the first base. Flagged by
  `criss_cross` and counted in reconciliation.
- **Shallow-history artifacts in the paper** (depth-80 fetches) are not reproduced on
  purpose: the harness uses full history. Disagreements are classified in reconciliation.

## What was not tested

- rename/rename and file/directory conflicts on real data (the fixture has none).
- Binary-file conflicts (regions 0, category from the path).

## What was assumed

- Conflicted paths come from `git diff --name-only --diff-filter=U`, sorted; regions count
  `<<<<<<< ` opening lines.
