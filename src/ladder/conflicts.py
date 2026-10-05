"""Read the replay study's conflict taxonomy out of git merge-tree's informational messages.

One `CONFLICT (<type>): ...` line is one message, and its type is the text inside the
first parentheses: the replay study's unit of conflict counting.
"""

import re

MESSAGE_PREFIX = "CONFLICT ("


def conflict_messages(output: str) -> list[str]:
    """Return every line of merge-tree output that starts with `CONFLICT (`, in output order."""
    return [line for line in output.splitlines() if line.startswith(MESSAGE_PREFIX)]


def conflict_type(message: str) -> str:
    """Return the text inside a conflict message's first parentheses, such as `content`."""
    return message.removeprefix(MESSAGE_PREFIX).split(")", 1)[0]


def mentions(message: str, path: str) -> bool:
    """Return whether a conflict message names the path as a whole word, not inside a longer one."""
    pattern = rf"(?:(?<=\s)|(?<=->)){re.escape(path)}(?=$|\s|->|[.,;:](?:\s|$))"
    return re.search(pattern, message) is not None


def types_for_path(path: str, messages: list[str]) -> list[str]:
    """Return the type of every message that names the path, in message order."""
    return [conflict_type(message) for message in messages if mentions(message, path)]
