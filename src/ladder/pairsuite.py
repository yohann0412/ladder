"""Run a runnable pair's suite on other trees, reusing the base environment when manifests match."""

from dataclasses import dataclass
from pathlib import Path

from ladder.adapters.base import Adapter, Site, Strategy, Unsupported
from ladder.completion import is_complete, mark_complete, unmark
from ladder.detect import detect
from ladder.layout import Layout
from ladder.manifests import differing, rev_manifests, tree_manifests
from ladder.procrun import Runner
from ladder.runtime import BASE_LABEL, RuntimeDir, remove_tree, runtime_for
from ladder.schemas import Runnability, TestOutcome, WorkspaceRecord
from ladder.testrun import outcome, run_suite
from ladder.trees import export_rev, workspace_repo

MAX_LISTED = 5
INSTALL_FAILED = "install failed"


class SuiteUnavailable(RuntimeError):
    """The base environment of a runnable pair cannot be rebuilt."""


@dataclass(frozen=True)
class PairSuite:
    """A runnable pair's installed base environment and the strategy that installed it."""

    runtime: RuntimeDir
    adapter: Adapter
    strategy: Strategy
    base_manifests: dict[str, str]

    def run(self, label: str, tree: Path, only: list[str] | None = None) -> TestOutcome:
        """Run the suite on an exported tree, installing again only if its manifests differ."""
        runner = Runner(self.runtime.logs(label), self.runtime.scratch())
        changed = differing(self.base_manifests, tree_manifests(tree))
        if changed:
            site = Site(tree, self.runtime.env(label))
            remove_tree(site.env)
            steps = self.adapter.install(runner, site, self.strategy)
            listed = ", ".join(changed[:MAX_LISTED]) + (
                ", ..." if len(changed) > MAX_LISTED else ""
            )
            note = f"dependency manifests differ from base ({listed}); installed again"
        else:
            base = Site(self.runtime.tree(BASE_LABEL), self.runtime.env(BASE_LABEL))
            site, steps = self.adapter.attach(runner, base, tree, self.strategy)
            note = "environment reused from base"
        failing = next((step for step in steps if not step.ok), None)
        if failing is not None:
            detail = f"{note}; {INSTALL_FAILED}: {failing.summary()}"
            return outcome("error", failing.argv, detail)
        reports = self.runtime.reports(label)
        result = run_suite(runner, self.adapter, site, self.strategy, reports=reports, only=only)
        return result.model_copy(update={"detail": f"{note}; {result.detail}"})


def open_pair_suite(
    layout: Layout, runnability: Runnability, workspace: WorkspaceRecord
) -> PairSuite:
    """Return a runnable pair's suite, rebuilding the base tree and environment unless complete.

    The base tree's completion mark covers its environment too: without the mark the tree is
    exported again and the environment deleted, and the mark is written once an install succeeds.
    """
    runtime = runtime_for(layout, runnability.pair_id)
    repo = workspace_repo(workspace)
    site = Site(runtime.tree(BASE_LABEL), runtime.env(BASE_LABEL))
    complete = is_complete(site.tree)
    if not complete:
        unmark(site.tree)
        remove_tree(site.env)
        export_rev(repo, "base", site.tree)
    found = detect(site.tree)
    if isinstance(found, Unsupported):
        raise SuiteUnavailable(f"base tree is no longer recognised: {found.detail}")
    standard, fallback = found.strategies()
    strategy = fallback if runnability.modifications else standard
    if not (complete and found.env_present(site)):
        unmark(site.tree)
        steps = found.install(
            Runner(runtime.logs(f"{BASE_LABEL}-reinstall"), runtime.scratch()), site, strategy
        )
        failing = next((step for step in steps if not step.ok), None)
        if failing is not None:
            raise SuiteUnavailable(f"base environment reinstall failed: {failing.summary()}")
        mark_complete(site.tree)
    return PairSuite(runtime, found, strategy, rev_manifests(repo, "base"))
