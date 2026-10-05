"""Keep one bare blob-less clone per repository and fetch PR heads and objects into it."""

import shutil
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path

from ladder.gitio import GitError, git_text, run_git

ATTEMPTS = 3
BACKOFF_S = 2.0
CLONE_TIMEOUT_S = 1800.0
FETCH_TIMEOUT_S = 600.0
OBJECT_BATCH = 1000


def pr_ref(number: int) -> str:
    """Return the cache ref a PR's fetched head is stored under."""
    return f"refs/ladder/pr/{number}"


def ensure_clone(clone_url: str, cache: Path, *, refresh: bool) -> None:
    """Clone a repository bare and blob-less unless cached; with refresh, re-fetch its branches."""
    if not cache.exists():
        partial = cache.with_name(cache.name + ".partial")
        shutil.rmtree(partial, ignore_errors=True)
        partial.parent.mkdir(parents=True, exist_ok=True)
        clone = ["clone", "--quiet", "--bare", "--filter=blob:none", clone_url, partial.name]
        _network(clone, partial.parent, timeout=CLONE_TIMEOUT_S, scratch=partial)
        partial.replace(cache)
    elif refresh:
        branches = ["fetch", "--quiet", "--prune", "origin", "+refs/heads/*:refs/heads/*"]
        _network(branches, cache, timeout=FETCH_TIMEOUT_S)


def fetch_pr(cache: Path, number: int) -> str:
    """Fetch a PR's head into its cache ref, force-updating it, and return the commit."""
    ref = pr_ref(number)
    fetch = ["fetch", "--quiet", "--no-tags", "origin", f"+refs/pull/{number}/head:{ref}"]
    _network(fetch, cache, timeout=FETCH_TIMEOUT_S)
    return git_text(["rev-parse", "--verify", f"{ref}^{{commit}}"], cache)


def fetch_objects(cache: Path, shas: Sequence[str]) -> None:
    """Fetch objects the blob-less clone lacks from origin by id, in batches."""
    fetch = ["-c", "fetch.negotiationAlgorithm=noop", "fetch", "--quiet", "--no-tags"]
    fetch += ["--no-write-fetch-head", "--stdin", "origin"]
    for start in range(0, len(shas), OBJECT_BATCH):
        wanted = "".join(f"{sha}\n" for sha in shas[start : start + OBJECT_BATCH])
        _network(fetch, cache, timeout=FETCH_TIMEOUT_S, stdin=wanted.encode())


def _network(
    args: list[str],
    cwd: Path,
    *,
    timeout: float,
    stdin: bytes | None = None,
    scratch: Path | None = None,
) -> None:
    for attempt in range(1, ATTEMPTS + 1):
        try:
            _attempt(args, cwd, timeout=timeout, stdin=stdin)
            return
        except GitError:
            if scratch is not None:
                shutil.rmtree(scratch, ignore_errors=True)
            if attempt == ATTEMPTS:
                raise
            time.sleep(BACKOFF_S * attempt)


def _attempt(args: list[str], cwd: Path, *, timeout: float, stdin: bytes | None) -> None:
    try:
        run_git(args, cwd, isolated=False, stdin=stdin, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise GitError(f"git {' '.join(args)} timed out after {timeout:g} s") from error
