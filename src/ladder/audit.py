"""Check a resolver transcript against the pre-registered tool and path rules (PLAN.md 8)."""

import itertools
import os
import re
from pathlib import Path, PurePosixPath

from ladder.schemas import ResolverTask
from ladder.transcript import ToolCall, Transcript

ALLOWED_TOOLS = frozenset({"Read", "Glob", "Grep", "Write", "SubagentHandback"})
SHOWN_CHARS = 200
GLOB_CHARS = frozenset("*?[{")
READ_OUTSIDE_TASK = re.compile(r"(Read|Grep|Glob) outside the task directory: (.+)", re.DOTALL)


def audit_transcript(transcript: Transcript, task: ResolverTask) -> list[str]:
    """Return one message per breach of the spawn line, tool and path rules, without repeats."""
    task_dir, output_dir = Path(task.task_dir), Path(task.output_dir)
    violations = _spawn_violations(transcript.first_user_text, task.spawn_line)
    for call in transcript.tool_calls:
        violations += _call_violations(call, task_dir, output_dir)
    return list(dict.fromkeys(violations))


def read_inside(violation: str, root: Path) -> bool:
    """Return whether a violation is a Read, Grep or Glob outside the task directory but in root."""
    found = READ_OUTSIDE_TASK.fullmatch(violation)
    if found is None:
        return False
    tool, value = found.groups()
    if tool == "Glob":
        return not _climbs(value) and _inside(_fixed_prefix(value), root)
    return _inside(value, root)


def _spawn_violations(first: str | None, spawn_line: str) -> list[str]:
    if first is None:
        return ["the transcript has no user message, so the spawn line cannot be checked"]
    if first.strip() != spawn_line:
        return [f"first user message is not the spawn line: {first[:SHOWN_CHARS]!r}"]
    return []


def _call_violations(call: ToolCall, task_dir: Path, output_dir: Path) -> list[str]:
    match call.name:
        case "Read":
            return _path_rule(call, "file_path", task_dir, "task directory")
        case "Glob":
            return _glob_rule(call, task_dir)
        case "Grep":
            return _path_rule(call, "path", task_dir, "task directory")
        case "Write":
            return _path_rule(call, "file_path", output_dir, "output directory")
        case name if name in ALLOWED_TOOLS:
            return []
        case name:
            return [f"disallowed tool: {name or '(unnamed)'}"]


def _path_rule(call: ToolCall, key: str, root: Path, place: str) -> list[str]:
    value = call.arguments.get(key)
    if not isinstance(value, str) or not value:
        return [f"{call.name} without a {key}"]
    if not _inside(value, root):
        return [f"{call.name} outside the {place}: {value}"]
    return []


def _glob_rule(call: ToolCall, task_dir: Path) -> list[str]:
    """A Glob names its place by a path inside the task directory, or else by its pattern."""
    if call.arguments.get("path") in (None, ""):
        return _bare_pattern(call, task_dir)
    return [*_path_rule(call, "path", task_dir, "task directory"), *_pattern(call, task_dir)]


def _pattern(call: ToolCall, task_dir: Path) -> list[str]:
    pattern = call.arguments.get("pattern")
    if not isinstance(pattern, str) or not pattern:
        return ["Glob without a pattern"]
    if ".." in PurePosixPath(pattern).parts:
        return [f"Glob pattern climbs out of its path: {pattern}"]
    if pattern.startswith("/") and not Path(os.path.normpath(pattern)).is_relative_to(task_dir):
        return [f"Glob outside the task directory: {pattern}"]
    return []


def _bare_pattern(call: ToolCall, task_dir: Path) -> list[str]:
    """Without a path, a Glob's pattern must itself be absolute and fixed inside the task dir."""
    pattern = call.arguments.get("pattern")
    if not isinstance(pattern, str) or not pattern:
        return ["Glob without a path", "Glob without a pattern"]
    if not pattern.startswith("/"):
        return [f"Glob without a path and with a relative pattern: {pattern}"]
    if _climbs(pattern):
        return [f"Glob pattern climbs out with '..': {pattern}"]
    if not _inside(_fixed_prefix(pattern), task_dir):
        return [f"Glob outside the task directory: {pattern}"]
    return []


def _climbs(pattern: str) -> bool:
    return ".." in re.split(r"[/{},]", pattern)


def _fixed_prefix(pattern: str) -> str:
    """The pattern's leading components, up to the first one holding a glob character."""
    parts = PurePosixPath(pattern).parts
    fixed = itertools.takewhile(lambda part: not GLOB_CHARS.intersection(part), parts)
    return str(PurePosixPath(*fixed))


def _inside(raw: str, root: Path) -> bool:
    path = Path(raw)
    if not path.is_absolute():
        return False
    lexical = Path(os.path.normpath(path))
    return lexical.is_relative_to(root) and path.resolve().is_relative_to(root.resolve())
