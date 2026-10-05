# Review: F2 leak-proof workspace

Diff read in full: `treecopy.py`, `workspace.py`, `wsverify.py`, `workspace_cli.py`,
`workspace_view.py`. Acceptance re-run by the main model on the merged tree:
`uv run pytest e2e/test_workspace.py -q` -> passed. The subagent built a real replay
workspace for Rello 517/518: all 8 checks passed, 1,253 objects stored = reachable, 3 commits.

## What could be wrong

- **Pseudo-refs are not checked.** `for-each-ref` does not list `MERGE_HEAD`, `ORIG_HEAD`,
  `AUTO_MERGE`. The canonical workspace never has them; rung copies and resolver
  snapshots do (they merge `b` into `a`), and they point only at the three synthetic
  commits. A check that every pseudo-ref resolves to one of the three commits belongs in
  the resolver's snapshot verification (F5).
- **Hooks directory** contains git's sample hooks; harmless text, never executed.
- **Index and working tree** are populated with `read-tree --reset -u`; files with
  `export-ignore`/`export-subst` attributes are unaffected because no `git archive` is used.
- **Submodules**: gitlink entries are copied as tree entries; their commits are absent, so
  submodule directories are empty. A conflict inside a submodule pointer cannot be
  resolved from content; such pairs will show up as conflicted gitlinks.

## What was not tested

- A tree containing symlinks, executable bits or gitlinks.
- Very large trees (object batches of 1,000 SHAs per fetch).

## What was assumed

- Exit code 2 for an unusable pair, 1 for a failed check; a failed verification deletes the
  previous record and writes none.
