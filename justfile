# ladder: measure how far up the git -> structural -> LLM ladder agent PR conflicts climb.

set shell := ["bash", "-euo", "pipefail", "-c"]

# List every recipe.
default:
    @just --list
