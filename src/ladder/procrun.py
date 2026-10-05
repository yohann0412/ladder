"""Run installers and test runners under a time cap, logging their combined output to a file."""

import os
import shutil
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

KILL_GRACE_S = 10
TAIL_BYTES = 200_000
TIMEOUT_EXIT_CODES = (124, 137)
HARNESS_VARIABLES = ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME", "UV_PROJECT_ENVIRONMENT")


@dataclass(frozen=True)
class StepResult:
    """The outcome of one external command."""

    name: str
    argv: list[str]
    exit_code: int | None
    duration_s: float
    timed_out: bool
    missing: bool
    log: Path

    @property
    def ok(self) -> bool:
        """Return True when the command ran and exited 0."""
        return self.exit_code == 0

    def output(self) -> str:
        """Return the end of the command's combined output."""
        if not self.log.exists():
            return ""
        with self.log.open("rb") as handle:
            size = handle.seek(0, os.SEEK_END)
            handle.seek(max(0, size - TAIL_BYTES))
            return handle.read().decode("utf-8", "replace")

    def summary(self) -> str:
        """Return one line naming the step and how it ended."""
        if self.missing:
            return f"{self.name}: {self.argv[0]} not found"
        if self.timed_out:
            return f"{self.name}: timed out after {self.duration_s:.0f} s"
        return f"{self.name}: exit {self.exit_code} in {self.duration_s:.1f} s"


def tool_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return the environment for a project's tools, without the harness's own Python setup."""
    env = {key: value for key, value in os.environ.items() if key not in HARNESS_VARIABLES}
    harness_bins = {str(Path(sys.prefix) / "bin")}
    if "VIRTUAL_ENV" in os.environ:
        harness_bins.add(str(Path(os.environ["VIRTUAL_ENV"]) / "bin"))
    path = [entry for entry in env.get("PATH", "").split(os.pathsep) if entry not in harness_bins]
    env["PATH"] = os.pathsep.join(path)
    if extra:
        env.update(extra)
    return env


@dataclass(frozen=True)
class Runner:
    """Runs commands with explicit arguments, one log file per step, each under a time cap."""

    logs: Path

    def run(
        self,
        name: str,
        argv: Sequence[str],
        cwd: Path,
        *,
        cap: int,
        env: Mapping[str, str] | None = None,
    ) -> StepResult:
        """Run one command; a run longer than cap seconds is killed with its process group."""
        self.logs.mkdir(parents=True, exist_ok=True)
        log = self.logs / f"{name}.log"
        full_env = tool_env(env)
        args = list(argv)
        if shutil.which(args[0], path=full_env["PATH"]) is None:
            log.write_text(f"{args[0]} not found on PATH\n", encoding="utf-8")
            return StepResult(name, args, None, 0.0, timed_out=False, missing=True, log=log)
        start = time.monotonic()
        with log.open("wb") as out:
            try:
                proc = subprocess.run(
                    ["timeout", f"--kill-after={KILL_GRACE_S}", str(cap), *args],
                    cwd=cwd,
                    env=full_env,
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=subprocess.STDOUT,
                    timeout=cap + 3 * KILL_GRACE_S,
                    check=False,
                )
                code: int | None = proc.returncode
            except subprocess.TimeoutExpired:
                code = None
        duration = time.monotonic() - start
        timed_out = code is None or (code in TIMEOUT_EXIT_CODES and duration >= cap)
        return StepResult(
            name,
            args,
            None if timed_out else code,
            duration,
            timed_out=timed_out,
            missing=False,
            log=log,
        )
