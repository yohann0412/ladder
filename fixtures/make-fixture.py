#!/usr/bin/env python3
"""Build the textkit fixture: a source repository, emulated GitHub origins, traps, a manifest.

Usage: python fixtures/make-fixture.py OUTDIR [--record]

Every commit is written with git plumbing under an isolated configuration with fixed
identities and dates, so every build yields the same object ids. By default the built ids
are checked against fixtures/pairs.json; --record rewrites that file with them instead.
"""

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, cast

MANIFEST = Path(__file__).resolve().parent / "pairs.json"
BASE_TIME = datetime(2025, 1, 1, tzinfo=UTC)
IDENTITY = {
    "GIT_AUTHOR_NAME": "textkit-dev",
    "GIT_AUTHOR_EMAIL": "dev@textkit.invalid",
    "GIT_COMMITTER_NAME": "textkit-dev",
    "GIT_COMMITTER_EMAIL": "dev@textkit.invalid",
}
GIT_FLAGS = ("-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main")

OPEN_A = timedelta(hours=9)
COMMIT_A = timedelta(hours=9, minutes=30)
OPEN_B = timedelta(hours=10)
COMMIT_B = timedelta(hours=10, minutes=30)
MERGE_A = timedelta(hours=12)
UPDATE_B = timedelta(hours=13)
MERGE_B = timedelta(hours=14)

Files = dict[str, str]
Changes = dict[str, str | None]
Flow = Literal["merge", "absorb", "rebase"]
Json = dict[str, object]


class FixtureError(Exception):
    """Raised when the fixture cannot be built as designed."""


# ----------------------------------------------------------------------------- project text

PYPROJECT = """[project]
name = "textkit"
version = "0.1.0"
description = "Tiny helpers for comma-separated text."
requires-python = ">=3.10"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
"""

README = """# textkit

Tiny helpers for comma-separated text.

```python
from textkit.core import format, parse

parse("a, b")       # ["a", "b"]
format(["a", "b"])  # "a,b"
```
"""

HEADER = '''"""Small helpers for comma-separated text."""

from textkit.helpers import normalize'''

PARSE = '''def parse(text):
    """Split comma-separated text into normalized fields."""
    return [normalize(value) for value in text.split(",")]'''

FORMAT = '''def format(fields):
    """Join fields back into comma-separated text."""
    return ",".join(fields)'''

VALIDATE = '''def validate(fields):
    """Return True when every field is non-empty."""
    return all(fields)'''

SUMMARIZE = '''def summarize(text):
    """Return the number of fields in the text."""
    return len(parse(text))'''

HELPERS = '''"""Low-level helpers shared by the core functions."""


def normalize(value):
    """Return the value without surrounding whitespace."""
    return value.strip()
'''

TEST_CORE = """from textkit.core import format, parse, summarize, validate


def test_parse_splits_on_commas():
    assert parse("a,b,c") == ["a", "b", "c"]


def test_parse_strips_fields():
    assert parse(" a , b ") == ["a", "b"]


def test_parse_single_field():
    assert parse("solo") == ["solo"]


def test_format_joins_with_commas():
    assert format(["a", "b"]) == "a,b"


def test_format_empty():
    assert format([]) == ""


def test_validate_accepts_filled_fields():
    assert validate(["a", "b"])


def test_validate_rejects_empty_field():
    assert not validate(["a", ""])


def test_summarize_counts_fields():
    assert summarize("a,b,c") == 3


def test_round_trip():
    assert format(parse("a, b")) == "a,b"
"""

TEST_HELPERS = """from textkit.helpers import normalize


def test_normalize_strips_spaces():
    assert normalize("  a ") == "a"


def test_normalize_keeps_inner_text():
    assert normalize("a b") == "a b"
"""


def core(
    parse: str = PARSE,
    fmt: str = FORMAT,
    validate: str = VALIDATE,
    summarize: str = SUMMARIZE,
    header: str = HEADER,
) -> str:
    """Assemble textkit/core.py from its blocks, two blank lines apart."""
    return "\n\n\n".join([header, parse, fmt, validate, summarize]) + "\n"


def edit(text: str, old: str, new: str) -> str:
    """Return text with its single occurrence of old replaced by new."""
    if text.count(old) != 1:
        raise FixtureError(f"expected exactly one occurrence of {old!r}")
    return text.replace(old, new)


def gap(*blocks: str) -> str:
    """Join top-level blocks with two blank lines, as they sit in a module."""
    return "\n\n\n".join(blocks)


BASE_FILES: Files = {
    "README.md": README,
    "pyproject.toml": PYPROJECT,
    "textkit/__init__.py": '"""Tiny helpers for comma-separated text."""\n',
    "textkit/core.py": core(),
    "textkit/helpers.py": HELPERS,
    "textkit/utils/__init__.py": '"""Utility helpers."""\n',
    "tests/test_core.py": TEST_CORE,
    "tests/test_helpers.py": TEST_HELPERS,
}

# fx01: different functions, insertions into the same gap.

PARSE_EMPTY = '''def parse(text):
    """Split comma-separated text into normalized fields."""
    if not text:
        return []
    return [normalize(value) for value in text.split(",")]'''

