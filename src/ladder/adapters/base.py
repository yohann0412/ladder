"""The contract every language adapter fulfils, and the pieces adapters share."""

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ladder.procrun import Runner, StepResult
from ladder.schemas import UnrunnableReason
from ladder.testreports import Counts

INSTALL_CAP_S = 900
TEST_CAP_S = 600
SKIP_DIRS = frozenset(
    {".git", "node_modules", ".venv", "venv", ".tox", ".nox", "site-packages", "target", "vendor"}
)


@dataclass(frozen=True)
class Strategy:
    """One way to install a project; the fallback names the modification it makes."""

    name: str
    modification: str | None


@dataclass(frozen=True)
class Site:
    """Where a suite runs: a source tree and the environment directory it uses."""

    tree: Path
    env: Path


@dataclass(frozen=True)
class Step:
    """One install command of an adapter."""

    name: str
    argv: list[str]
    cwd: Path
    env: dict[str, str] = field(default_factory=dict[str, str])


@dataclass(frozen=True)
class SuiteCommand:
    """The command that runs a suite, its extra environment, and a note on how it was narrowed."""

    argv: list[str]
    env: dict[str, str] = field(default_factory=dict[str, str])
    note: str = ""


@dataclass(frozen=True)
class Unsupported:
    """A project the harness recognises but cannot run, and why."""

    language: str | None
    package_manager: str | None
    test_runner: str | None
    reason: UnrunnableReason
    detail: str


class Adapter(Protocol):
    """Install a project's dependencies, and run and read its test suite."""

    @property
    def language(self) -> str:
        """Return the language name recorded in the runnability record."""
        ...

    @property
    def package_manager(self) -> str | None:
        """Return the package manager that installs the dependencies."""
        ...

    @property
    def test_runner(self) -> str:
        """Return the test runner's name."""
        ...

    @property
    def toolchain(self) -> str:
        """Return the executable whose absence makes the project unrunnable."""
        ...

    @property
    def has_tests(self) -> bool:
        """Return True when the tree shows evidence of a suite for this runner."""
        ...

    def strategies(self) -> tuple[Strategy, Strategy]:
        """Return the standard install and the one fallback tried when it fails."""
        ...

    def env_present(self, site: Site) -> bool:
        """Return True when a site's environment has been installed."""
        ...

    def install(self, runner: Runner, site: Site, strategy: Strategy) -> list[StepResult]:
        """Install the dependencies of a site's tree, stopping at the first failing step."""
        ...

    def attach(
        self, runner: Runner, base: Site, tree: Path, strategy: Strategy
    ) -> tuple[Site, list[StepResult]]:
        """Reuse the base environment for another tree with identical dependency manifests."""
        ...

    def suite(
        self, site: Site, strategy: Strategy, report: Path, only: list[str] | None
    ) -> SuiteCommand:
        """Return the command that runs the suite, or only the given test files."""
        ...

    def parse(self, site: Site, report: Path, log_text: str) -> Counts | None:
        """Read the counts of a finished run, or None when the runner left no readable report."""
        ...


def run_steps(runner: Runner, steps: list[Step]) -> list[StepResult]:
    """Run install steps in order under the install cap, stopping at the first failure."""
    results: list[StepResult] = []
    for step in steps:
        result = runner.run(step.name, step.argv, step.cwd, cap=INSTALL_CAP_S, env=step.env)
        results.append(result)
        if not result.ok:
            break
    return results


def find_file(tree: Path, matches: Callable[[str], bool]) -> bool:
    """Return True when some file below the tree, outside dependency directories, matches."""
    for _root, dirnames, filenames in os.walk(tree):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        if any(matches(name) for name in filenames):
            return True
    return False
