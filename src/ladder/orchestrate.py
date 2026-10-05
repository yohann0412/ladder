"""Drive every step of the ladder for selected pairs, in-process, skipping what is recorded.

Pairs are taken one repository at a time. Within a repository every pair first goes as far as
its resolver runs (git rungs, structural rungs, plan, prepare); only then do the pairs whose
runs are settled extract truth and score, unless the run stops before truth. Truth also waits
while another pair of the same repository has resolver runs pending, because no resolver may
start once a same-repository truth exists. A pair with a pending resolver run is never pruned.
"""

import threading
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from rich.console import Console

from ladder.diskspace import wait_for_disk
from ladder.gitrung import git_record_name
from ladder.jsonio import read_optional, write_record
from ladder.layout import Layout
from ladder.pairsteps import PairSteps, Say
from ladder.prune import prune_cache, prune_pair
from ladder.resolve import resolve_pairs, with_refs
from ladder.resolver_records import pending_tasks
from ladder.run_view import PairOutcome, claim_c_summary
from ladder.runlog import append_failure
from ladder.schemas import GitRungResult, Pair, PairRefs, PairSet, ResolverTask

STOPPED = (
    "resolver runs settled; truth, runnability and scores are left for a run without "
    "--stop-before-truth"
)


@dataclass(frozen=True)
class RunOptions:
    """The flags of one `ladder run`."""

    no_llm: bool
    skip_claim_c: bool
    prune: bool
    min_free_gib: float
    jobs: int
    stop_before_truth: bool


@dataclass(frozen=True)
class RunResult:
    """Every selected pair's outcome and the resolver tasks still waiting for a subagent."""

    outcomes: list[PairOutcome]
    pending: list[ResolverTask]

    @property
    def failed(self) -> bool:
        """Return whether any pair failed."""
        return any(outcome.state == "failed" for outcome in self.outcomes)


def run_pairs(
    layout: Layout,
    pair_set: PairSet,
    selected: Sequence[Pair],
    options: RunOptions,
    console: Console,
) -> RunResult:
    """Take every selected pair as far as it can go; a failing pair is logged and skipped."""
    say = _sayer(console)
    wait_for_disk(layout.work, options.min_free_gib, lambda text: say("run", text))
    pair_set, errors = resolve_missing(layout, pair_set, selected, options.jobs, say)
    by_id = {pair.pair_id: pair for pair in pair_set.pairs}
    runner = _Runner(layout, pair_set, options, say)
    outcomes: list[PairOutcome] = []
    for group in _by_repository([by_id[pair.pair_id] for pair in selected]):
        outcomes += runner.group(group, errors)
    repos = {pair.repo for pair in selected}
    pending = [
        task
        for task in pending_tasks(layout)
        if task.pair_id in by_id and by_id[task.pair_id].repo in repos
    ]
    return RunResult(outcomes, pending)


def resolve_missing(
    layout: Layout, pair_set: PairSet, selected: Sequence[Pair], jobs: int, say: Say
) -> tuple[PairSet, dict[str, str]]:
    """Resolve every selected pair without refs, one worker per repository; write pairs.json once.

    Return the updated pair set and, by pair id, the error of every pair whose repository raised.
    """
    groups: dict[str, list[Pair]] = {}
    for pair in selected:
        if pair.refs is None:
            groups.setdefault(pair.repo, []).append(pair)
    if not groups:
        return pair_set, {}
    results: dict[str, PairRefs] = {}
    errors: dict[str, str] = {}
    lock = threading.Lock()

    def done(pair_id: str, refs: PairRefs) -> None:
        with lock:
            results[pair_id] = refs
        say(pair_id, f"refs {refs.status}" + (f": {refs.detail}" if refs.detail else ""))

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = [
            (pool.submit(resolve_pairs, layout, group, jobs=1, refresh=False, done=done), group)
            for group in groups.values()
        ]
        for future, group in futures:
            try:
                future.result()
            except Exception as error:
                for pair in group:
                    if pair.pair_id not in results:
                        errors[pair.pair_id] = _describe(error)
    updated = with_refs(pair_set, results)
    write_record(layout.pairs_file, updated)
    return updated, errors