PARSE_LINES = '''def parse_lines(text):
    """Parse every line of the text into its own list of fields."""
    return [parse(line) for line in text.splitlines()]'''

RENDER_ROWS = '''def render_rows(rows):
    """Format every row of fields as one line of comma-separated text."""
    return [format(row) for row in rows]'''

FORMAT_STRIP = '''def format(fields):
    """Join fields back into comma-separated text."""
    return ",".join(field.strip() for field in fields)'''

TEST_PARSE_LINES = r"""from textkit.core import parse, parse_lines


def test_parse_empty_text_has_no_fields():
    assert parse("") == []


def test_parse_lines_splits_rows():
    assert parse_lines("a,b\nc") == [["a", "b"], ["c"]]
"""

TEST_RENDER_ROWS = """from textkit.core import format, render_rows


def test_format_strips_fields():
    assert format([" a", "b "]) == "a,b"


def test_render_rows():
    assert render_rows([["a", "b"], ["c"]]) == ["a,b", "c"]
"""

# fx02: compatible edits inside parse().

PARSE_GUARD = '''def parse(text):
    """Split comma-separated text into normalized fields."""
    if not isinstance(text, str):
        raise TypeError("parse() expects a string")
    return [normalize(value) for value in text.split(",")]'''

PARSE_SKIP_BLANK = '''def parse(text):
    """Split comma-separated text into normalized fields."""
    return [normalize(value) for value in text.split(",") if value.strip()]'''

PARSE_GUARD_SKIP_BLANK = '''def parse(text):
    """Split comma-separated text into normalized fields."""
    if not isinstance(text, str):
        raise TypeError("parse() expects a string")
    return [normalize(value) for value in text.split(",") if value.strip()]'''

TEST_PARSE_TYPES = """import pytest

from textkit.core import parse


def test_parse_rejects_non_strings():
    with pytest.raises(TypeError):
        parse(None)
"""

TEST_PARSE_BLANKS = """from textkit.core import parse


def test_parse_skips_blank_fields():
    assert parse("a,,b, ") == ["a", "b"]
"""

# fx03: incompatible edits inside parse().

PARSE_SOURCE = '''def parse(source):
    """Split comma-separated text into normalized fields."""
    return [normalize(value) for value in source.split(",")]'''

PARSE_REWRITE = '''def parse(text):
    """Split comma-separated text into normalized fields."""
    fields = text.replace(";", ",").split(",")
    return [normalize(f) for f in fields if f]'''

PARSE_SOURCE_REWRITE = '''def parse(source):
    """Split comma-separated text into normalized fields."""
    fields = source.replace(";", ",").split(",")
    return [normalize(f) for f in fields if f]'''

TEST_PARSE_KEYWORD = """from textkit.core import parse


def test_parse_accepts_source_keyword():
    assert parse(source="a,b") == ["a", "b"]
"""

TEST_PARSE_EMPTY = """from textkit.core import parse


def test_parse_accepts_semicolons_and_drops_empty_fields():
    assert parse("a;b,,c") == ["a", "b", "c"]
"""

# fx04: modify/delete of the helpers module.

HELPERS_COLLAPSE = '''"""Low-level helpers shared by the core functions."""


def normalize(value):
    """Return the value with runs of whitespace collapsed to single spaces."""
    return " ".join(value.split())
'''

HEADER_NO_IMPORT = '"""Small helpers for comma-separated text."""'

PARSE_INLINE_STRIP = '''def parse(text):
    """Split comma-separated text into normalized fields."""
    return [value.strip() for value in text.split(",")]'''

PARSE_INLINE_COLLAPSE = '''def parse(text):
    """Split comma-separated text into normalized fields."""
    return [" ".join(value.split()) for value in text.split(",")]'''

TEST_WHITESPACE = """from textkit.core import parse


def test_parse_collapses_inner_whitespace():
    assert parse("a   b , c") == ["a b", "c"]
"""

# fx05: add/add of the retry module.

RETRY_A = '''"""Retry a flaky callable."""


def retry(fn, attempts=3):
    """Call fn until it succeeds, trying at most attempts times."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception:
            if attempt == attempts:
                raise
    return None
'''

RETRY_B = '''"""Retry helpers with an optional pause between attempts."""

import time


class RetryError(Exception):
    """Raised when every attempt failed."""


def retry(fn, attempts=3, delay=0.0):
    """Call fn up to attempts times, sleeping delay seconds after each failure."""
    for _ in range(attempts):
        try:
            return fn()
        except Exception:
            time.sleep(delay)
    raise RetryError(f"gave up after {attempts} attempts")
'''

RETRY_COMBINED = '''"""Retry a flaky callable, optionally pausing between attempts."""

import time


class RetryError(Exception):
    """Raised when every attempt failed."""


def retry(fn, attempts=3, delay=0.0):
    """Call fn until it succeeds, trying at most attempts times."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as error:
            if attempt == attempts:
                raise RetryError(f"gave up after {attempts} attempts") from error
            time.sleep(delay)
    return None
'''

TEST_RETRY = """from textkit.utils.retry import retry


def test_retry_returns_after_transient_failures():
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("not yet")
        return "ok"

    assert retry(flaky) == "ok"
    assert len(calls) == 3
"""

