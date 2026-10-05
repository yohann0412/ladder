# Review: F8f, temporary files and package caches inside each pair's runtime

Commit: the one that adds this file. Changed files:
- `procrun.py`: `Runner.scratch` and `_scratch_env`;
- `runtime.py`: `RuntimeDir.scratch`;
- `pairsuite.py`, `runnable.py`: the three `Runner` constructions.

## Why

At 11:44, all three shards of the final pass were waiting at 5.4 GiB free, and the cache
janitor had no more repository caches it was allowed to delete. Three things outside
`work/` held the space:

- 8.6 GB in `/tmp`, mostly ten 431 MB `bruin-cli-embedded_*` Python environments that the
  bruin pairs' tests unpack, and a 3 GB `go-build*` directory left by a Go test killed at
  its time cap;
- 6.5 GB of shared uv cache;
- 3.0 GB of shared Go module cache.

Pruning a pair touches none of them. I deleted the named `/tmp` leftovers by hand after
checking that no `go` process was running and no process had its working directory
inside them.

## The change

A `Runner` built for a pair's runtime now gets `<runtime>/scratch`. Every install and
suite step it runs has these set under it:

- `TMPDIR`, `TMP` and `TEMP`;
- `UV_CACHE_DIR`;
- `GOMODCACHE`.

A step's own variables still take precedence (the Python adapter's
`UV_PROJECT_ENVIRONMENT`, the Go adapter's `GOCACHE` and `GOFLAGS`). Pruning the pair
deletes its runtime, and `remove_tree` already handles the Go module cache's read-only
files.

## What could be wrong

- **Cold caches.** Every pair now downloads its Python packages and Go modules from
  scratch. Installs take longer, and a large project can hit the install cap more often.
  That is recorded as `exceeds_cap`, so its pair leaves the tests-based denominators by a
  visible cause. Pairs scored before the change used warm shared caches. That gives
  later pairs a slightly higher chance of a cap, but the same outcome when they finish.
- **Suites that hard-code `/tmp`** still write there. Only `TMPDIR`-respecting tools move.
- **Suite outcomes** should not depend on where temporary files or caches live. A suite
  that does depend on it would already be fragile in CI.
- **Node package managers** (npm, pnpm, yarn) keep their shared caches. They grew slowly
  here (npm about 0.4 GB, pnpm store 1.3 GB) and are left alone.

## How it was checked

- ruff and pyright strict: clean.
- A throwaway Go module with one dependency, installed with `-mod=mod` through a scratch
  `Runner`: install and build passed. The module was downloaded into
  `scratch/go-mod`, not the shared cache.
- A probe step printed the scratch `TMPDIR`, `UV_CACHE_DIR` and `GOMODCACHE`, together with
  its own `GOFLAGS`.
- `e2e/test_runnable.py`, `e2e/test_claim_c.py` and `e2e/test_score.py`, which install the
  fixture's Python project with uv and run its suites: result in LOG.md.
