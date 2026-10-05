# Review: F7b scoring

Diff read in full: `testpick.py`, `entitymap.py`, `pairsides.py`, `rungoutputs.py`,
`mergeable.py`, `equivalence.py`, `intent.py`, `scoretests.py`, `score.py`, `score_view.py`,
`score_cli.py`. Acceptance re-run by the main model on the merged tree:
`uv run pytest e2e/test_score.py -q` -> `1 passed`. After the merge, pyright flagged the
recorded resolver output under `fixtures/recorded/` (data, never edited); excluded from
lint and type checks.

Subagent results on the fixture match the design: fx01 weave/mergiraf human-equivalent,
no drops, tests 15/15; fx07 trap tests pass and intent dropped (B, `validate`); a
resolution deleting `helpers.py` in fx04 is human-equivalent on the conflicted file but
drops A's `normalize` change (A touched non-conflicted files: counted separately);
resolved/3 for fx03 scores equivalent with no drops.

## What could be wrong

- **Deletion is invisible to containment.** When one side modifies an entity and the other
  deletes it, the spec's rule only asks whether the deleting side's *added* lines appear,
  which is vacuous; a resolution that keeps the modified version is never flagged for
  losing the deletion. Whole-file deletions still surface through `<rest>`. This follows
  the spec's definition literally and under-counts Claim B in modify/delete conflicts.
- **Containment is set membership over the resolved files' normalized lines**, not a
  multiset: a line added twice by the loser counts as present if it appears once.
  Docstring and comment lines count, as the plan says; a resolver that rewords a docstring
  can trigger a drop. Both effects are what the calibration sample checks.
- **Entity keys shift** when a side inserts a same-name entity before another (overloads):
  then two entities look changed. Rare outside languages with overloading.
- **Mergeable also requires every conflicted path to be decided** (no unmerged index entry
  or missing rationale entry). Needed so git's modify/delete state is not "mergeable".
- **Tests on the resolved state reuse the base environment** when manifests match; a
  resolution that edits a manifest triggers a reinstall (more `error` outcomes).

## What was not tested

- Languages other than Python through the full scorer on the fixture (entities and
  comparison were hand-checked in F7a).
- A rung output whose conflicted path is a binary file (token mode on undecodable bytes).

## What was assumed

- Weave/mergiraf records with status `error` score as unavailable.
- Scratch trees are deleted after scoring; logs and reports stay.
