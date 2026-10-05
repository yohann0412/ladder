"""Render a resolver task's PROMPT.md from the fixed template, and the line that spawns it."""

import hashlib
import os
from collections.abc import Sequence
from pathlib import Path
from string import Template

from ladder.schemas import LlmRung, Pair

TEMPLATE_ENV = "LADDER_RESOLVER_TEMPLATE"
DEFAULT_TEMPLATE = Path(__file__).resolve().parents[2] / "resolver" / "PROMPT.md"
NO_DESCRIPTION = "(no description)"
CONFLICT_SOURCE: dict[LlmRung, str] = {
    "llm-raw": (
        "These are the conflicts git's default merge strategy left when merging PR B into "
        "PR A. Markers use the diff3 style: `<<<<<<<` opens PR A's side, `|||||||` the base, "
        "`=======` PR B's side, and `>>>>>>>` closes the region."
    ),
    "llm-post-weave": (
        "A structural merge tool (weave) ran first as git's merge driver. The files below are "
        "what it could not resolve, and `conflicted` holds its partial result with its own "
        "conflict markers."
    ),
}


def template_path() -> Path:
    """Return the prompt template: the file named by the environment, else resolver/PROMPT.md."""
    override = os.environ.get(TEMPLATE_ENV)
    return Path(override) if override else DEFAULT_TEMPLATE


def template_sha256(path: Path) -> str:
    """Return the sha256 of a template file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spawn_line(task_dir: Path) -> str:
    """Return the one fixed line the orchestrator gives a resolver subagent."""
    return f"Read {task_dir}/PROMPT.md and follow it exactly."


def render_prompt(
    template: str,
    *,
    pair: Pair,
    rung: LlmRung,
    task_dir: Path,
    output_dir: Path,
    snapshot_dir: Path,
    files: Sequence[tuple[str, Sequence[str]]],
) -> str:
    """Fill the template with the PRs' text, the directories and one table row per file."""
    rows = [
        f"| {k} | {_cell(path)} | {_cell(', '.join(types))} |"
        for k, (path, types) in enumerate(files, start=1)
    ]
    return Template(template).substitute(
        task_dir=str(task_dir),
        output_dir=str(output_dir),
        snapshot_dir=str(snapshot_dir),
        a_title=pair.a.title,
        a_body=_body(pair.a.body),
        b_title=pair.b.title,
        b_body=_body(pair.b.body),
        conflict_source=CONFLICT_SOURCE[rung],
        file_table="\n".join(rows),
    )


def _body(body: str) -> str:
    return body.strip() or NO_DESCRIPTION


def _cell(text: str) -> str:
    return text.replace("|", "\\|")
