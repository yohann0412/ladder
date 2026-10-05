"""Locate the pinned structural merge drivers and install one as git's merge driver for a repo.

git runs a driver through the shell with %O (base), %A (ours, overwritten with the result),
%B (theirs), %L (marker size) and %P (the path, shell-quoted) substituted. git 2.43 does not
expand %S, %X or %Y, so the drivers' side labels are not passed. git treats every non-zero
driver exit as a conflict; the installed command therefore logs each exit above 1 (the
drivers' own error codes, or 124 and 137 when the time limit stopped the driver with TERM or,
10 s later, KILL) so that a crash or a timeout can be told apart from a conflict.
"""

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ladder.gitio import git_text, run_git
from ladder.mergework import RungError
from ladder.schemas import StructuralTool

DRIVER_TIMEOUT_S = 120
TIMEOUT_EXITS = frozenset({"124", "137"})
FAILURE_LOG = "ladder-driver-failures.log"


@dataclass(frozen=True)
class DriverSpec:
    """Where to find a structural tool and how git invokes it as a merge driver."""

    env_var: str
    local_path: str
    command: str
    name: str
    arguments: str


DRIVERS: dict[StructuralTool, DriverSpec] = {
    "weave": DriverSpec(
        env_var="LADDER_WEAVE_DRIVER",
        local_path=".tools/npm/node_modules/.bin/weave-driver",
        command="weave-driver",
        name="Entity-level semantic merge",
        arguments="%O %A %B %L %P",
    ),
    "mergiraf": DriverSpec(
        env_var="LADDER_MERGIRAF",
        local_path=".tools/cargo/bin/mergiraf",
        command="mergiraf",
        name="mergiraf",
        arguments="merge --git %O %A %B -p %P -l %L",
    ),
}


@dataclass(frozen=True)
class Driver:
    """A located structural merge driver binary and the version it reports."""

    tool: StructuralTool
    binary: Path
    version: str


def locate(tool: StructuralTool) -> Driver:
    """Find a tool from its env var, else .tools/ under the working directory, else PATH."""
    spec = DRIVERS[tool]
    configured = os.environ.get(spec.env_var)
    local = Path.cwd() / spec.local_path
    if configured:
        found = shutil.which(configured)
    elif local.is_file():
        found = str(local)
    else:
        found = shutil.which(spec.command)
    if found is None:
        raise RungError(
            f"{tool}: {configured or spec.command} not found "
            f"(set {spec.env_var} or run `just tools`)"
        )
    binary = Path(found).absolute()
    return Driver(tool=tool, binary=binary, version=_version(tool, binary))


def _version(tool: StructuralTool, binary: Path) -> str:
    try:
        proc = subprocess.run(
            [str(binary), "--version"], capture_output=True, text=True, timeout=60, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RungError(
            f"{tool}: cannot run {binary} --version ({error}); run `just tools`"
        ) from None
    lines = proc.stdout.strip().splitlines()
    if proc.returncode != 0 or not lines:
        raise RungError(f"{tool}: {binary} --version exited {proc.returncode}; run `just tools`")
    return lines[0].split()[-1]


def driver_command(driver: Driver, failure_log: Path) -> str:
    """Return the git driver command: the tool under a time limit, logging exits above 1."""
    spec = DRIVERS[driver.tool]
    tool = f"timeout -k 10 {DRIVER_TIMEOUT_S} {shlex.quote(str(driver.binary))} {spec.arguments}"
    log = shlex.quote(str(failure_log))
    return (
        f'{tool}; status=$?; if [ "$status" -gt 1 ]; then echo "$status" %P >> {log}; fi; '
        'exit "$status"'
    )


def install(repo: Path, driver: Driver) -> Path:
    """Make the driver git's merge driver for every path of the repo; return its failure log."""
    git_dir = Path(git_text(["rev-parse", "--absolute-git-dir"], repo))
    attributes = git_dir / "info" / "attributes"
    attributes.parent.mkdir(parents=True, exist_ok=True)
    attributes.write_text(f"* merge={driver.tool}\n", encoding="utf-8")
    failure_log = git_dir / FAILURE_LOG
    run_git(["config", f"merge.{driver.tool}.name", DRIVERS[driver.tool].name], repo)
    run_git(["config", f"merge.{driver.tool}.driver", driver_command(driver, failure_log)], repo)
    return failure_log


def driver_failures(failure_log: Path) -> list[str]:
    """Return one description per logged driver run that neither merged nor reported conflicts."""
    if not failure_log.exists():
        return []
    failures: list[str] = []
    for line in failure_log.read_text(encoding="utf-8", errors="replace").splitlines():
        code, _, path = line.partition(" ")
        timed_out = f"timed out after {DRIVER_TIMEOUT_S} s, " if code in TIMEOUT_EXITS else ""
        failures.append(f"{path}: driver {timed_out}exit {code}")
    return failures
