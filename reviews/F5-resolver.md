# Review: F5 resolver protocol

Diff read in full: `plan.py`, `prepare.py`, `snapshot.py`, `taskfiles.py`, `prompt.py`,
`prtext.py`, `manifest.py`, `transcript.py`, `audit.py`, `ingest.py`, `finalize.py`,
`resolver_records.py`, `resolver_view.py`, `canary.py`, `trap.py`, `trap_cli.py`,
`resolve_cli.py`, `cli_support.py`, `refusal.py`, the `verify_snapshot` addition to
`wsverify.py`. The main model registered the trap command in the rung sub-app.

Acceptance: the main model prepared fixture scenario 3, spawned one real resolver subagent
with the fixed spawn line, finalized it (audit `ok`, 14 tool calls, about 18 s, no
violations), checked its output is AST-equivalent to `resolved/3` with `ladder compare`,
and recorded it in `fixtures/recorded/`. `uv run pytest e2e/test_resolver.py -q` ->
`1 passed` on the merged tree.

## What could be wrong

- **The audit trusts the transcript file.** It is written by the agent harness, outside the
  resolver's write permission in principle, but a resolver with Write could overwrite it
  (the path is not in its output dir, so the Write itself would be a violation recorded in
  the same transcript before the overwrite took effect - unless it rewrote the whole file).
  Mitigation: `finalize` runs right after each run; the transcript path is outside every
  directory the prompt names.
- **Harness-injected user messages** (a system reminder about hand-back arrives as the
  second user line) are ignored by design; only the first user message must equal the spawn
  line. A future harness that puts something before the prompt would make every run
  `protocol_violation`; that would be loud, not silent.
- **Grep `glob` and `type` arguments** are not path-checked; `path` is, and it is required.
- **Symlinks inside the snapshot** that point outside resolve outside and count as
  violations, which is correct but means a repository with absolute symlinks makes Read of
  those files a violation.
- **Caps**: 20 files, 200 kB per version, 600 kB total (`taskfiles.py`). Recorded in
  `DECISIONS.md` D16.
- **Renamed files lose one side's version.** `taskfiles.py` reads base, a and b at the
  conflicted path only. When one side renamed the file and the other edited it, the editing
  side's version lives under the old path and is left out of `files/<k>/`; the snapshot is
  the merged working tree, so it does not hold that version either. The resolver then sees
  the edit only through the conflicted file's markers. Not changed: a different task layout
  is a protocol change, which would mean a new labeled run over the whole set.
- **`prepare` does not require the run to be in the plan** (the test prepares an unplanned
  run 2). The truth guard uses the plan, so an unplanned run cannot unblock truth.

## What was not tested

- A transcript from a different harness version.
- A resolver that writes extra files outside `files/` but inside the output dir (rejected
  as malformed by `ingest`; checked by reading the code).

## What was assumed

- Non-pending tasks (`input_cap`, `identical_input`) still get `files/` and `PROMPT.md` for
  inspection, but no snapshot.

## Follow-up: transcripts with U+2028 or U+2029 (found in Phase 3)

- **Bug:** `read_transcript` split the JSON Lines file with `str.splitlines()`, which also
  breaks on U+2028, U+2029 and U+0085. JSON allows those unescaped inside strings. Both
  moonbitlang__core__2267-2422 runs quoted such characters from a test file, and the
  transcript was reported as unparseable.
- **Effect:** `collect` would have refused the runs, or `finalize` would have recorded
  `audit_impossible`.
- **What was done:** the acceptance test now plants both characters in the clean recorded
  run (`7d2e1eb`). The fix splits JSON Lines on `\n` only, also for `go test -json` output
  (`347541d`).
- **Effect on records:** no other run was affected. Every run already finalized had parsed
  cleanly, and the four disk-full runs were cut off at the end of the file (D21), not split
  in the middle.
