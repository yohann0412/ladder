# ladder: measure how far up the git -> structural -> LLM ladder agent PR conflicts climb.

set shell := ["bash", "-euo", "pipefail", "-c"]

fixture_dir := "work/fixture"
fixture_flags := "--pairs " + fixture_dir + "/pairs.json --work " + fixture_dir + "/work --results " + fixture_dir + "/results"

# List every recipe.
default:
    @just --list

# Install Python dependencies into .venv.
setup:
    uv sync

# Install the pinned structural merge drivers into .tools/.
tools:
    mkdir -p .tools
    npm install --silent --prefix .tools/npm @ataraxy-labs/weave@0.5.2
    cargo install --locked --quiet --root .tools/cargo mergiraf@0.20.0
    .tools/npm/node_modules/.bin/weave --version
    .tools/cargo/bin/mergiraf --version

# Lint, format-check and type-check.
check:
    uv run ruff check .
    uv run ruff format --check .
    uv run pyright

# Format the code.
fmt:
    uv run ruff format .
    uv run ruff check --fix .

# Run every end-to-end acceptance test.
e2e *args:
    uv run pytest {{args}}

# Build the fixture repository into work/fixture and load its pairs.
fixture:
    rm -rf {{fixture_dir}}
    uv run python fixtures/make-fixture.py {{fixture_dir}}/build
    uv run ladder {{fixture_flags}} pairs load --fixture {{fixture_dir}}/build

# Load the paper's pairs from the vendored sources into data/pairs.json.
pairs:
    uv run ladder pairs load --source data/source

# Run the ladder on one pair id, or on every fixture scenario with --fixture.
ladder target:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "{{target}}" == "--fixture" ]]; then
        uv run ladder {{fixture_flags}} run --all --expect fixtures/expected.json
    else
        uv run ladder run {{target}}
    fi

# Run the ladder on every paper and supplementary pair.
ladder-all:
    uv run ladder run --all

# Run Claim C (passes alone, fails together) on every clean, runnable pair.
claim-c:
    uv run ladder claim-c --all

# Write RESULTS.md and data/results/summary.json from every result record.
report:
    uv run ladder report
