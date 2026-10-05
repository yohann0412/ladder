# Review: F1b ref resolution

Diff read in full: `cache.py`, `gitgraph.py`, `mergecommits.py`, `contamination.py`,
`resolve.py`, `resolve_view.py`, `pairselect.py`, the `pairs resolve` command. Acceptance
re-run by the main model on the merged tree: `uv run pytest e2e/test_pairs_resolve.py -q`
-> passed (5 acceptance tests passed together). No protected file touched.

Real-pair spot checks reported by the subagent agree with the main model's own
reconnaissance in `LOG.md` entry 4: Rello 517/518 contaminated on #517 (PR a), rewound one
commit, truth = absorption commit 6280cc9, still conflicting (CHANGELOG.md,
js/navigation.js); jdx/mise unrecoverable (walk lands on the default branch after 78
commits); vscode-mssql clean of contamination.

## What could be wrong

- **Clock skew.** Contamination rule (b) takes the oldest-in-chain-order default-branch
  commit with committer time >= T_F - 5 s. A single mis-dated old commit on the main line
  would make every PR "contaminated" and rewind it too far. Detection: the report lists
  rewound-commit counts; any pair rewound past its own first commit becomes
  unrecoverable, which is visible.
- **Base branch assumption.** Only the repository's current default branch is searched for
  merge commits; PRs into other branches get "truth unlocated". A renamed default branch
  is not re-read on `--refresh`.
- **AIDev `merged_at` drives both truth ordering and contamination time.** If AIDev is wrong
  (seen: v3 vs main disagree for 113 PRs), the wrong PR could be called "later".
- **No network timeout** in clone/fetch: sent back as a follow-up (timeouts, partial clone
  cleanup).
- **Ties**: equal merged_at -> b counts as later. Rare.

## What was not tested

- A true-merged PR with own commits after the other PR merged (the case revision 10 of the
  plan fixes) has no fixture scenario; the rule is checked by reading the code
  (`markers` uses the first-parent chain only).
- Criss-cross histories (count recorded, first base used).
- A pair whose two PRs both contaminate each other.

## What was assumed

- The rewind's binary search is valid because contamination is monotone along a
  first-parent chain (a commit reaching a marker makes its descendants reach it).
- Merge-commit search runs only for merged PRs, and only merged PRs can contaminate.
