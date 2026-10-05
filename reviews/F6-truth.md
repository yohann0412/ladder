# Review: F6 truth extraction

Diff read in full: `truth.py`, `regions.py`, `blobs.py`, `truth_cli.py`. Acceptance re-run by
the main model on the merged tree: `uv run pytest e2e/test_truth.py -q` -> `1 passed`.
Subagent checks on the fixture: rewrite true only for fx04 (core.py touched beyond the
conflict), fx08 located by absorption, `leak_head_equals_truth` fires when a replay head is
pointed at the truth commit.

## What could be wrong

- **Rewrite flag (a) compares against git's clean merge** of the replay heads. For an
  absorption truth commit, other default-branch commits merged in at the same time change
  non-conflicted files too, so `touched_beyond_conflict` will be common on real data. That
  is the intended meaning ("truth includes changes beyond the conflict"), and results are
  reported with and without such pairs.
- **Flag (b) context matching** is exact per line after stripping trailing whitespace; a
  human who re-indented the whole file is flagged as editing outside the regions.
- **Truth needs the git rung's copy on disk** (`work/rungs/<pair>/git-replay`). Under the
  streaming disk policy (`LOG.md` entry 11) the orchestrator must rebuild it before truth.
- **Guard**: plan must exist and every planned run must be settled; `truth audit` lists any
  truth directory without that. The cross-pair same-repository guard lives in `prepare`.

## What was not tested

- Truth commits whose conflicted path is a submodule or a symlink.
- A truth commit missing from the cache because the default branch was force-pushed.

## What was assumed

- A non-located truth writes only the record.
- CRLF is treated as LF when comparing non-conflicted files.
