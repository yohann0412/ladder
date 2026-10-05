"""Keep one bare blob-less clone per repository and fetch PR heads and objects into it."""

import shutil
import time
from collections.abc import Sequence
from pathlib import Path

from ladder.gitio import GitError, git_text, run_git

ATTEMPTS = 3
BACKOFF_S = 2.0
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
        _network(clone, partial.parent)
        partial.replace(cache)
    elif refresh:
        _network(["fetch", "--quiet", "--prune", "origin", "+refs/heads/*:refs/heads/*"], cache)


def fetch_pr(cache: Path, number: int) -> str:
    """Fetch a PR's head into its cache ref, force-updating it, and return the commit."""
    ref = pr_ref(number)
    _network(["fetch", "--quiet", "--no-tags", "origin", f"+refs/pull/{number}/head:{ref}"], cache)
    return git_text(["rev-parse", "--verify", f"{ref}^{{commit}}"], cache)


def fetch_objects(cache: Path, shas: Sequence[str]) -> None:
    """Fetch objects the blob-less clone lacks from origin by id, in batches."""
    fetch = ["-c", "fetch.negotiationAlgorithm=noop", "fetch", "--quiet", "--no-tags"]
    fetch += ["--no-write-fetch-head", "--stdin", "origin"]
    for start in range(0, len(shas), OBJECT_BATCH):
        wanted = "".join(f"{sha}\n" for sha in shas[start : start + OBJECT_BATCH])
        _network(fetch, cache, stdin=wanted.encode())


def _network(args: list[str], cwd: Path, *, stdin: bytes | None = None) -> None:
    for attempt in range(1, ATTEMPTS + 1):
        try:
            run_git(args, cwd, isolated=False, stdin=stdin)
            return
        except GitError:
            if attempt == ATTEMPTS:
                raise
            time.sleep(BACKOFF_S * attempt)
