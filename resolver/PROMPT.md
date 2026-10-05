# Merge-conflict resolution task

You are resolving a merge conflict between two pull requests, as one data point in a
research experiment. Your output is saved exactly as you write it and scored later.
Nobody will correct it. Work carefully and completely.

## Rules

Breaking any rule voids the run.

1. Use only these tools: Read, Glob, Grep, Write. Do not use a shell, web access, Edit,
   or other agents.
2. Read, Glob and Grep only inside this task directory, and always pass an absolute path
   that starts with it:
   `$task_dir`
3. Write only inside this output directory:
   `$output_dir`
4. Do not run tests, builds or any program.
5. Produce the merged content of each conflicted file listed below, and nothing else.

## The two pull requests

The merge brings PR B into PR A. Both were written against the same base.

### PR A: $a_title

$a_body

### PR B: $b_title

$b_body

## Conflicted files

$conflict_source

For each conflicted file there is a directory `$task_dir/files/<k>/` holding:

- `base`: the file at the merge base (missing if the file did not exist there)
- `a`: the file in PR A (missing if PR A deleted it)
- `b`: the file in PR B (missing if PR B deleted it)
- `conflicted`: the file as the merge left it, with conflict markers (missing when there
  is no merged text, for example when one side deleted the file)

| k | path | conflict |
|---|------|----------|
$file_table

The directory `$snapshot_dir` is the repository checked out at this conflicted merge
state. Its git history holds only three commits: the base, PR A and PR B. Read any
file in it that helps you understand the surrounding code.

## What to write

For every conflicted file, decide the merged content that keeps the intent of both
pull requests wherever both can be kept.

- To keep the file, write its complete merged content to
  `$output_dir/files/<path>`, where `<path>` is the repository path from the table.
  The file must contain no conflict markers.
- To delete the file, do not write it, and mark it `delete` below.

Then write `$output_dir/rationale.json` with exactly one entry per conflicted file:

```json
{"files": [{"path": "<path>", "action": "keep", "rationale": "<one sentence>"}]}
```

`action` is `keep` or `delete`. When everything is written, reply with the single word
DONE.
