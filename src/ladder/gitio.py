"""Run git as a subprocess with explicit arguments and a reproducible environment."""

import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

FIXED_IDENTITY = {
    "GIT_AUTHOR_NAME": "ladder",
    "GIT_AUTHOR_EMAIL": "ladder@localhost",
    "GIT_COMMITTER_NAME": "ladder",
    "GIT_COMMITTER_EMAIL": "ladder@localhost",
    "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
    "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
}

ISOLATED_OPTIONS = (
    "-c",
    "commit.gpgsign=false",
    "-c",
    "tag.gpgsign=false",
    "-c",
    "core.autocrlf=false",
    "-c",
    "init.defaultBranch=main",
    "-c",
    "advice.detachedHead=false",
)


class GitError(RuntimeError):
    """A git command exited with an unexpected status."""


def git_env(*, isolated: bool, extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return the environment for a git call; isolated calls ignore user and system config."""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["LC_ALL"] = "C"
    if isolated:
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env.update(FIXED_IDENTITY)
    if extra:
        env.update(extra)
    return env


def run_git(
    args: Sequence[str],
    cwd: Path,
    *,
    isolated: bool = True,
    ok_codes: Sequence[int] = (0,),
    stdin: bytes | None = None,
    env: Mapping[str, str] | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run git and return the completed process; raise GitError on an unexpected exit code."""
    argv = ["git", *(ISOLATED_OPTIONS if isolated else ()), *args]
    proc = subprocess.run(
        argv,
        cwd=cwd,
        input=stdin,
        capture_output=True,
        env=git_env(isolated=isolated, extra=env),
        timeout=timeout,
        check=False,
    )
    if proc.returncode not in ok_codes:
        message = proc.stderr.decode("utf-8", "replace").strip()
        raise GitError(f"git {' '.join(args)} exited {proc.returncode}: {message}")
    return proc


def git_text(args: Sequence[str], cwd: Path, *, isolated: bool = True) -> str:
    """Run git and return its stripped standard output as text."""
    return run_git(args, cwd, isolated=isolated).stdout.decode("utf-8", "replace").strip()
