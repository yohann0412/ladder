"""Parse a subagent transcript (JSON lines) into its tool calls, first prompt, tokens and time."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from ladder.schemas import TokenUsage

MESSAGE_TYPES = frozenset({"assistant", "user"})


class TranscriptError(ValueError):
    """A transcript is missing or cannot be parsed, so the run cannot be audited."""


class _Envelope(BaseModel):
    type: str | None = None


class _Usage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None


class _Block(BaseModel):
    type: str
    name: str | None = None
    input: dict[str, Any] | None = None
    text: str | None = None


class _Message(BaseModel):
    id: str | None = None
    content: str | list[_Block] = ""
    usage: _Usage | None = None


class _Line(BaseModel):
    type: str
    message: _Message
    timestamp: datetime | None = None


@dataclass(frozen=True)
class ToolCall:
    """One tool_use block: the tool's name and its input."""

    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Transcript:
    """What the audit and the run record need from a transcript."""

    first_user_text: str | None
    tool_calls: list[ToolCall]
    tokens: TokenUsage | None
    duration_ms: int | None


def read_transcript(path: Path) -> Transcript:
    """Parse a transcript; raise TranscriptError when it is missing or not valid JSON lines."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise TranscriptError(f"transcript unreadable: {error}") from error
    lines: list[_Line] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            if _Envelope.model_validate_json(raw).type in MESSAGE_TYPES:
                lines.append(_Line.model_validate_json(raw))
        except ValidationError as error:
            reason = error.errors()[0]["msg"]
            raise TranscriptError(f"transcript line {number} is unparseable: {reason}") from error
    if not lines:
        raise TranscriptError("transcript holds no user or assistant message")
    return Transcript(
        first_user_text=_first_user_text(lines),
        tool_calls=[
            ToolCall(block.name or "", block.input or {})
            for line in lines
            if line.type == "assistant"
            for block in _blocks(line)
            if block.type == "tool_use"
        ],
        tokens=_tokens(lines),
        duration_ms=_duration_ms(lines),
    )


def _blocks(line: _Line) -> list[_Block]:
    content = line.message.content
    return [] if isinstance(content, str) else content


def _first_user_text(lines: list[_Line]) -> str | None:
    user = next((line for line in lines if line.type == "user"), None)
    if user is None:
        return None
    content = user.message.content
    if isinstance(content, str):
        return content
    return "".join(block.text or "" for block in content if block.type == "text")


def _tokens(lines: list[_Line]) -> TokenUsage | None:
    by_message: dict[str, _Usage] = {}
    for index, line in enumerate(lines):
        if line.type == "assistant" and line.message.usage is not None:
            by_message[line.message.id or f"line-{index}"] = line.message.usage
    if not by_message:
        return None
    usages = by_message.values()
    return TokenUsage(
        input_tokens=sum(u.input_tokens or 0 for u in usages),
        output_tokens=sum(u.output_tokens or 0 for u in usages),
        cache_creation_input_tokens=sum(u.cache_creation_input_tokens or 0 for u in usages),
        cache_read_input_tokens=sum(u.cache_read_input_tokens or 0 for u in usages),
    )


def _duration_ms(lines: list[_Line]) -> int | None:
    stamps = [line.timestamp for line in lines if line.timestamp is not None]
    if not stamps:
        return None
    return round((stamps[-1] - stamps[0]).total_seconds() * 1000)
