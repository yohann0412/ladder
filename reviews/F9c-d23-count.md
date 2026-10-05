# Review: F9c, the report counts records redone under D23

Commits:
- the test (mine): `e2e/test_report.py::test_report_counts_records_redone_under_d23`;
- the feature (cherry-picked from the implementation lane's worktree).

## What the diff does

- `RedoPair` and `RedoRecord` model `data/results/redo-d23.json`, which the redo script
  writes.
- `collect()` reads the file the same way as the calibration record. A missing file is
  `None`.
- `metrics.redo_counts` gives the pairs and the deleted record files. They become two new
  `Summary` fields, `d23_redone_pairs` and `d23_replaced_records`.
- RESULTS.md gets a `## Redone runs (D23)` section after Runnability, with one sentence.
  The sentence uses singular or plural to match the counts.

## What could be wrong

- **What is counted.** The count is of record files deleted, not of records whose content
  changed after the redo. A redo can reproduce a record exactly. The section says "deleted
  and run again", which is accurate.
- **One rule, one file.** The `rule` field is free text. A second redo rule would need its
  own file and fields.

## How it was checked

The lane ran `e2e/test_report.py` (4 passed). After merging, I ran it myself (4 passed in
156 s), plus ruff and pyright strict (clean). I also parsed the real `redo-d23.json` (20
pairs, 110 records) with `RedoRecord`.