TEST_RETRY_DELAY = """import pytest

from textkit.utils.retry import RetryError, retry


def test_retry_raises_retry_error_when_every_attempt_fails():
    def broken():
        raise ValueError("always")

    with pytest.raises(RetryError):
        retry(broken, attempts=2, delay=0.0)
"""

# fx06: semantic conflict between a changed return type and a new caller.

SUMMARIZE_DICT = '''def summarize(text):
    """Return the number of fields and characters in the text."""
    return {"fields": len(parse(text)), "characters": len(text)}'''

REPORT = '''"""Human-readable reports about comma-separated text."""

from textkit.core import summarize


def report(text):
    """Describe how many fields the text has."""
    count = summarize(text)
    noun = "field" if count == 1 else "fields"
    return f"{count} {noun}"
'''

TEST_REPORT = """from textkit.report import report


def test_report_counts_fields():
    assert report("a,b") == "2 fields"


def test_report_uses_singular_for_one_field():
    assert report("a") == "1 field"
"""

# fx07: both sides rewrite validate()'s return line; only A's change is tested.

VALIDATE_BLANK = '''def validate(fields):
    """Return True when every field is non-empty."""
    return all(field.strip() for field in fields)'''

VALIDATE_LIMIT = '''def validate(fields):
    """Return True when every field is non-empty."""
    return len(fields) <= 10 and "" not in fields'''

VALIDATE_BOTH = '''def validate(fields):
    """Return True when every field is non-empty."""
    return len(fields) <= 10 and all(field.strip() for field in fields)'''

TEST_VALIDATE_BLANK = """from textkit.core import validate


def test_validate_rejects_whitespace_only_fields():
    assert not validate(["a", "   "])


def test_validate_accepts_padded_fields():
    assert validate(["a", " b "])
"""

# fx08: conflicting edits of format(); B absorbs main after A was squash-merged.

FORMAT_SPACED = '''def format(fields):
    """Join fields back into comma-separated text."""
    return ", ".join(fields)'''

FORMAT_STR = '''def format(fields):
    """Join fields back into comma-separated text."""
    return ",".join(str(field) for field in fields)'''

FORMAT_SPACED_STR = '''def format(fields):
    """Join fields back into comma-separated text."""
    return ", ".join(str(field) for field in fields)'''

TEST_CORE_SPACED = edit(
    edit(
        TEST_CORE,
        'assert format(["a", "b"]) == "a,b"',
        'assert format(["a", "b"]) == "a, b"',
    ),
    'assert format(parse("a, b")) == "a,b"',
    'assert format(parse("a, b")) == "a, b"',
)

TEST_FORMAT_VALUES = """from textkit.core import format


def test_format_accepts_numbers():
    assert format([1, 2.5]) == format(["1", "2.5"])
"""

# fx09: clean control.

SLUG = '''"""Turn text into URL-friendly slugs."""


def slugify(text):
    """Lower-case the text and join its words with hyphens."""
    return "-".join(text.lower().split())
'''

TEST_SLUG = """from textkit.utils.slug import slugify


def test_slugify_joins_lower_case_words():
    assert slugify("Hello  World") == "hello-world"
"""

README_DEV = README + "\n## Development\n\nRun `python -m pytest` from the repository root.\n"

# fx10: overlapping summarize() fixes; B is rebased onto main after A was squash-merged.

SUMMARIZE_LIST = '''def summarize(text):
    """Return the number of fields in the text."""
    return len([field for field in parse(text) if field])'''

SUMMARIZE_SUM = '''def summarize(text):
    """Return the number of fields in the text."""
    return sum(1 for field in parse(text) if field)'''

TEST_CORE_SKIP_EMPTY = (
    TEST_CORE
    + """

def test_summarize_skips_empty_fields():
    assert summarize("a,,b") == 2
"""
)

TEST_SUMMARY = """from textkit.core import summarize


def test_summarize_ignores_blank_fields():
    assert summarize("a, ,b") == 2
"""

README_SUMMARY = edit(
    README, 'format(["a", "b"])  # "a,b"\n', 'format(["a", "b"])  # "a,b"\nsummarize("a,,b")  # 2\n'
)


# ----------------------------------------------------------------------------- scenarios


@dataclass(frozen=True)
class Pr:
    """One emulated pull request: its agent, its text and its changes against base."""

    number: int
    agent: str
    ref: str
    title: str
    body: str
    changes: Changes


@dataclass(frozen=True)
class Trap:
    """A planted wrong resolution that keeps PR A's version of one conflicted file."""

    path: str
    rationale: str


@dataclass(frozen=True)
class Scenario:
    """Two concurrent PRs from base, how both were merged, and what the human kept."""

    n: int
    title: str
    description: str
    a: Pr
    b: Pr
    flow: Flow
    resolution: Changes | None
    has_truth: bool = True
    trap: Trap | None = None

    @property
    def pair_id(self) -> str:
        """Return the scenario's pair id."""
        return f"fx{self.n:02d}"

    def at(self, offset: timedelta) -> datetime:
        """Return a fixed time on this scenario's own day."""
        return BASE_TIME + timedelta(days=self.n) + offset


