"""Markdown building blocks: escaped cells, tables and headed sections."""

from collections.abc import Sequence


def escape(text: str) -> str:
    """Return text safe inside a Markdown table cell."""
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    """Return a Markdown table with numbers right-aligned, or `None.` when there are no rows."""
    if not rows:
        return "None."
    numeric = [all(isinstance(row[i], int) for row in rows) for i in range(len(headers))]
    align = ["---:" if right else "---" for right in numeric]
    lines = [
        "| " + " | ".join(escape(header) for header in headers) + " |",
        "| " + " | ".join(align) + " |",
        *("| " + " | ".join(escape(str(value)) for value in row) + " |" for row in rows),
    ]
    return "\n".join(lines)


def section(title: str, *blocks: str) -> str:
    """Return a level-2 section whose blocks are separated by blank lines."""
    return "\n\n".join([f"## {title}", *blocks])
