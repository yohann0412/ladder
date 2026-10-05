"""Compare two versions of a file: exact and order-insensitive equivalence, and similarity."""

from collections import Counter
from typing import Literal

from ladder.entities import Entity, extract
from ladder.normalize import (
    SimilarityMethod,
    equivalent,
    normalize,
    normalize_nodes,
    similarity,
)
from ladder.schemas import Record
from ladder.syntax import Parsed, parse, parses


class Comparison(Record):
    """How two versions of a file relate once formatting and comments are ignored."""

    mode: Literal["ast", "token"]
    language: str | None
    equivalent: bool
    equivalent_unordered: bool
    similarity: float
    similarity_method: SimilarityMethod
    left_parses: bool | None
    right_parses: bool | None


def _remainder(parsed: Parsed, entities: list[Entity]) -> tuple[str, ...]:
    if parsed.tree is None:
        return ()
    skip = frozenset(node.id for entity in entities for node in entity.nodes)
    return normalize_nodes([parsed.tree.root_node], parsed.source, skip).form


def equivalent_unordered(left: Parsed, right: Parsed) -> bool:
    """Return whether two files have equal top-level entities as multisets and equal rest."""
    if left.tree is None or right.tree is None:
        return equivalent(normalize(left), normalize(right))
    left_top = [entity for entity in extract(left) if entity.top_level]
    right_top = [entity for entity in extract(right) if entity.top_level]
    left_forms = Counter(entity.normalized.form for entity in left_top)
    right_forms = Counter(entity.normalized.form for entity in right_top)
    return left_forms == right_forms and _remainder(left, left_top) == _remainder(right, right_top)


def compare_versions(left: bytes, right: bytes, language: str | None) -> Comparison:
    """Parse two versions of a file with one language and compare their normalized forms."""
    left_file, right_file = parse(left, language), parse(right, language)
    left_normal, right_normal = normalize(left_file), normalize(right_file)
    same = equivalent(left_normal, right_normal)
    score = similarity(left_normal, right_normal)
    return Comparison(
        mode="token" if language is None else "ast",
        language=language,
        equivalent=same,
        equivalent_unordered=same or equivalent_unordered(left_file, right_file),
        similarity=score.value,
        similarity_method=score.method,
        left_parses=parses(left_file),
        right_parses=parses(right_file),
    )
