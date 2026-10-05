# Contributing

## Setup

```sh
uv sync          # Python 3.12+ environment with dev tools
just tools       # pinned weave and mergiraf into .tools/
just e2e         # every acceptance test
just check       # ruff lint, ruff format check, pyright strict
```

## Rules

- **Tests are end-to-end only.** Every test in `e2e/` runs the real `ladder` executable
  as a subprocess against real git repositories on disk and asserts on exit codes,
  files, JSON and numbers. No unit tests, no mocks, no test imports of `ladder` code.
  A feature gets exactly one acceptance test, written before the feature.
- **git is called through `ladder.gitio.run_git`** with explicit argument lists. Local
  operations run with user and system git configuration disabled so results do not
  depend on the machine.
- **Every record written to disk is a pydantic model** from `ladder/schemas.py`.
- Small modules with one job each, a one-line docstring on every public function saying
  what it does, no dead or commented-out code, no TODO markers.
- `ruff` and `pyright --strict` must pass.
- Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `data:`, `chore:`), one logical
  change per commit.
- Never change a resolver output, a truth file or a result record by hand. A protocol
  change is a new, labeled run over the whole set, recorded in `DECISIONS.md`.
