# Review: F7a syntax-aware comparison

Diff read in full: `languages.py`, `syntax.py`, `normalize.py`, `entities.py`,
`entity_rules.py`, `compare.py`, `syntax_cli.py`, the cli.py registration. Acceptance re-run
by the main model on the merged tree: `uv run pytest e2e/test_compare.py -q` -> `1 passed`.
No protected file touched. One integration conflict in `cli.py` (two registration lines from
parallel lanes) resolved by the main model by keeping both.

## What could be wrong

- **Uncovered text kept verbatim.** To keep string contents that no child node covers
  (escapes, interpolation, heredocs), `_parts` emits the gaps between children as leaves for
  any node with a non-whitespace gap, and then emits *all* gaps of that node, whitespace
  included. In a grammar where a non-string node has a hidden non-whitespace token, spacing
  differences inside that node would count as non-equivalence. The subagent's hand checks
  (JS, C, JSON reformatting) found none; not proven for every grammar. The calibration
  sample (PLAN.md 5.6) is where a false "not equivalent" would show up.
- **Similarity is over leaf tokens only**: a Python indentation-only change reports
  similarity 1.0 with equivalent false. Similarity is only a near-miss indicator, never a
  verdict, so this is acceptable but must be stated next to similarity numbers.
- **Budgeted difflib.** Exact `ratio()` below a 50M-step work budget, `quick_ratio()` above
  it (an upper bound, so near-miss similarity is inflated for huge repetitive files such as
  lockfiles). The method is recorded per comparison.
- **Entity names are not unique** (overloads, property setter/getter, trait impls). The
  intent scorer must key entities by (name, occurrence index) or compare multisets.
- **tree-sitter 0.26.0 memory corruption** when reading `Node.start_point.row`; avoided via
  byte offsets. Any later code must not read `.row`.

## What was not tested

- Markdown, YAML, TOML and other extensionless or unmapped files go to token mode; no
  grammar check for them (by design, flagged `token_mode`).
- `.h` files are parsed as C even in C++ projects; C++ headers may fail to parse and then be
  reported as not parseable, which would make a structural rung look worse than it is.
  Count of `.h` conflicted files will be checked in the real data before scoring.
- Entity extraction on minified or generated code.

## What was assumed

- CSS, HTML and JSON are one whole-file entity each.
- Namespaces are never entities; C/C++ structs and classes are.
