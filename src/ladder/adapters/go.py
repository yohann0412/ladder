"""Go modules tested with go test."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ladder.adapters.base import Site, Step, Strategy, SuiteCommand, find_file, run_steps
from ladder.procrun import Runner, StepResult
from ladder.testreports import Counts, parse_go_json

STANDARD = Strategy("standard", None)
MOD_MOD = Strategy("mod-mod", "GOFLAGS=-mod=mod, so go.mod and go.sum drift is resolved")


@dataclass(frozen=True)
class GoAdapter:
    """A Go module at the root of the tree."""

    has_tests: bool
    language = "go"
    package_manager = "go modules"
    test_runner = "go test"
    toolchain = "go"

    def strategies(self) -> tuple[Strategy, Strategy]:
        """Return the standard install and the -mod=mod fallback."""
        return STANDARD, MOD_MOD

    def env_present(self, site: Site) -> bool:
        """Return True: modules live in the shared Go module cache."""
        return True

    def install(self, runner: Runner, site: Site, strategy: Strategy) -> list[StepResult]:
        """Download the modules and compile every package's tests without running them."""
        env = _env(strategy, site)
        steps = [
            Step("install", ["go", "mod", "download"], site.tree, env),
            Step("build", ["go", "test", "-count=1", "-run", "^$", "./..."], site.tree, env),
        ]
        return run_steps(runner, steps)

    def attach(
        self, runner: Runner, base: Site, tree: Path, strategy: Strategy
    ) -> tuple[Site, list[StepResult]]:
        """Reuse the shared module cache; nothing to link."""
        return Site(tree, base.env), []

    def suite(
        self, site: Site, strategy: Strategy, report: Path, only: list[str] | None
    ) -> SuiteCommand:
        """Return go test -json over every package, or the packages of the given files."""
        if not only:
            return SuiteCommand(["go", "test", "-count=1", "-json", "./..."], _env(strategy, site))
        packages = sorted({"./" + str(PurePosixPath(path).parent) for path in only})
        note = "go test runs the whole packages of the selected files"
        env = _env(strategy, site)
        return SuiteCommand(["go", "test", "-count=1", "-json", *packages], env, note)

    def parse(self, site: Site, report: Path, log_text: str) -> Counts | None:
        """Read the go test -json event stream from the log."""
        return parse_go_json(log_text)


def detect(tree: Path) -> GoAdapter | None:
    """Recognise a Go module by its go.mod."""
    if not (tree / "go.mod").exists():
        return None
    return GoAdapter(has_tests=find_file(tree, lambda name: name.endswith("_test.go")))


def _env(strategy: Strategy, site: Site) -> dict[str, str]:
    """Return the Go variables of a run: a build cache inside the pair's runtime, pruned with it."""
    env = {"GOCACHE": str(site.env.resolve() / "gocache")}
    if strategy == MOD_MOD:
        env["GOFLAGS"] = "-mod=mod"
    return env
