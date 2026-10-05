"""Rust crates tested with cargo test."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ladder.adapters.base import Site, Step, Strategy, SuiteCommand, run_steps
from ladder.procrun import Runner, StepResult
from ladder.testreports import Counts, parse_cargo_text

STANDARD = Strategy("standard", None)
UPDATED = Strategy("cargo-update", "updated Cargo.lock to the newest compatible versions")


@dataclass(frozen=True)
class RustAdapter:
    """A Cargo package or workspace at the root of the tree."""

    has_lockfile: bool
    language = "rust"
    package_manager = "cargo"
    test_runner = "cargo test"
    toolchain = "cargo"
    has_tests = True

    def strategies(self) -> tuple[Strategy, Strategy]:
        """Return the locked install and the cargo update fallback."""
        return STANDARD, UPDATED

    def env_present(self, site: Site) -> bool:
        """Return True: crates live in the shared Cargo registry cache."""
        return True

    def install(self, runner: Runner, site: Site, strategy: Strategy) -> list[StepResult]:
        """Fetch the crates and compile the tests without running them."""
        locked = ["--locked"] if self.has_lockfile and strategy == STANDARD else []
        fetch = ["cargo", "fetch", *locked] if strategy == STANDARD else ["cargo", "update"]
        steps = [
            Step("install", fetch, site.tree, _env(site)),
            Step("build", ["cargo", "test", "--no-run", *locked], site.tree, _env(site)),
        ]
        return run_steps(runner, steps)

    def attach(
        self, runner: Runner, base: Site, tree: Path, strategy: Strategy
    ) -> tuple[Site, list[StepResult]]:
        """Share the base target directory, so unchanged crates are not rebuilt."""
        return Site(tree, base.env), []

    def suite(
        self, site: Site, strategy: Strategy, report: Path, only: list[str] | None
    ) -> SuiteCommand:
        """Return cargo test over every target, or the integration tests among the files."""
        argv = ["cargo", "test", "--no-fail-fast"]
        if not only:
            return SuiteCommand(argv, _env(site))
        targets = sorted(
            PurePosixPath(path).stem
            for path in only
            if PurePosixPath(path).parent == PurePosixPath("tests") and path.endswith(".rs")
        )
        if not targets:
            note = "no integration-test target among the selected files; ran every target"
            return SuiteCommand(argv, _env(site), note)
        return SuiteCommand([*argv, *(f"--test={name}" for name in targets)], _env(site))

    def parse(self, site: Site, report: Path, log_text: str) -> Counts | None:
        """Read the per-test lines cargo test printed."""
        return parse_cargo_text(log_text)


def detect(tree: Path) -> RustAdapter | None:
    """Recognise a Cargo project by its Cargo.toml."""
    if not (tree / "Cargo.toml").exists():
        return None
    return RustAdapter(has_lockfile=(tree / "Cargo.lock").exists())


def _env(site: Site) -> dict[str, str]:
    return {"CARGO_TARGET_DIR": str(site.env), "CARGO_TERM_COLOR": "never"}
