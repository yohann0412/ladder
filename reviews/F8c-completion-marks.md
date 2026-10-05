# Review: completion marks on working copies

Commits: `1a10d1e` (test, mine) and `a49527e` (implementation, cherry-picked from the
implementation lane). After merging I ran `e2e/test_interrupted.py`, `e2e/test_run_fixture.py`,
ruff and pyright myself: all passed or clean.

## What the diff does

- Each rebuildable working directory gets a mark, an empty file `<dir>.complete` beside it:
  the replay and final workspaces, the git copies, the weave and mergiraf copies, and the
  runtime base tree with its installed environment. The writer removes the mark before its
  first write and writes it after its last.
- `run`, truth, scoring, preparation and Claim C treat an unmarked directory as missing.
  Steps that can rebuild do so; readers that cannot refuse with "missing or incomplete".
- Prune, and every other delete path, removes marks before the trees they belong to.

## What could be wrong

- **Directories built before this commit have no mark.** They are all rebuilt on their next
  use. That is intended: the rebuilt copy must agree with its record, as it already had to.
  It costs time only.
- **The runtime base tree is now reinstalled whenever its mark is missing.** The first
  scoring pass after this commit therefore reinstalls every environment that still exists.
- **Trap outputs (fixture only) are still trusted when they exist.** They sit under
  `work/resolutions/`, which this change deliberately does not touch.
- **A mark proves that the step finished, not that the tree is unchanged since.** A
  directory edited by hand later still passes. Nothing in the pipeline edits these trees
  after writing them.

## What was not tested

- A real kill in the middle of a step. The test plants a partial directory where the kill
  would have left one.
- The runtime base tree path. The lane checked it by hand: an unmarked base with a stray
  entry was rebuilt and marked again. No committed test covers it.
