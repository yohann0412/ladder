"""Map a path's extension to a tree-sitter grammar from the official language packs."""

from collections.abc import Callable
from functools import cache
from pathlib import PurePath

import tree_sitter_bash
import tree_sitter_c
import tree_sitter_c_sharp
import tree_sitter_cpp
import tree_sitter_css
import tree_sitter_go
import tree_sitter_html
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_json
import tree_sitter_php
import tree_sitter_python
import tree_sitter_ruby
import tree_sitter_rust
import tree_sitter_scala
import tree_sitter_typescript
from tree_sitter import Language, Parser

GRAMMARS: dict[str, Callable[[], object]] = {
    "bash": tree_sitter_bash.language,
    "c": tree_sitter_c.language,
    "c_sharp": tree_sitter_c_sharp.language,
    "cpp": tree_sitter_cpp.language,
    "css": tree_sitter_css.language,
    "go": tree_sitter_go.language,
    "html": tree_sitter_html.language,
    "java": tree_sitter_java.language,
    "javascript": tree_sitter_javascript.language,
    "json": tree_sitter_json.language,
    "php": tree_sitter_php.language_php,
    "python": tree_sitter_python.language,
    "ruby": tree_sitter_ruby.language,
    "rust": tree_sitter_rust.language,
    "scala": tree_sitter_scala.language,
    "tsx": tree_sitter_typescript.language_tsx,
    "typescript": tree_sitter_typescript.language_typescript,
}

EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".cs": "c_sharp",
    ".rb": "ruby",
    ".php": "php",
    ".sh": "bash",
    ".bash": "bash",
    ".css": "css",
    ".html": "html",
    ".htm": "html",
    ".json": "json",
    ".scala": "scala",
}


def language_for(path: str | PurePath) -> str | None:
    """Return the grammar name for a path's extension, or None when no pack covers it."""
    return EXTENSIONS.get(PurePath(path).suffix.lower())


@cache
def parser_for(language: str) -> Parser:
    """Return the cached parser for a grammar name."""
    return Parser(Language(GRAMMARS[language]()))
