"""Normalized forms of files and syntax nodes, in which formatting and comments never matter.

A syntax node becomes `(type children...)` and a leaf becomes its text; nodes whose type
contains "comment" are left out. Text inside a node that no child covers (string contents
held by hidden tokens, for example) is kept as a leaf, so string contents always matter.

Similarity is difflib's ratio over the leaf tokens. Its matching can take minutes on long,
repetitive token streams such as lockfiles, so it falls back to quick_ratio when both
streams exceed QUICK_RATIO_ABOVE tokens or when the matching would exceed RATIO_WORK_BUDGET
steps; the result names the method used.
"""

from collections import Counter
from collections.abc import Sequence, Set
from contextlib import suppress
from dataclasses import dataclass
from difflib import Match, SequenceMatcher
from typing import Literal

from tree_sitter import Node

from ladder.schemas import Record
from ladder.syntax import Parsed

OPEN = "("
CLOSE = ")"
LEAF = "'"
QUICK_RATIO_ABOVE = 20000
RATIO_WORK_BUDGET = 50_000_000

SimilarityMethod = Literal["ratio", "quick_ratio"]


@dataclass(frozen=True)
class Normalized:
    """A canonical form to test equality and the leaf-token sequence to measure similarity."""

    form: tuple[str, ...]
    tokens: tuple[str, ...]


class Similarity(Record):
    """A difflib similarity in [0, 1] and the difflib method that produced it."""

    value: float
    method: SimilarityMethod


def _decode(data: bytes) -> str:
    return data.decode("utf-8", "surrogateescape")


def _parts(node: Node, source: bytes) -> list[Node | str]:
    children = node.children
    starts = [node.start_byte, *(child.end_byte for child in children)]
    ends = [*(child.start_byte for child in children), node.end_byte]
    gaps = [source[start:end] for start, end in zip(starts, ends, strict=True)]
    if not node.type.endswith("content") and not any(gap.strip() for gap in gaps):
        return list(children)
    parts: list[Node | str] = []
    for gap, child in zip(gaps, [*children, None], strict=True):
        if gap:
            parts.append(_decode(gap))
        if child is not None:
            parts.append(child)
    return parts


def normalize_nodes(
    nodes: Sequence[Node], source: bytes, skip: Set[int] = frozenset()
) -> Normalized:
    """Return the normalized form of nodes, leaving out comments and the node ids in skip."""
    form: list[str] = []
    tokens: list[str] = []
    stack: list[Node | str | None] = list(reversed(nodes))
    while stack:
        item = stack.pop()
        if item is None:
            form.append(CLOSE)
        elif isinstance(item, str):
            form.append(LEAF + item)
            tokens.append(item)
        elif "comment" in item.type or item.id in skip:
            continue
        elif item.child_count == 0:
            text = _decode(source[item.start_byte : item.end_byte])
            form.append(LEAF + text)
            tokens.append(text)
        else:
            form.append(OPEN + item.type)
            stack.append(None)
            stack.extend(reversed(_parts(item, source)))
    return Normalized(form=tuple(form), tokens=tuple(tokens))


def normalize(parsed: Parsed) -> Normalized:
    """Return a file's normalized syntax tree, or its whitespace-split tokens without a grammar."""
    if parsed.tree is None:
        tokens = tuple(_decode(parsed.source).split())
        return Normalized(form=tokens, tokens=tokens)
    return normalize_nodes([parsed.tree.root_node], parsed.source)


def equivalent(left: Normalized, right: Normalized) -> bool:
    """Return whether two normalized forms are equal."""
    return left.form == right.form


class _RatioTooCostly(Exception):
    """The exact ratio would cost more than the work budget."""


class _BudgetedMatcher(SequenceMatcher[str]):
    """difflib's matcher that gives up once its searches could exceed the work budget."""

    def __init__(self, a: tuple[str, ...], b: tuple[str, ...]) -> None:
        super().__init__(None, a, b, autojunk=False)
        self._a = a
        self._b_counts = Counter(b)
        self._budget = RATIO_WORK_BUDGET

    def find_longest_match(
        self, alo: int = 0, ahi: int | None = None, blo: int = 0, bhi: int | None = None
    ) -> Match:
        """Charge the b positions this search may visit, then run difflib's own search."""
        stop = len(self._a) if ahi is None else ahi
        self._budget -= sum(self._b_counts[token] for token in self._a[alo:stop])
        if self._budget < 0:
            raise _RatioTooCostly
        return super().find_longest_match(alo, ahi, blo, bhi)


def similarity(left: Normalized, right: Normalized) -> Similarity:
    """Return difflib's ratio of the leaf tokens, or quick_ratio when that is too costly."""
    long = len(left.tokens) > QUICK_RATIO_ABOVE and len(right.tokens) > QUICK_RATIO_ABOVE
    if equivalent(left, right):
        return Similarity(value=1.0, method="quick_ratio" if long else "ratio")
    matcher = _BudgetedMatcher(left.tokens, right.tokens)
    if not long:
        with suppress(_RatioTooCostly):
            return Similarity(value=round(matcher.ratio(), 4), method="ratio")
    return Similarity(value=round(matcher.quick_ratio(), 4), method="quick_ratio")
