"""Named definitions of a file, with qualified names, in document order.

Nested definitions are qualified by their enclosing definition (`Outer.inner`). A file
without a grammar, or whose grammar has no definition rules (CSS, HTML, JSON), is one
`<file>` entity.
"""

from dataclasses import dataclass

from tree_sitter import Node

from ladder.entity_rules import RULES
from ladder.normalize import Normalized, normalize, normalize_nodes
from ladder.schemas import Record
from ladder.syntax import Parsed, parses

WHOLE_FILE = "<file>"


@dataclass(frozen=True)
class Entity:
    """One named definition: its qualified name, kind, lines, nodes and normalized form."""

    name: str
    kind: str
    start_line: int
    end_line: int
    top_level: bool
    nodes: tuple[Node, ...]
    normalized: Normalized


class EntitySummary(Record):
    """The printable part of an entity."""

    name: str
    kind: str
    start_line: int
    end_line: int


class EntityListing(Record):
    """A file's language, whether it parses, and its entities."""

    language: str | None
    parses: bool | None
    entities: list[EntitySummary]


@dataclass(frozen=True)
class _Scope:
    prefix: str
    holds_methods: bool


WRAPPERS = frozenset({"decorated_definition", "export_statement", "template_declaration"})
SINGLE_WRAPPERS = frozenset({"lexical_declaration", "variable_declaration", "type_declaration"})


def _clean(name: str) -> str:
    return " ".join(name.split()).replace("::", ".")


def _wraps(parent: Node) -> bool:
    if parent.type in WRAPPERS:
        return True
    if parent.type not in SINGLE_WRAPPERS:
        return False
    return sum(1 for child in parent.named_children if "comment" not in child.type) == 1


def _span(core: Node) -> tuple[Node, ...]:
    outer = core
    while (parent := outer.parent) is not None and _wraps(parent):
        outer = parent
    attributes: list[Node] = []
    sibling = outer.prev_named_sibling
    while sibling is not None and (sibling.type == "attribute_item" or "comment" in sibling.type):
        if sibling.type == "attribute_item":
            attributes.insert(0, sibling)
        sibling = sibling.prev_named_sibling
    return (*attributes, outer)


def _lines(nodes: tuple[Node, ...], source: bytes) -> tuple[int, int]:
    # Lines come from byte offsets: reading Point.row corrupts memory in py-tree-sitter 0.26.0.
    start = nodes[0].start_byte
    last = max(start, nodes[-1].end_byte - 1)
    return source.count(b"\n", 0, start) + 1, source.count(b"\n", 0, last) + 1


def _whole_file(parsed: Parsed) -> Entity:
    nodes = () if parsed.tree is None else (parsed.tree.root_node,)
    lines = max(1, len(parsed.source.splitlines()))
    return Entity(WHOLE_FILE, "file", 1, lines, True, nodes, normalize(parsed))


def extract(parsed: Parsed) -> list[Entity]:
    """Return a file's named definitions in document order, or one `<file>` entity."""
    rules = None if parsed.language is None else RULES.get(parsed.language)
    if parsed.tree is None or rules is None:
        return [_whole_file(parsed)]
    entities: list[Entity] = []
    stack: list[tuple[Node, _Scope | None]] = [(parsed.tree.root_node, None)]
    while stack:
        node, scope = stack.pop()
        rule = rules.get(node.type)
        named = None if rule is None else rule.namer(node, parsed.source)
        if rule is not None and named is not None:
            display, owner = _clean(named[0]), _clean(named[1])
            prefix = "" if scope is None else scope.prefix + "."
            in_type = scope is not None and scope.holds_methods
            kind = "method" if rule.kind == "function" and in_type else rule.kind
            nodes = _span(node)
            start, end = _lines(nodes, parsed.source)
            normalized = normalize_nodes(nodes, parsed.source)
            entity = Entity(prefix + display, kind, start, end, scope is None, nodes, normalized)
            entities.append(entity)
            scope = _Scope(prefix + owner, rule.holds_methods)
        stack.extend((child, scope) for child in reversed(node.children))
    return entities


def list_entities(parsed: Parsed) -> EntityListing:
    """Return the printable listing of a file's language, parse status and entities."""
    return EntityListing(
        language=parsed.language,
        parses=parses(parsed),
        entities=[
            EntitySummary(name=e.name, kind=e.kind, start_line=e.start_line, end_line=e.end_line)
            for e in extract(parsed)
        ],
    )
