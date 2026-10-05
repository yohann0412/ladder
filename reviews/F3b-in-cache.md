# Review: in-cache git rung (extension of F3)

Diff read in full: `cacherung.py`, the `git_result` rename in `gitrung.py`, the
`--in-cache` option in `rung_cli.py`, and the added equivalence check in
`e2e/test_git_rung.py`. Acceptance re-run by the main model on the merged tree:
`uv run pytest e2e/test_git_rung.py -q` -> `1 passed` (all 19 scenario/heads records equal
to the workspace path apart from `detail`).

Why: building two full workspaces per pair to reconcile 747 pairs took hours and filled the
disk (`LOG.md` entry 11). The replay study ran merge-tree on the original heads; doing the
same in the blob-less cache fetches only the blobs the merge reads (about 1-2 s per pair).

## What could be wrong

- **Final heads use git's virtual merge base** for criss-cross histories (the study's method)
  while the workspace path uses the first base. On a real criss-cross pair
  (elsa-studio 521/526) the in-cache result matches the study's row and the workspace result
  does not. Replay heads pass the recorded base explicitly, so they match the workspace.
- **Relabeling** replaces the two commit ids with `a` and `b` in messages and paths; a path
  that contains a full commit id would be relabeled too (implausible).
- **A failed lazy fetch is recorded as `status: error`**; reconciliation re-runs error
  records before reporting.

## What was not tested

- Repositories with submodule conflicts in-cache.

## What was assumed

- Lazy fetch works with the isolated git configuration (verified with fresh clones).
