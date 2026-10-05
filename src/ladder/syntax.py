"""Parse a file's bytes with its grammar and check that the parse has no errors."""

from collections.abc import Iterator
from dataclasses import dataclass

from tree_sitter import Node, Tree

from ladder.languages import parser_for


@dataclass(frozen=True)
class Parsed:
    """A file's LF-normalized bytes and, when its language has a grammar, its syntax tree."""

    source: bytes
    language: str | None
    tree: Tree | None


def to_lf(data: bytes) -> bytes:
    """Return the bytes with CRLF and lone CR line endings replaced by LF."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def parse(data: bytes, language: str | None) -> Parsed:
    """Normalize line endings, then parse with the language's grammar when there is one."""
    source = to_lf(data)
    tree = None if language is None else parser_for(language).parse(source)
    return Parsed(source=source, language=language, tree=tree)


def walk(node: Node) -> Iterator[Node]:
    """Yield a node and all its descendants in document order."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))


def parses(parsed: Parsed) -> bool | None:
    """Return whether the tree has no ERROR or MISSING node, or None without a grammar."""
    if parsed.tree is None:
        return None
    root = parsed.tree.root_node
    return not root.has_error and not any(node.is_missing for node in walk(root))
