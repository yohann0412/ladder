# Recorded resolver runs

`fx03-llm-raw/` is one real resolver subagent run on fixture scenario 3 (llm-raw, run 1),
spawned with the fixed line `Read <task>/PROMPT.md and follow it exactly.` and finalized
with `ladder resolve finalize`, which audited it as `ok` (14 tool calls, no violations).
Its output is AST-equivalent to `resolved/3`.

- `output/` is the run's output directory, unchanged.
- `transcript.jsonl` is the subagent transcript cut down to what the audit reads: user and
  assistant lines with `type`, `timestamp`, and `message.{id, role, content, usage}`. The
  absolute task and output directories are replaced by `$TASK_DIR` and `$OUTPUT_DIR`, and
  model identifiers are dropped.

`e2e/test_resolver.py` replays this run through `prepare` and `finalize` in a fresh
experiment, so the protocol is tested end to end without needing an agent at test time.
