"""Every rung output of a conflicting pair, and the resolved state each one leaves on disk.

git's output is its conflicted working tree; weave's and mergiraf's are their working trees.
The trap and the LLM rungs start from git's tree (llm-post-weave from weave's) and replace or
remove each path their rationale names.
"""

import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from ladder.jsonio import read_optional
from ladder.layout import Layout
from ladder.runtime import remove_tree
from ladder.schemas import (
    GitRungResult,
    LlmRung,
    ResolverPlan,
    ResolverRun,
    ResolverTask,
    StructuralResult,
    StructuralTool,
)
from ladder.trees import copy_dir

GIT_RUNG_DIR = "git-replay"
STRUCTURAL_TOOLS: tuple[StructuralTool, ...] = ("weave", "mergiraf")
LLM_RUNGS: tuple[LlmRung, ...] = ("llm-raw", "llm-post-weave")
TRAP = "trap"
NOT_RUN = "not run"


class ScoreError(RuntimeError):
    """A pair cannot be scored: not conflicted, or a record or working tree it needs is missing."""


class RationaleEntry(BaseModel):
    """What a resolver or the trap did with one path."""

    path: str
    action: Literal["keep", "delete"]


class Rationale(BaseModel):
    """The rationale.json of a resolution directory."""

    files: list[RationaleEntry]


@dataclass(frozen=True)
class Source:
    """Where an available output's resolved state comes from."""

    start: Path
    unmerged: frozenset[str]
    overlay: Path | None = None


@dataclass(frozen=True)
class RungOutput:
    """One rung output to score: its source, or why it is not available."""

    rung: str
    run: int
    source: Source | None
    unavailable_reason: str | None

    @property
    def name(self) -> str:
        """Return its record name: score-<rung>, and score-<rung>-run-<n> from run 2 on."""
        return f"score-{self.rung}" if self.run == 1 else f"score-{self.rung}-run-{self.run}"


@dataclass(frozen=True)
class ResolvedState:
    """A materialised resolved state and the conflicted paths it still leaves unmerged."""

    tree: Path
    unresolved: frozenset[str]

    def read(self, path: str) -> bytes | None:
        """Return a file's bytes in the resolved state, or None when it is absent."""
        file = self.tree / path
        return file.read_bytes() if file.is_file() else None


def rung_outputs(layout: Layout, pair_id: str, git_rung: GitRungResult) -> list[RungOutput]:
    """Return every output of a conflicting pair: git, structural, trap and LLM runs."""
    git_dir = layout.rung_dir(pair_id, GIT_RUNG_DIR)
    if not git_dir.is_dir():
        raise ScoreError(f"git's working tree is missing at {git_dir}; rerun ladder rung git")
    git_source = Source(git_dir, frozenset(file.path for file in git_rung.files))
    outputs = [RungOutput("git", 1, git_source, None)]
    starts: dict[LlmRung, Source | None] = {"llm-raw": git_source, "llm-post-weave": None}
    for tool in STRUCTURAL_TOOLS:
        record = read_optional(layout.result_file(pair_id, f"rung-{tool}"), StructuralResult)
        if record is None:
            continue
        outputs.append(_structural(record))
        if tool == "weave":
            starts["llm-post-weave"] = outputs[-1].source
    trap_dir = layout.resolution_dir(pair_id, TRAP, 1)
    if trap_dir.is_dir():
        outputs.append(RungOutput(TRAP, 1, replace(git_source, overlay=trap_dir), None))
    plan = read_optional(layout.result_file(pair_id, "resolver-plan"), ResolverPlan)
    llm = _LlmOutputs(layout, pair_id, plan, starts)
    outputs.extend(llm.output(rung, run) for rung in LLM_RUNGS for run in _runs(plan, rung))
    return outputs


def materialise(source: Source, dest: Path) -> ResolvedState:
    """Copy an output's starting tree without .git, then apply its rationale's keeps and deletes."""
    copy_dir(source.start, dest)
    if source.overlay is None:
        return ResolvedState(dest, source.unmerged)
    text = (source.overlay / "rationale.json").read_text(encoding="utf-8")
    decided: set[str] = set()
    for entry in Rationale.model_validate_json(text).files:
        target = _inside(dest, entry.path)
        remove_tree(target)
        if entry.action == "keep":
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_inside(source.overlay / "files", entry.path), target)
        decided.add(entry.path)
    return ResolvedState(dest, source.unmerged - decided)


def _inside(root: Path, path: str) -> Path:
    target = root / path
    if not target.resolve().is_relative_to(root.resolve()):
        raise ScoreError(f"rationale path {path!r} points outside {root}")
    return target


def _structural(record: StructuralResult) -> RungOutput:
    if record.status == "error":
        return RungOutput(record.tool, 1, None, f"{record.tool} error: {record.detail}")
    source = Source(Path(record.output_dir), frozenset(record.remaining_conflicted))
    return RungOutput(record.tool, 1, source, None)


def _runs(plan: ResolverPlan | None, rung: LlmRung) -> list[int]:
    planned: list[int] = [] if plan is None else [r.run for r in plan.runs if r.rung == rung]
    return sorted({1, *planned})


@dataclass(frozen=True)
class _LlmOutputs:
    layout: Layout
    pair_id: str
    plan: ResolverPlan | None
    starts: dict[LlmRung, Source | None]

    def output(self, rung: LlmRung, run: int) -> RungOutput:
        """Return one LLM run's output, llm-raw's for an identical post-weave input."""
        task = read_optional(self._record(rung, run, "-task"), ResolverTask)
        if rung == "llm-post-weave" and task is not None and task.status == "identical_input":
            return replace(self.output("llm-raw", run), rung=rung)
        record = read_optional(self._record(rung, run), ResolverRun)
        start = self.starts[rung]
        if record is not None and record.status == "ok":
            if start is None:
                return RungOutput(rung, run, None, "no weave working tree to start from")
            overlay = self.layout.resolution_dir(self.pair_id, rung, run)
            return RungOutput(rung, run, replace(start, overlay=overlay), None)
        return RungOutput(rung, run, None, self._reason(record, task))

    def _record(self, rung: LlmRung, run: int, suffix: str = "") -> Path:
        return self.layout.result_file(self.pair_id, f"resolver-{rung}-run-{run}{suffix}")

    def _reason(self, record: ResolverRun | None, task: ResolverTask | None) -> str:
        if record is not None:
            failure = record.failure or "failed"
            return f"{failure}: {'; '.join(record.violations)}" if record.violations else failure
        if task is not None and task.status == "input_cap":
            return "input_cap"
        if self.plan is not None and self.plan.excluded_reason:
            return self.plan.excluded_reason
        return NOT_RUN
