"""Run installers and test runners under a time cap and a disk floor, logging their output."""

import contextlib
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from ladder.diskfloor import FLOOR_ENV, min_free_gib, stopped_below
from ladder.diskspace import free_gib

KILL_GRACE_S = 10
DISK_POLL_S = 2.0
TAIL_BYTES = 200_000
TIMEOUT_EXIT_CODES = (124, 137)
HARNESS_VARIABLES = ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME", "UV_PROJECT_ENVIRONMENT")
TIMED_OUT = "timed out after"

Process = subprocess.Popen[bytes]


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
    disk_floor: bool
    floor_gib: float

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
            return f"{self.name}: {TIMED_OUT} {self.duration_s:.0f} s"
        if self.disk_floor:
            return f"{self.name}: {stopped_below(self.floor_gib)}"
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
    """Runs commands with explicit arguments, a log per step, under a time cap and a disk floor.

    With a scratch directory, temporary files and the uv and Go module caches of every step
    live under it, so they are deleted with the pair's runtime instead of piling up.
    """

    logs: Path
    scratch: Path | None = None

    def _scratch_env(self) -> dict[str, str]:
        if self.scratch is None:
            return {}
        scratch = self.scratch.resolve()
        tmp = scratch / "tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        return {
            "TMPDIR": str(tmp),
            "TMP": str(tmp),
            "TEMP": str(tmp),
            "UV_CACHE_DIR": str(scratch / "uv-cache"),
            "GOMODCACHE": str(scratch / "go-mod"),
        }

    def run(
        self,
        name: str,
        argv: Sequence[str],
        cwd: Path,
        *,
        cap: int,
        env: Mapping[str, str] | None = None,
    ) -> StepResult:
        """Run one command, killing its process group past cap seconds or below the disk floor."""
        floor = min_free_gib()
        self.logs.mkdir(parents=True, exist_ok=True)
        log = self.logs / f"{name}.log"
        full_env = tool_env({**self._scratch_env(), **(env or {})})
        args = list(argv)
        if shutil.which(args[0], path=full_env["PATH"]) is None:
            log.write_text(f"{args[0]} not found on PATH\n", encoding="utf-8")
            return StepResult(
                name,
                args,
                None,
                0.0,
                timed_out=False,
                missing=True,
                log=log,
                disk_floor=False,
                floor_gib=floor,
            )
        if (free := free_gib(cwd)) < floor:
            log.write_text(_floor_line("not started", free, cwd, floor), encoding="utf-8")
            return StepResult(
                name,
                args,
                None,
                0.0,
                timed_out=False,
                missing=False,
                log=log,
                disk_floor=True,
                floor_gib=floor,
            )
        start = time.monotonic()
        with log.open("wb") as out:
            proc = subprocess.Popen(
                ["timeout", f"--kill-after={KILL_GRACE_S}", str(cap), *args],
                cwd=cwd,
                env=full_env,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                code, starved = _watch(proc, cwd, floor, start + cap + 3 * KILL_GRACE_S)
            except BaseException:
                _kill(proc)
                raise
        duration = time.monotonic() - start
        if starved is not None:
            with log.open("a", encoding="utf-8") as note:
                note.write("\n" + _floor_line("stopped", starved, cwd, floor))
        disk_floor = starved is not None
        timed_out = code is None or (code in TIMEOUT_EXIT_CODES and duration >= cap)
        return StepResult(
            name,
            args,
            None if timed_out or disk_floor else code,
            duration,
            timed_out=timed_out,
            missing=False,
            log=log,
            disk_floor=disk_floor,
            floor_gib=floor,
        )


def _watch(
    proc: Process, cwd: Path, floor: float, backstop: float
) -> tuple[int | None, float | None]:
    while (left := backstop - time.monotonic()) > 0:
        with contextlib.suppress(subprocess.TimeoutExpired):
            return proc.wait(timeout=min(DISK_POLL_S, left)), None
        if (free := free_gib(cwd)) < floor:
            _stop(proc)
            return proc.returncode, free
    _kill(proc)
    return None, None


def _stop(proc: Process) -> None:
    _signal(proc, signal.SIGTERM)
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=KILL_GRACE_S)
    _kill(proc)


def _kill(proc: Process) -> None:
    _signal(proc, signal.SIGKILL)
    proc.wait()


def _signal(proc: Process, signum: signal.Signals) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signum)


def _floor_line(what: str, free: float, cwd: Path, floor: float) -> str:
    return (
        f"{what}: {free:.1f} GiB free under {cwd}, "
        f"below the {floor:g} GiB floor set by {FLOOR_ENV}\n"
    )