@dataclass(frozen=True)
class _Runner:
    layout: Layout
    pair_set: PairSet
    options: RunOptions
    say: Say

    def group(self, pairs: list[Pair], errors: dict[str, str]) -> list[PairOutcome]:
        """Run every pair of one repository: up to the resolver runs, then truth and scores."""
        outcomes: dict[str, PairOutcome] = {}
        ready: list[PairSteps] = []
        for pair in pairs:
            self._wait(pair.pair_id)
            if (error := errors.get(pair.pair_id)) is not None:
                outcomes[pair.pair_id] = self._failure(pair.pair_id, "resolve", error)
                continue
            steps = PairSteps(self.layout, self.pair_set, pair, self.say)
            outcome = self._guarded(steps, self._advance)
            if outcome is None:
                ready.append(steps)
            else:
                outcomes[pair.pair_id] = outcome
        for steps in ready:
            if self.options.stop_before_truth:
                outcomes[steps.pair_id] = PairOutcome(steps.pair_id, "stopped", STOPPED)
                continue
            outcomes[steps.pair_id] = self._guarded(steps, self._finish)
        if self.options.prune:
            settled = [pair for pair in pairs if outcomes[pair.pair_id].state != "pending"]
            self._prune(pairs[0].repo, settled)
        return [outcomes[pair.pair_id] for pair in pairs]

    def _advance(self, steps: PairSteps) -> PairOutcome | None:
        """Run the steps up to the resolver runs; None when the pair is ready for truth."""
        refs = steps.refs()
        steps.git_final()
        if refs.status != "ok":
            return PairOutcome(steps.pair_id, "done", f"{refs.status}: {refs.detail}")
        git = steps.git_replay()
        if git.status == "clean":
            return self._claim_c(steps)
        if git.status != "conflicted":
            return PairOutcome(steps.pair_id, "done", f"git rung {git.status}: {git.detail}")
        steps.ensure_workspace()
        steps.ensure_git_copy(git)
        steps.ensure_structural()
        steps.ensure_trap()
        plan = steps.ensure_plan(self.options.no_llm)
        steps.prepare_runs(plan)
        pending = steps.pending_tasks(plan)
        if pending:
            return PairOutcome(steps.pair_id, "pending", f"{len(pending)} resolver runs pending")
        return None

    def _finish(self, steps: PairSteps) -> PairOutcome:
        blocking = steps.blocking_siblings()
        if blocking:
            detail = "truth waits for " + ", ".join(blocking)
            steps.say(steps.pair_id, detail)
            return PairOutcome(steps.pair_id, "waiting", detail)
        steps.ensure_truth()
        steps.ensure_runnability()
        scores = steps.score()
        return PairOutcome(steps.pair_id, "done", f"ladder pair, {len(scores)} outputs scored")

    def _claim_c(self, steps: PairSteps) -> PairOutcome:
        if self.options.skip_claim_c:
            return PairOutcome(steps.pair_id, "done", "clean; Claim C skipped")
        record = steps.claim_c()
        return PairOutcome(steps.pair_id, "done", f"clean; Claim C {claim_c_summary(record)}")

    def _guarded[T: PairOutcome | None](
        self, steps: PairSteps, action: Callable[[PairSteps], T]
    ) -> T | PairOutcome:
        try:
            return action(steps)
        except Exception as error:
            return self._failure(steps.pair_id, steps.step, _describe(error))

    def _failure(self, pair_id: str, step: str, error: str) -> PairOutcome:
        self.say(pair_id, f"FAILED at {step}: {error}")
        append_failure(self.layout, pair_id, step, error)
        return PairOutcome(pair_id, "failed", f"{step}: {error}")

    def _prune(self, repo: str, pairs: list[Pair]) -> None:
        for pair in pairs:
            deleted = prune_pair(self.layout, pair.pair_id)
            if deleted:
                self.say(pair.pair_id, f"pruned {len(deleted)} working directories")
        siblings = [pair for pair in self.pair_set.pairs if pair.repo == repo]
        if not any(self._in_ladder(pair.pair_id) for pair in siblings):
            cache = prune_cache(self.layout, repo)
            if cache is not None:
                self.say(repo, f"pruned the repository cache {cache}")

    def _in_ladder(self, pair_id: str) -> bool:
        record = self.layout.result_file(pair_id, git_record_name("replay"))
        git = read_optional(record, GitRungResult)
        return git is not None and git.status == "conflicted"

    def _wait(self, pair_id: str) -> None:
        wait_for_disk(
            self.layout.work, self.options.min_free_gib, lambda text: self.say(pair_id, text)
        )


def _by_repository(pairs: list[Pair]) -> list[list[Pair]]:
    groups: dict[str, list[Pair]] = {}
    for pair in pairs:
        groups.setdefault(pair.repo, []).append(pair)
    return list(groups.values())


def _describe(error: BaseException) -> str:
    return f"{type(error).__name__}: {error}"


def _sayer(console: Console) -> Say:
    def say(pair_id: str, message: str) -> None:
        console.print(f"{pair_id}: {message}", markup=False, highlight=False, soft_wrap=True)

    return say
