"""F7a acceptance: AST equivalence ignores formatting and comments but not code."""

import json
from pathlib import Path

from conftest import LADDER, run

ORIGINAL = '''"""Module."""


def parse(text):
    """Split text."""
    return [f.strip() for f in text.split(",")]


class Box:
    def size(self):
        return 1
'''

REFORMATTED = '''"""Module."""
def parse( text ):
    # a comment the other side never had
    """Split text."""
    return [ f.strip()   for f in text.split( "," ) ]
class Box:
        def size(self):
                return 1
'''

STRING_CHANGED = ORIGINAL.replace('","', '";"')
REORDERED = '''"""Module."""


class Box:
    def size(self):
        return 1


def parse(text):
    """Split text."""
    return [f.strip() for f in text.split(",")]
'''


def _compare(tmp_path: Path, name: str, left: str, right: str) -> dict[str, object]:
    a, b = tmp_path / f"left-{name}", tmp_path / f"right-{name}"
    a.write_text(left)
    b.write_text(right)
    proc = run([LADDER, "compare", str(a), str(b)])
    return json.loads(proc.stdout)


def test_compare_and_entities(tmp_path: Path) -> None:
    same = _compare(tmp_path, "fmt.py", ORIGINAL, REFORMATTED)
    assert same["mode"] == "ast" and same["language"] == "python"
    assert same["equivalent"] is True and same["similarity"] == 1.0

    diff = _compare(tmp_path, "str.py", ORIGINAL, STRING_CHANGED)
    assert diff["equivalent"] is False and 0.5 < float(str(diff["similarity"])) < 1.0

    moved = _compare(tmp_path, "order.py", ORIGINAL, REORDERED)
    assert moved["equivalent"] is False and moved["equivalent_unordered"] is True

    docs = _compare(
        tmp_path, "notes.md", "# Title\n\nsome  text\nhere\n", "# Title\nsome text here\n"
    )
    assert docs["mode"] == "token" and docs["language"] is None
    assert docs["equivalent"] is True

    crlf = _compare(tmp_path, "crlf.py", ORIGINAL, ORIGINAL.replace("\n", "\r\n"))
    assert crlf["equivalent"] is True

    broken = tmp_path / "broken.py"
    broken.write_text("def parse(:\n    return\n")
    entities = tmp_path / "entities.py"
    entities.write_text(ORIGINAL)
    listing = json.loads(run([LADDER, "entities", str(entities)]).stdout)
    assert listing["parses"] is True
    assert [e["name"] for e in listing["entities"]] == ["parse", "Box", "Box.size"]
    assert json.loads(run([LADDER, "entities", str(broken)]).stdout)["parses"] is False
