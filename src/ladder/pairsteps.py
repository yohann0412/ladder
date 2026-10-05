"""The steps `ladder run` takes for one pair; each runs only when its record or copy is missing.

Every step names itself in `step` before it acts, so a failure can be logged with the step
that raised.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

from ladder.cache import ensure_clone, fetch_pr
from ladder.cacherung import run_git_rung_in_cache
from ladder.claimc import run_claim_c
from ladder.gitrung import git_record_name, run_git_rung
from ladder.jsonio import read_optional, write_record
from ladder.layout import Layout
from ladder.plan import plan_pair
from ladder.prepare import GIT_RUNG_DIR, prepare_run
from ladder.resolver_records import read_plan, read_task, run_exists, unsettled_runs
from ladder.run_view import (
    claim_c_summary,
    git_summary,
    plan_summary,
    runnability_summary,
    score_summary,
    structural_summary,
    task_summary,
    truth_summary,
)
from ladder.runnable import classify_pair
from ladder.runtime import remove_tree
from ladder.schemas import (
    ClaimCRecord,
    GitRungResult,
    HeadsKind,
    Pair,
    PairRefs,
    PairSet,
    Record,
    ResolverPlan,
    ResolverTask,
    RungScore,
    Runnability,
    StructuralResult,
    StructuralTool,
    TruthRecord,
    WorkspaceRecord,
)
from ladder.score import score_pair
from ladder.structural import run_structural_rung
from ladder.trap import TRAP_RUN, TRAP_RUNG, install_trap
from ladder.truth import TRUTH, extract_truth
from ladder.workspace import build_recorded

NO_LLM_REASON = "run without resolver subagents (--no-llm)"
STRUCTURAL_TOOLS: tuple[StructuralTool, ...] = ("weave", "mergiraf")
RUNNABILITY = "runnability"
CLAIM_C = "claim-c"

Say = Callable[[str, str], None]


class StepFailedError(RuntimeError):
    """A step found the pair in a state it cannot continue from."""


@dataclass
class PairSteps:
    """The steps of one pair, the step running now, and where to say what each step did."""

    layout: Layout
    pair_set: PairSet
    pair: Pair
    say: Say
    step: str = "start"

    @property
    def pair_id(self) -> str:
        """Return the pair id."""
        return self.pair.pair_id

    def refs(self) -> PairRefs:
        """Return the pair's resolved refs; raise when resolving left it without any."""
        self.step = "resolve"
        if self.pair.refs is None:
            raise StepFailedError("the pair has no resolved refs")
        return self.pair.refs

    def git_final(self) -> None:
        """Run the in-cache git rung at final heads, when they and their merge base are known."""
        refs = self.refs()
        self.step = git_record_name("final")
        known = refs.a.final_head and refs.b.final_head and refs.final_merge_base
        if not known or self._file(self.step).exists():
            return
        self._git_in_cache("final")

    def git_replay(self) -> GitRungResult:
        """Return the replay-head git rung record, running the in-cache rung when it is missing."""
        self.step = git_record_name("replay")
        record = read_optional(self._file(self.step), GitRungResult)
        return record if record is not None else self._git_in_cache("replay")

    def ensure_workspace(self) -> WorkspaceRecord:
        """Return the replay workspace record, rebuilding the workspace when it is not on disk."""
        self.step = "workspace"
        record = read_optional(self._file("workspace-replay"), WorkspaceRecord)
        if record is not None and Path(record.path).is_dir():
            return record
        self._ensure_cache()
        self.step = "workspace"
        built = build_recorded(self.layout, self.pair, "replay")
        if built.record is None:
            failed = [check.name for check in built.verification.checks if not check.passed]
            raise StepFailedError(f"workspace verification failed: {', '.join(failed)}")
        self._say(f"workspace built at {built.path}")
        return built.record

    def ensure_git_copy(self, recorded: GitRungResult) -> None:
        """Re-run the git rung on the workspace when its working copy is missing; it must agree."""
        self.step = "git-replay copy"
        if self.layout.rung_dir(self.pair_id, GIT_RUNG_DIR).is_dir():
            return
        result = run_git_rung(self.layout, self.pair_id, "replay")
        self._say(f"git rung working copy: {git_summary(result)}")
        if _git_key(result) != _git_key(recorded):
            self._restore(
                git_record_name("replay"),
                recorded,
                self.layout.rung_dir(self.pair_id, GIT_RUNG_DIR),
                f"the workspace git rung ({git_summary(result)}) disagrees with the recorded one "
                f"({git_summary(recorded)})",
            )

    def ensure_structural(self) -> None:
        """Run weave and mergiraf when their record or working copy is missing; it must agree."""
        for tool in STRUCTURAL_TOOLS:
            self.step = f"rung-{tool}"
            record = read_optional(self._file(self.step), StructuralResult)
            if record is not None and (
                record.status == "error" or Path(record.output_dir).is_dir()
            ):
                continue
            result = run_structural_rung(self.layout, self.pair_id, tool)
            self._say(f"{tool}: {structural_summary(result)}")
            if record is not None and _structural_key(result) != _structural_key(record):
                self._restore(
                    self.step,
                    record,
                    Path(result.output_dir),
                    f"re-running {tool} ({structural_summary(result)}) disagrees with its "
                    f"record ({structural_summary(record)})",
                )

    def ensure_trap(self) -> None:
        """Install the planted resolution of a trap scenario when it is not installed."""
        self.step = "trap"
        if self.pair.trap_dir is None:
            return
        if self.layout.resolution_dir(self.pair_id, TRAP_RUNG, TRAP_RUN).is_dir():
            return
        target = install_trap(self.layout, self.pair)
        self._say(f"trap installed at {target}")

    def ensure_plan(self, no_llm: bool) -> ResolverPlan:
        """Return the resolver plan, writing it when missing; --no-llm plans no LLM run."""
        self.step = "resolver plan"
        plan = read_plan(self.layout, self.pair_id)
        if plan is not None:
            return plan
        plan = plan_pair(self.layout, self.pair, NO_LLM_REASON if no_llm else None)
        self._say(f"resolver plan: {plan_summary(plan)}")
        return plan

    def prepare_runs(self, plan: ResolverPlan) -> None:
        """Prepare every planned run that has neither a task record nor a run record."""
        for planned in plan.runs:
            self.step = f"prepare {planned.rung} run {planned.run}"
            if read_task(self.layout, self.pair_id, planned.rung, planned.run) is not None:
                continue
            if run_exists(self.layout, self.pair_id, planned.rung, planned.run):
                continue
            task = prepare_run(self.layout, self.pair_set, self.pair, planned.rung, planned.run)
            self._say(task_summary(task))

    def pending_tasks(self, plan: ResolverPlan) -> list[ResolverTask]:
        """Return the prepared tasks of planned runs still waiting for their subagent."""
        self.step = "pending"
        pending: list[ResolverTask] = []
        for planned in unsettled_runs(self.layout, plan):
            task = read_task(self.layout, self.pair_id, planned.rung, planned.run)
            if task is None:
                raise StepFailedError(f"{planned.rung} run {planned.run} was never prepared")
            pending.append(task)
        return pending

    def blocking_siblings(self) -> list[str]:
        """Return the pairs of the same repository whose resolver runs truth must wait for."""
        self.step = "truth guard"
        blocking: list[str] = []
        for other in self.pair_set.pairs:
            if other.repo != self.pair.repo or other.pair_id == self.pair_id:
                continue
            plan = read_plan(self.layout, other.pair_id)
            git = read_optional(
                self.layout.result_file(other.pair_id, git_record_name("replay")), GitRungResult
            )
            if plan is not None and unsettled_runs(self.layout, plan):
                blocking.append(f"{other.pair_id} (resolver runs pending)")
            elif plan is None and git is not None and git.status == "conflicted":
                blocking.append(f"{other.pair_id} (conflicted, no resolver plan yet)")
        return blocking

    def ensure_truth(self) -> None:
        """Extract the human resolution when the pair has no truth record."""
        self.step = TRUTH
        if read_optional(self._file(TRUTH), TruthRecord) is not None:
            return
        self._ensure_cache()
        self.step = TRUTH
        self._say(f"truth: {truth_summary(extract_truth(self.layout, self.pair))}")

    def ensure_runnability(self) -> None:
        """Classify the suite at the merge base when the pair has no runnability record."""
        self.step = RUNNABILITY
        if read_optional(self._file(RUNNABILITY), Runnability) is not None:
            return
        record = classify_pair(self.layout, self.pair_id)
        write_record(self._file(RUNNABILITY), record)
        self._say(f"runnability: {runnability_summary(record)}")

    def score(self) -> list[RungScore]:
        """Score every rung output of the pair, always afresh."""
        self.step = "score"
        scores = score_pair(self.layout, self.pair_id)
        self._say(score_summary(scores))
        return scores

    def claim_c(self) -> ClaimCRecord:
        """Return the Claim C record, running runnability and Claim C when either is missing."""
        self.step = CLAIM_C
        record = read_optional(self._file(CLAIM_C), ClaimCRecord)
        has_runnability = read_optional(self._file(RUNNABILITY), Runnability) is not None
        if record is not None and has_runnability:
            return record
        self.ensure_workspace()
        self.ensure_runnability()
        if record is not None:
            return record
        self.step = CLAIM_C
        record = run_claim_c(self.layout, self.pair_id)
        write_record(self._file(CLAIM_C), record)
        self._say(f"Claim C: {claim_c_summary(record)}")
        return record

    def _git_in_cache(self, heads: HeadsKind) -> GitRungResult:
        self._ensure_cache()
        self.step = git_record_name(heads)
        result = run_git_rung_in_cache(self.layout, self.pair, heads)
        self._say(f"git rung at {heads} heads: {git_summary(result)}")
        return result

    def _ensure_cache(self) -> None:
        self.step = "cache"
        cache = self.layout.cache_dir(self.pair.repo)
        if cache.is_dir():
            return
        ensure_clone(self.pair.clone_url, cache, refresh=False)
        for pr in (self.pair.a, self.pair.b):
            fetch_pr(cache, pr.number)
        self._say(f"repository cache cloned again at {cache}")

    def _restore(self, name: str, record: Record, copy: Path, problem: str) -> NoReturn:
        """Put back the record a re-run disagreed with, delete the re-run's copy, and raise."""
        write_record(self._file(name), record)
        remove_tree(copy)
        raise StepFailedError(f"{problem}; the record is kept and the new copy deleted")

    def _file(self, name: str) -> Path:
        return self.layout.result_file(self.pair_id, name)

    def _say(self, message: str) -> None:
        self.say(self.pair_id, message)


def _git_key(result: GitRungResult) -> tuple[str, list[str], list[str]]:
    return result.status, result.types, [file.path for file in result.files]


def _structural_key(result: StructuralResult) -> tuple[str, list[str]]:
    return result.status, result.remaining_conflicted
