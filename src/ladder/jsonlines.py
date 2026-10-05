"""Split JSON Lines text on newlines only, never inside a JSON string.

str.splitlines() also breaks on U+2028, U+2029, U+0085 and other separators that JSON
allows unescaped inside strings. A carriage return left at the end of a line is JSON
whitespace, so the parser accepts it.
"""


def json_lines(text: str) -> list[str]:
    """Return the lines of JSON Lines text, without the empty piece after a final newline."""
    lines = text.split("\n")
    return lines[:-1] if lines[-1] == "" else lines
