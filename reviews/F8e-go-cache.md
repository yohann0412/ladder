# Review: F8e, a Go build cache per pair

Commit: the one that adds this file. Changed file: `src/ladder/adapters/go.py`.

## Why

Go suites used the shared build cache in `~/.cache/go-build`. Within an hour of being
cleared, it reached 4.1 GB, mostly from `onflow__flow-go`. Nothing trims it, and pruning a
pair does not touch it. That cache plus the Go module cache (1.7 GB) left 3.4 GiB free, so
the final pass stopped before every pair. Clearing the shared cache while a suite builds
could break that build and record a false failure. So the cache is cleared only when no
`go` process runs, and from now on each pair gets its own.

## The change

Every Go install and suite command now sets `GOCACHE` to `<pair runtime>/envs/<label>/gocache`
(absolute). Suites that reuse the base environment reuse its cache. Pruning the pair deletes
it with the rest of the runtime directory. `GOFLAGS=-mod=mod` is set as before for the
fallback strategy.

## What could be wrong

- **Outcomes.** The build cache only holds compiled packages, keyed by content, and suites
  already run with `-count=1`. So test outcomes should not depend on where the cache lives.
  Pairs scored before this change used the shared cache.
- **Speed.** Each pair now compiles the standard library and its dependencies from scratch.
  A large Go project could hit its time cap more often. That shows up as `capped` (by cause),
  not as a pass or fail.
- **Module cache.** The module cache (`~/go/pkg/mod`) stays shared. Its files are read-only,
  so the plain directory delete used for pruning cannot remove it. It grows more slowly and
  is cleared by hand, only when no `go` process runs.

## How it was checked

ruff, ruff format and pyright are clean. A throwaway module with one test was installed and
built through `GoAdapter.install`. Both steps passed, the cache filled under the pair's env
directory, and the suite command carries the same `GOCACHE`. No e2e test covers the Go
adapter, because the fixture is Python.
