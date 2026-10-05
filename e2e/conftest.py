"""Shared helpers for the end-to-end acceptance tests.

Every test runs the real `ladder` executable as a subprocess against real git
repositories on disk and asserts only on exit codes, files, JSON and numbers.
No test imports harness code.
"""

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LADDER = shutil.which("ladder") or str(Path(sys.executable).parent / "ladder")
CLEAN_GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
}


def run(
    argv: list[str], *, cwd: Path = REPO_ROOT, check: bool = True, timeout: float = 900
) -> subprocess.CompletedProcess[str]:
    """Run a command and return its result; fail the test with its output when check fails."""
    env = {**os.environ, **CLEAN_GIT_ENV}
    proc = subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout, check=False
    )
    if check and proc.returncode != 0:
        pytest.fail(
            f"command failed ({proc.returncode}): {' '.join(argv)}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
    return proc


def git(repo: Path, *args: str) -> str:
    """Run git in a repository with no user configuration and return stripped stdout."""
    return run(["git", "-c", "commit.gpgsign=false", *args], cwd=repo).stdout.strip()


def read_json(path: Path) -> Any:
    """Parse a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Experiment:
    """The three locations one experiment uses."""

    pairs: Path
    work: Path
    results: Path

    def ladder(
        self, *args: str, check: bool = True, timeout: float = 900
    ) -> subprocess.CompletedProcess[str]:
        """Run the ladder CLI against this experiment."""
        argv = [
            LADDER,
            "--pairs",
            str(self.pairs),
            "--work",
            str(self.work),
            "--results",
            str(self.results),
            *args,
        ]
        return run(argv, check=check, timeout=timeout)

    def result(self, pair_id: str, name: str) -> Any:
        """Read one result record of a pair."""
        return read_json(self.results / "pairs" / pair_id / f"{name}.json")


def build_fixture(out: Path) -> Path:
    """Build the fixture repository into a directory with the committed script."""
    run([sys.executable, str(REPO_ROOT / "fixtures" / "make-fixture.py"), str(out)])
    return out


@pytest.fixture(scope="session")
def fixture_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the fixture once per test session."""
    return build_fixture(tmp_path_factory.mktemp("fixture") / "fx")


@pytest.fixture
def fx(fixture_dir: Path, tmp_path: Path) -> Experiment:
    """Return a fresh experiment whose pairs.json was loaded from the fixture by the CLI."""
    experiment = Experiment(
        pairs=tmp_path / "pairs.json", work=tmp_path / "work", results=tmp_path / "results"
    )
    experiment.ladder("pairs", "load", "--fixture", str(fixture_dir))
    return experiment


@pytest.fixture
def fx_resolved(fx: Experiment) -> Experiment:
    """Return a fixture experiment whose pairs have had their refs resolved by the CLI."""
    fx.ladder("pairs", "resolve", "--all")
    return fx
