"""Flag PR text that mentions conflicts, rebases or merging the default branch."""

import re

from ladder.schemas import Pair

FLAGS = {
    "conflict": re.compile(r"\bconflict", re.IGNORECASE),
    "rebase": re.compile(r"\brebas", re.IGNORECASE),
    "merged-default-branch": re.compile(
        r"merg\w* (the )?(main|master|develop|default)", re.IGNORECASE
    ),
}


def pr_text_flags(pair: Pair) -> list[str]:
    """Return the names of the flags whose pattern matches either PR's title or body."""
    texts = [pair.a.title, pair.a.body, pair.b.title, pair.b.body]
    return [name for name, pattern in FLAGS.items() if any(pattern.search(t) for t in texts)]