SCENARIOS = [
    Scenario(
        n=1,
        title="Different functions, same file",
        description=(
            "A edits parse() and adds parse_lines() after it; B edits format() and adds "
            "render_rows() before it. Both insertions land in the same gap of core.py."
        ),
        a=Pr(
            number=1,
            agent="OpenAI_Codex",
            ref="codex/parse-lines",
            title="Add parse_lines and return no fields for empty text",
            body=(
                "Adds a `parse_lines()` helper that parses multi-line input row by row and makes "
                "`parse()` return an empty list for empty text. Tests cover both."
            ),
            changes={
                "textkit/core.py": core(parse=gap(PARSE_EMPTY, PARSE_LINES)),
                "tests/test_parse_lines.py": TEST_PARSE_LINES,
            },
        ),
        b=Pr(
            number=2,
            agent="Copilot",
            ref="copilot/render-rows",
            title="Add render_rows and trim fields in format",
            body=(
                "This PR makes `format()` trim each field before joining and adds "
                "`render_rows()` to format several rows at once. New tests are included."
            ),
            changes={
                "textkit/core.py": core(fmt=gap(RENDER_ROWS, FORMAT_STRIP)),
                "tests/test_render_rows.py": TEST_RENDER_ROWS,
            },
        ),
        flow="merge",
        resolution={
            "textkit/core.py": core(
                parse=gap(PARSE_EMPTY, PARSE_LINES), fmt=gap(RENDER_ROWS, FORMAT_STRIP)
            )
        },
    ),
    Scenario(
        n=2,
        title="Same function, compatible edits",
        description=(
            "A adds a type guard as the first statement of parse(); B changes parse()'s "
            "return statement to skip blank fields. The edits are adjacent lines."
        ),
        a=Pr(
            number=3,
            agent="Devin",
            ref="devin/1735894800-parse-type-guard",
            title="Reject non-string input in parse",
            body=(
                "`parse()` now raises a clear `TypeError` when it is given something other "
                "than a string instead of failing inside `split`. Added a regression test."
            ),
            changes={
                "textkit/core.py": core(parse=PARSE_GUARD),
                "tests/test_parse_types.py": TEST_PARSE_TYPES,
            },
        ),
        b=Pr(
            number=4,
            agent="Devin",
            ref="devin/1735898400-skip-blank-fields",
            title="Skip blank fields when parsing",
            body=(
                "Blank fields such as the middle of `a,,b` are now dropped by `parse()`. "
                "Added a test for the new behaviour."
            ),
            changes={
                "textkit/core.py": core(parse=PARSE_SKIP_BLANK),
                "tests/test_parse_blanks.py": TEST_PARSE_BLANKS,
            },
        ),
        flow="merge",
        resolution={"textkit/core.py": core(parse=PARSE_GUARD_SKIP_BLANK)},
    ),
    Scenario(
        n=3,
        title="Same function, incompatible edits",
        description=(
            "A renames parse()'s parameter text to source; B rewrites parse()'s body with "
            "the old name. The correct resolution is B's body written with A's name."
        ),
        a=Pr(
            number=5,
            agent="OpenAI_Codex",
            ref="codex/rename-parse-arg",
            title="Rename parse argument to source",
            body=(
                "Renames the `text` parameter of `parse()` to `source` so keyword callers "
                "read naturally. No behaviour change; adds a keyword-call test."
            ),
            changes={
                "textkit/core.py": core(parse=PARSE_SOURCE),
                "tests/test_parse_keyword.py": TEST_PARSE_KEYWORD,
            },
        ),
        b=Pr(
            number=6,
            agent="OpenAI_Codex",
            ref="codex/parse-semicolons",
            title="Accept semicolons and drop empty fields in parse",
            body=(
                "Rewrites `parse()` to treat semicolons like commas and to skip empty fields, "
                "so `a;b,,c` parses to three fields. Adds a test."
            ),
            changes={
                "textkit/core.py": core(parse=PARSE_REWRITE),
                "tests/test_parse_empty.py": TEST_PARSE_EMPTY,
            },
        ),
        flow="merge",
        resolution={"textkit/core.py": core(parse=PARSE_SOURCE_REWRITE)},
    ),
    Scenario(
        n=4,
        title="Modify/delete",
        description=(
            "A changes normalize() in helpers.py; B deletes helpers.py and inlines .strip() "
            "in parse(). The human deletes the module and inlines A's expression."
        ),
        a=Pr(
            number=7,
            agent="Copilot",
            ref="copilot/collapse-whitespace",
            title="Collapse inner whitespace in normalize",
            body=(
                "`normalize()` now collapses runs of whitespace inside a value to a single "
                "space in addition to trimming it. Adds a parse-level test."
            ),
            changes={
                "textkit/helpers.py": HELPERS_COLLAPSE,
                "tests/test_whitespace.py": TEST_WHITESPACE,
            },
        ),
        b=Pr(
            number=8,
            agent="Devin",
            ref="devin/1736071200-inline-normalize",
            title="Inline normalize and remove the helpers module",
            body=(
                "`textkit.helpers` only wrapped `str.strip`, so this inlines the call in "
                "`parse()` and deletes the module and its tests."
            ),
            changes={
                "textkit/core.py": core(header=HEADER_NO_IMPORT, parse=PARSE_INLINE_STRIP),
                "textkit/helpers.py": None,
                "tests/test_helpers.py": None,
            },
        ),
        flow="merge",
        resolution={
            "textkit/core.py": core(header=HEADER_NO_IMPORT, parse=PARSE_INLINE_COLLAPSE),
            "textkit/helpers.py": None,
        },
    ),
    Scenario(
        n=5,
        title="Add/add",
        description=(
            "Both PRs add textkit/utils/retry.py with different contents, each with its own "
            "test file. The human combines both into one module."
        ),
        a=Pr(
            number=9,
            agent="Copilot",
            ref="copilot/add-retry",
            title="Add retry utility",
            body=(
                "Adds `textkit.utils.retry.retry()`, which calls a function until it succeeds "
                "or the attempt budget runs out. Includes a unit test."
            ),
            changes={"textkit/utils/retry.py": RETRY_A, "tests/test_retry.py": TEST_RETRY},
        ),
        b=Pr(
            number=10,
            agent="Copilot",
            ref="copilot/retry-with-delay",
            title="Add retry helper with delay and RetryError",
            body=(
                "Introduces `retry(fn, attempts, delay)` with an optional pause between "
                "attempts and a dedicated `RetryError` raised when every attempt fails."
            ),
            changes={
                "textkit/utils/retry.py": RETRY_B,
                "tests/test_retry_delay.py": TEST_RETRY_DELAY,
            },
        ),
        flow="merge",
        resolution={"textkit/utils/retry.py": RETRY_COMBINED},
    ),
    Scenario(
        n=6,
        title="Semantic conflict, no textual overlap",
        description=(
            "A makes summarize() return a dict; B adds report.py, which formats summarize()'s "
            "result as an int. Git merges cleanly and the merge fails B's test."
        ),
        a=Pr(
            number=11,
            agent="Cursor",
            ref="cursor/summary-dict-5f2a",
            title="Return a summary dict from summarize",
            body=(
                "`summarize()` now returns a dict with field and character counts instead of a "
                "bare integer. Tests updated accordingly."
            ),
            changes={
                "textkit/core.py": core(summarize=SUMMARIZE_DICT),
                "tests/test_core.py": edit(
                    TEST_CORE,
                    'assert summarize("a,b,c") == 3',
                    'assert summarize("a,b,c") == {"fields": 3, "characters": 5}',
                ),
            },
        ),
        b=Pr(
            number=12,
            agent="OpenAI_Codex",
            ref="codex/add-report",
            title="Add text report helper",
            body=(
                "Adds `textkit.report.report()`, which renders the field count from "
                "`summarize()` as a short phrase such as `2 fields`. Includes tests."
            ),
            changes={"textkit/report.py": REPORT, "tests/test_report.py": TEST_REPORT},
        ),
        flow="merge",
        resolution=None,
        has_truth=False,
    ),
    Scenario(
        n=7,
        title="Intent-drop trap",
        description=(
            "Both PRs rewrite validate()'s return line. Only A's rule (whitespace-only fields "
            "are invalid) is tested; B's ten-field limit is not, so dropping B passes."
        ),
        a=Pr(
            number=13,
            agent="OpenAI_Codex",
            ref="codex/blank-fields-invalid",
            title="Treat whitespace-only fields as invalid",
            body=(
                "`validate()` now rejects fields that contain only whitespace, not just empty "
                "strings. Adds a test."
            ),
            changes={
                "textkit/core.py": core(validate=VALIDATE_BLANK),
                "tests/test_validate_blank.py": TEST_VALIDATE_BLANK,
            },
        ),
        b=Pr(
            number=14,
            agent="Devin",
            ref="devin/1736330400-limit-fields",
            title="Limit validate to ten fields",
            body=(
                "Records with more than ten fields are now rejected by `validate()`, matching "
                "the downstream import limit."
            ),
            changes={"textkit/core.py": core(validate=VALIDATE_LIMIT)},
        ),
        flow="merge",
        resolution={"textkit/core.py": core(validate=VALIDATE_BOTH)},
        trap=Trap(
            path="textkit/core.py",
            rationale=(
                "Kept PR A's validate() because its whitespace rule is covered by a test and "
                "the full suite passes with it."
            ),
        ),
    ),
    Scenario(
        n=8,
        title="Contaminated head, rewound",
        description=(
            "Both PRs change format()'s join. A is squash-merged; B then merges main into "
            "its branch, resolving the conflict there, and is squash-merged."
        ),
        a=Pr(
            number=15,
            agent="OpenAI_Codex",
            ref="codex/format-spacing",
            title="Add a space after commas in format",
            body=(
                "`format()` now joins fields with a comma and a space for readability. "
                "Updated the affected tests."
            ),
            changes={
                "textkit/core.py": core(fmt=FORMAT_SPACED),
                "tests/test_core.py": TEST_CORE_SPACED,
            },
        ),
        b=Pr(
            number=16,
            agent="OpenAI_Codex",
            ref="codex/format-non-strings",
            title="Accept non-string fields in format",
            body=(
                "`format()` converts every field with `str()` so numbers can be formatted "
                "directly. Adds a test."
            ),
            changes={
                "textkit/core.py": core(fmt=FORMAT_STR),
                "tests/test_format_values.py": TEST_FORMAT_VALUES,
            },
        ),
        flow="absorb",
        resolution={"textkit/core.py": core(fmt=FORMAT_SPACED_STR)},
    ),
    Scenario(
        n=9,
        title="Clean control",
        description="A adds a slug module with a test; B edits README.md. Git merges cleanly.",
        a=Pr(
            number=17,
            agent="Copilot",
            ref="copilot/add-slugify",
            title="Add slugify utility",
            body=(
                "Adds `textkit.utils.slug.slugify()` to turn text into lower-case, "
                "hyphen-separated slugs, with a test."
            ),
            changes={"textkit/utils/slug.py": SLUG, "tests/test_slug.py": TEST_SLUG},
        ),
        b=Pr(
            number=18,
            agent="Cursor",
            ref="cursor/readme-dev-notes-91c4",
            title="Document how to run the tests",
            body="Adds a Development section to the README explaining how to run the test suite.",
            changes={"README.md": README_DEV},
        ),
        flow="merge",
        resolution=None,
    ),
    Scenario(
        n=10,
        title="Rebased after the other PR merged",
        description=(
            "Both PRs change summarize()'s return line. A is squash-merged; B is rebased onto "
            "main, keeping A's line, and is squash-merged."
        ),
        a=Pr(
            number=19,
            agent="Devin",
            ref="devin/1736586000-summarize-skip-empty",
            title="Ignore empty fields in summarize",
            body=(
                "`summarize()` no longer counts empty fields, so `a,,b` reports two fields. "
                "Adds a test."
            ),
            changes={
                "textkit/core.py": core(summarize=SUMMARIZE_LIST),
                "tests/test_core.py": TEST_CORE_SKIP_EMPTY,
            },
        ),
        b=Pr(
            number=20,
            agent="Devin",
            ref="devin/1736589600-summary-docs",
            title="Skip blank fields in summarize and document it",
            body=(
                "Makes `summarize()` skip blank fields and documents the behaviour in the "
                "README, with a test."
            ),
            changes={
                "textkit/core.py": core(summarize=SUMMARIZE_SUM),
                "README.md": README_SUMMARY,
                "tests/test_summary.py": TEST_SUMMARY,
            },
        ),
        flow="rebase",
        resolution={"textkit/core.py": core(summarize=SUMMARIZE_LIST)},
    ),
]


