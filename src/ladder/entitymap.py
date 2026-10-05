"""The entities of one version of a file, keyed for scoring, with their text lines and nesting.

A key is (qualified name, occurrence index among same-name entities in document order). A
file whose language has definition rules also gets a `<rest>` pseudo-entity: the normalized
remainder outside its top-level entities (imports, module-level statements). A file without
such rules is one `<file>` entity, as in `ladder.entities`.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from tree_sitter import Node

from ladder.entities import WHOLE_FILE, Entity, extract
from ladder.normalize import normalize_nodes
from ladder.syntax import Parsed

REST = "<rest>"
COMMENT_MARKERS_ONLY = re.compile(r"#+|/{2,}|/\*+|\*+/?|-{2,}|;+|<!--|-->")

Key = tuple[str, int]


@dataclass(frozen=True)
class EntityVersion:
    """One entity's normalized form and the normalized lines of its source text."""

    form: tuple[str, ...]
    lines: tuple[str, ...]


@dataclass(frozen=True)
class FileEntities:
    """The keyed entities of one version of a file, each one's enclosing entity, name counts."""

    versions: dict[Key, EntityVersion] = field(default_factory=dict[Key, EntityVersion])
    parents: dict[Key, Key] = field(default_factory=dict[Key, Key])
    names: Counter[str] = field(default_factory=Counter[str])


def normalized_lines(text: bytes) -> list[str]:
    """Return the lines with whitespace collapsed, leaving out blank and comment-marker lines."""
    lines: list[str] = []
    for raw in text.decode("utf-8", "replace").splitlines():
        line = " ".join(raw.split())
        if line and not COMMENT_MARKERS_ONLY.fullmatch(line):
            lines.append(line)
    return lines


def display(key: Key) -> str:
    """Return an entity key as text: its name, suffixed with #index after the first occurrence."""
    name, index = key
    return name if index == 0 else f"{name}#{index}"


def file_entities(parsed: Parsed | None) -> FileEntities:
    """Return the keyed entities of a parsed file, or no entities for an absent file."""
    if parsed is None:
        return FileEntities()
    entities = extract(parsed)
    result = FileEntities()
    open_spans: list[tuple[Key, int]] = []
    for entity in entities:
        key = (entity.name, result.names[entity.name])
        result.names[entity.name] += 1
        start, end = _span(entity, parsed)
        while open_spans and open_spans[-1][1] <= start:
            open_spans.pop()
        if open_spans:
            result.parents[key] = open_spans[-1][0]
        open_spans.append((key, end))
        lines = tuple(normalized_lines(parsed.source[start:end]))
        result.versions[key] = EntityVersion(entity.normalized.form, lines)
    if WHOLE_FILE in result.names:
        del result.names[WHOLE_FILE]
    elif parsed.tree is not None:
        top = [entity for entity in entities if entity.top_level]
        result.versions[(REST, 0)] = _rest(parsed, parsed.tree.root_node, top)
    return result


def _span(entity: Entity, parsed: Parsed) -> tuple[int, int]:
    if not entity.nodes:
        return 0, len(parsed.source)
    return entity.nodes[0].start_byte, entity.nodes[-1].end_byte


def _rest(parsed: Parsed, root: Node, top: list[Entity]) -> EntityVersion:
    skip = frozenset(node.id for entity in top for node in entity.nodes)
    form = normalize_nodes([root], parsed.source, skip).form
    pieces: list[bytes] = []
    cursor = 0
    for start, end in sorted(_span(entity, parsed) for entity in top):
        pieces.append(parsed.source[cursor:start])
        cursor = max(cursor, end)
    pieces.append(parsed.source[cursor:])
    return EntityVersion(form, tuple(normalized_lines(b"\n".join(pieces))))
