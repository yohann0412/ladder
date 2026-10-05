# How to run ladder locally

These steps reproduce the experiment from a fresh clone. Steps 1 to 4 need no network
beyond package installs and finish on a laptop. Step 5 runs the real experiment, which
clones hundreds of public repositories.

> **Warning: Claim C and the tests-based scores run untrusted code.** They install
> dependencies for, and run the test suites of, public repositories chosen by the dataset.
> Run those steps only in a disposable VM or container with nothing of value in it.

## 1. Prerequisites

| Tool | Why | Checked with |
|------|-----|--------------|
| Python 3.12+ and [uv](https://docs.astral.sh/uv/) | the harness | `uv --version` |
| [just](https://github.com/casey/just) | recipes | `just --version` |
| git 2.38+ | `merge-tree --write-tree` | `git --version` |
| Node.js with npm | the weave structural driver | `npm --version` |
| Rust with cargo | the mergiraf structural driver | `cargo --version` |
| Optional: Go, Node, Rust, Python toolchains | running repository test suites (Claim C, tests-based scores) | per adapter |

Plan for roughly 40 GB of free disk for the full experiment. Repository caches are
blob-less but large; working copies are deleted as each pair finishes (`--prune`).

## 2. Install

```sh
git clone <this repository> ladder && cd ladder
just setup     # uv sync: Python dependencies and dev tools into .venv
just tools     # weave 0.5.2 into .tools/npm, mergiraf 0.20.0 into .tools/cargo
just check     # ruff, ruff format --check, pyright --strict
just e2e       # every end-to-end acceptance test
```

`just e2e` builds the fixture repository in a temporary directory and runs the real CLI
against it. It should report every test passing.

## 3. The fixture, without an LLM

```sh
just fixture                    # build work/fixture deterministically and load its pairs
just ladder --fixture --no-llm  # git, weave and mergiraf rungs on all scenarios
```

The run prints one row per scenario and compares it with `fixtures/expected.json`. Rows
that need a resolver show `n/a` with `--no-llm`.

## 4. The fixture, with resolver subagents

The LLM rung is never called through an API. `ladder` prepares one task directory per
resolver run and prints one spawn line per task:

```sh
just ladder --fixture        # exits 3 and prints lines such as
# Read /…/work/fixture/work/resolver/fx03/llm-raw/run-1/PROMPT.md and follow it exactly.
```

Give each line, unchanged, to a fresh-context agent that has only Read, Glob, Grep and
Write. `resolver/AGENT.md` is such an agent definition for Claude Code (copy it to
`.claude/agents/`). Do not add anything to the line. The audit compares the agent's first
message with it.

When every agent has finished, finalize the runs from their transcripts and run again:

```sh
uv run ladder --pairs work/fixture/pairs.json --work work/fixture/work \
  --results work/fixture/results resolve collect --transcripts <transcript directory>
just ladder --fixture
```

`collect` finalizes every pending task whose spawn line opens exactly one transcript.
Give it only transcripts of agents that have finished. The audit fails any run whose
transcript shows a tool or path outside the rules. Such runs stay failed and are never
re-run.

## 5. The real experiment

```sh
just pairs                                   # load the paper's 747 pairs from data/source
uv run ladder pairs sample-supplementary     # add the supplementary sample S (rule D15)
uv run ladder pairs resolve --all            # fetch and resolve commits into work/cache
uv run ladder run --all --stop-before-truth --prune --skip-claim-c   # rungs, resolver tasks
# … spawn one agent per printed line, then:
uv run ladder resolve collect --transcripts <dir>
uv run ladder run --all --prune --skip-claim-c   # truth, runnability, scores
just claim-c                                 # untrusted code: see the warning above
just report                                  # RESULTS.md, summary.json, plots
```

`ladder run` skips every step that already has a record, so it can be stopped and
restarted at any time. Exit code 3 means resolver tasks are waiting for agents. Truth is
extracted only after every planned resolver run of a pair is settled.

The records in `data/results/` are the ones behind `RESULTS.md`. Re-running a step whose
record exists does nothing. To reproduce a number from scratch, use an empty results
directory: `--results <dir>`.

## Settings

| Variable | Default | Meaning |
|----------|---------|---------|
| `LADDER_PAIRS`, `LADDER_WORK`, `LADDER_RESULTS` | `data/pairs.json`, `work`, `data/results` | the three locations |
| `LADDER_WEAVE_DRIVER`, `LADDER_MERGIRAF` | `.tools/…` | structural driver binaries |
| `LADDER_MIN_FREE_GIB` | 3 | installers and test suites stop below this much free disk |

`ladder run --min-free-gb N` also waits before starting each pair until N GiB are free.