# ----------------------------------------------------------------------------- git


def git_date(when: datetime) -> str:
    """Render a time in git's raw date format."""
    return f"@{int(when.timestamp())} +0000"


def git_env(committed: datetime, authored: datetime) -> dict[str, str]:
    """Return an environment that isolates git from user configuration and fixes dates."""
    inherited = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return {
        **inherited,
        **IDENTITY,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_DATE": git_date(authored),
        "GIT_COMMITTER_DATE": git_date(committed),
    }


@dataclass
class Repo:
    """A git repository the fixture writes objects and refs into."""

    path: Path
    blobs: dict[str, str] = field(default_factory=dict[str, str])

    def run(
        self,
        *args: str,
        stdin: str = "",
        when: datetime = BASE_TIME,
        authored: datetime | None = None,
    ) -> str:
        """Run git in this repository and return its stripped output; raise on failure."""
        proc = subprocess.run(
            ["git", *GIT_FLAGS, *args],
            cwd=self.path,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=git_env(when, authored or when),
            check=False,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip()
            raise FixtureError(f"git {' '.join(args)} exited {proc.returncode}: {detail}")
        return proc.stdout.strip()

    def blob(self, content: str) -> str:
        """Store a file's content and return its blob id."""
        if content not in self.blobs:
            self.blobs[content] = self.run("hash-object", "-w", "--stdin", stdin=content)
        return self.blobs[content]

    def tree(self, files: Files) -> str:
        """Store a tree holding exactly these files and return its id."""
        entries: list[str] = []
        subdirs: dict[str, Files] = {}
        for path, content in files.items():
            head, slash, rest = path.partition("/")
            if slash:
                subdirs.setdefault(head, {})[rest] = content
            else:
                entries.append(f"100644 blob {self.blob(content)}\t{head}")
        entries += [f"040000 tree {self.tree(sub)}\t{name}" for name, sub in subdirs.items()]
        return self.run("mktree", stdin="\n".join(entries) + "\n")

    def tree_of(self, commit: str) -> str:
        """Return the tree id of a commit."""
        return self.run("rev-parse", f"{commit}^{{tree}}")

    def commit(
        self,
        tree: str,
        parents: list[str],
        message: str,
        when: datetime,
        authored: datetime | None = None,
    ) -> str:
        """Create a commit with fixed identity and dates and return its id."""
        flags = [flag for parent in parents for flag in ("-p", parent)]
        return self.run(
            "commit-tree",
            tree,
            *flags,
            "-F",
            "-",
            stdin=message + "\n",
            when=when,
            authored=authored,
        )

    def clean_merge(self, left: str, right: str) -> str:
        """Return the tree of git's merge of two commits; raise if it conflicts."""
        return self.run("merge-tree", "--write-tree", left, right).splitlines()[0]

    def set_branch(self, name: str, commit: str) -> None:
        """Point a branch at a commit."""
        self.run("update-ref", f"refs/heads/{name}", commit)


# ----------------------------------------------------------------------------- build


@dataclass(frozen=True)
class Heads:
    """The commits one scenario produced."""

    a: str
    b: str
    main: str
    resolved: str | None
    extra: dict[str, str]


def apply(files: Files, changes: Changes) -> Files:
    """Return files with changes applied; a None change deletes the path."""
    result = dict(files)
    for path, content in changes.items():
        if content is None:
            result.pop(path, None)
        else:
            result[path] = content
    return result


def resolved_files(s: Scenario) -> Files:
    """Return the human resolution's files: both sides' changes, then the human's choices."""
    if s.resolution is None:
        raise FixtureError(f"{s.pair_id} has no resolution")
    both = {p for p in s.a.changes.keys() & s.b.changes.keys() if s.a.changes[p] != s.b.changes[p]}
    if not both <= s.resolution.keys():
        raise FixtureError(f"{s.pair_id} resolution misses {sorted(both - s.resolution.keys())}")
    return apply(apply(apply(BASE_FILES, s.a.changes), s.b.changes), s.resolution)


def merge_message(pr: Pr) -> str:
    """Return GitHub's merge-commit message for a PR."""
    return f"Merge pull request #{pr.number} from {pr.ref}\n\n{pr.title}"


def squash_message(pr: Pr) -> str:
    """Return GitHub's squash-merge subject for a PR."""
    return f"{pr.title} (#{pr.number})"


def build_merge(repo: Repo, s: Scenario, base: str, a: str, b: str) -> Heads:
    """Merge A then B into main with true merge commits, the second holding the resolution."""
    first = repo.commit(repo.tree_of(a), [base, a], merge_message(s.a), s.at(MERGE_A))
    tree = repo.clean_merge(first, b) if s.resolution is None else repo.tree(resolved_files(s))
    second = repo.commit(tree, [first, b], merge_message(s.b), s.at(MERGE_B))
    return Heads(a, b, second, second if s.has_truth else None, {})


def build_absorb(repo: Repo, s: Scenario, base: str, a: str, b: str) -> Heads:
    """Squash-merge A, merge main into B with the resolution, then squash-merge B."""
    first = repo.commit(repo.tree_of(a), [base], squash_message(s.a), s.at(MERGE_A))
    absorbed = repo.commit(
        repo.tree(resolved_files(s)),
        [b, first],
        f"Merge branch 'main' into {s.b.ref}",
        s.at(UPDATE_B),
    )
    second = repo.commit(repo.tree_of(absorbed), [first], squash_message(s.b), s.at(MERGE_B))
    return Heads(a, absorbed, second, absorbed, {f"b-pre/{s.n}": b})


def build_rebase(repo: Repo, s: Scenario, base: str, a: str, b: str) -> Heads:
    """Squash-merge A, rebase B onto main with the resolution, then squash-merge B."""
    first = repo.commit(repo.tree_of(a), [base], squash_message(s.a), s.at(MERGE_A))
    rebased = repo.commit(
        repo.tree(resolved_files(s)), [first], s.b.title, s.at(UPDATE_B), s.at(COMMIT_B)
    )
    second = repo.commit(repo.tree_of(rebased), [first], squash_message(s.b), s.at(MERGE_B))
    return Heads(a, rebased, second, second, {f"b-pre/{s.n}": b})


FLOWS: dict[Flow, Callable[[Repo, Scenario, str, str, str], Heads]] = {
    "merge": build_merge,
    "absorb": build_absorb,
    "rebase": build_rebase,
}


def publish_origin(out: Path, repo: Repo, s: Scenario, heads: Heads) -> str:
    """Create the scenario's bare origin with GitHub-style refs; return its relative path."""
    relative = f"origins/{s.pair_id}.git"
    origin = Repo(out / relative)
    origin.path.mkdir(parents=True)
    origin.run("init", "--quiet", "--bare")
    origin.run("config", "uploadpack.allowFilter", "true")
    origin.run("config", "uploadpack.allowAnySHA1InWant", "true")
    refs = {
        "refs/heads/main": heads.main,
        f"refs/pull/{s.a.number}/head": heads.a,
        f"refs/pull/{s.b.number}/head": heads.b,
        f"refs/heads/{s.a.ref}": heads.a,
        f"refs/heads/{s.b.ref}": heads.b,
    }
    repo.run("push", "--quiet", str(origin.path), *(f"{sha}:{ref}" for ref, sha in refs.items()))
    return relative


def write_trap(out: Path, s: Scenario) -> str | None:
    """Write the scenario's planted resolution, if any; return its relative directory."""
    if s.trap is None:
        return None
    relative = f"traps/{s.pair_id}"
    target = out / relative / "files" / s.trap.path
    target.parent.mkdir(parents=True)
    target.write_bytes(apply(BASE_FILES, s.a.changes)[s.trap.path].encode())
    rationale = {"files": [{"path": s.trap.path, "action": "keep", "rationale": s.trap.rationale}]}
    (out / relative / "rationale.json").write_text(dumps(rationale), encoding="utf-8")
    return relative


def timestamp(when: datetime) -> str:
    """Render a UTC time as ISO 8601 with a Z suffix."""
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def pr_record(pr: Pr, branch: str, head: str, opened: datetime, merged: datetime) -> Json:
    """Return the manifest entry of one PR."""
    return {
        "number": pr.number,
        "agent": pr.agent,
        "title": pr.title,
        "body": pr.body,
        "branch": branch,
        "head": head,
        "created_at": timestamp(opened),
        "closed_at": timestamp(merged),
        "merged_at": timestamp(merged),
    }


def build_scenario(out: Path, repo: Repo, base: str, s: Scenario) -> Json:
    """Commit one scenario, publish its origin and trap, and return its manifest entry."""
    a = repo.commit(repo.tree(apply(BASE_FILES, s.a.changes)), [base], s.a.title, s.at(COMMIT_A))
    b = repo.commit(repo.tree(apply(BASE_FILES, s.b.changes)), [base], s.b.title, s.at(COMMIT_B))
    heads = FLOWS[s.flow](repo, s, base, a, b)
    branches = {f"a/{s.n}": heads.a, f"b/{s.n}": heads.b, f"main/{s.n}": heads.main, **heads.extra}
    if heads.resolved is not None:
        branches[f"resolved/{s.n}"] = heads.resolved
    for name, commit in branches.items():
        repo.set_branch(name, commit)
    return {
        "pair_id": s.pair_id,
        "title": s.title,
        "description": s.description,
        "stratum": "same" if s.a.agent == s.b.agent else "cross",
        "base": base,
        "a": pr_record(s.a, f"a/{s.n}", heads.a, s.at(OPEN_A), s.at(MERGE_A)),
        "b": pr_record(s.b, f"b/{s.n}", heads.b, s.at(OPEN_B), s.at(MERGE_B)),
        "resolved_branch": None if heads.resolved is None else f"resolved/{s.n}",
        "resolved": heads.resolved,
        "trap_dir": write_trap(out, s),
        "origin": publish_origin(out, repo, s, heads),
    }


def build(out: Path) -> Json:
    """Build the whole fixture into an empty directory and return its manifest."""
    if out.exists() and any(out.iterdir()):
        raise FixtureError(f"{out} is not empty")
    repo = Repo(out / "repo")
    repo.path.mkdir(parents=True)
    repo.run("init", "--quiet")
    base = repo.commit(repo.tree(BASE_FILES), [], "Create textkit package", BASE_TIME)
    repo.set_branch("base", base)
    scenarios = [build_scenario(out, repo, base, s) for s in SCENARIOS]
    repo.run("checkout", "--quiet", "base")
    return {"scenarios": scenarios}


# ----------------------------------------------------------------------------- manifest


def dumps(value: object) -> str:
    """Serialize JSON the way every fixture file is written."""
    return json.dumps(value, indent=2) + "\n"


def flatten(value: object, prefix: str = "") -> dict[str, object]:
    """Map every leaf of a JSON value to a readable path; list items use their pair_id."""
    if isinstance(value, dict):
        items = cast("dict[str, object]", value).items()
    elif isinstance(value, list):
        items = [(label(item, i), item) for i, item in enumerate(cast("list[object]", value))]
    else:
        return {prefix: value}
    leaves: dict[str, object] = {}
    for key, item in items:
        leaves |= flatten(item, f"{prefix}.{key}" if prefix else key)
    return leaves


def label(item: object, index: int) -> str:
    """Return a list item's pair_id when it has one, else its index."""
    if isinstance(item, dict):
        pair_id = cast("dict[str, object]", item).get("pair_id")
        if isinstance(pair_id, str):
            return pair_id
    return str(index)


def differences(committed: object, built: Json) -> list[str]:
    """List every path whose committed and built values differ."""
    old, new = flatten(committed), flatten(built)
    return [
        f"{key}: committed {old.get(key)!r}, built {new.get(key)!r}"
        for key in sorted(old.keys() | new.keys())
        if old.get(key) != new.get(key)
    ]


def check(built: Json) -> int:
    """Compare the built manifest with fixtures/pairs.json and report every mismatch."""
    if not MANIFEST.is_file():
        print(f"make-fixture: {MANIFEST} is missing; run with --record", file=sys.stderr)
        return 1
    problems = differences(json.loads(MANIFEST.read_text(encoding="utf-8")), built)
    for problem in problems:
        print(f"make-fixture: mismatch {problem}", file=sys.stderr)
    return 1 if problems else 0


def main() -> int:
    """Build the fixture, then check or record fixtures/pairs.json."""
    parser = argparse.ArgumentParser(description="Build the textkit fixture repository.")
    parser.add_argument("outdir", type=Path, help="empty or missing directory to build into")
    parser.add_argument(
        "--record", action="store_true", help="rewrite fixtures/pairs.json with the built ids"
    )
    args = parser.parse_args()
    out: Path = args.outdir.resolve()
    try:
        manifest = build(out)
    except FixtureError as error:
        print(f"make-fixture: {error}", file=sys.stderr)
        return 2
    text = dumps(manifest)
    (out / "manifest.json").write_text(text, encoding="utf-8")
    if args.record:
        MANIFEST.write_text(text, encoding="utf-8")
        print(f"make-fixture: recorded {MANIFEST}")
        return 0
    return check(manifest)


if __name__ == "__main__":
    sys.exit(main())
