"""Keep one bare blob-less clone per repository and fetch PR heads into it."""

import shutil
import time
from pathlib import Path

from ladder.gitio import GitError, git_text, run_git

ATTEMPTS = 3
BACKOFF_S = 2.0


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


def _network(args: list[str], cwd: Path) -> None:
    for attempt in range(1, ATTEMPTS + 1):
        try:
            run_git(args, cwd, isolated=False)
            return
        except GitError:
            if attempt == ATTEMPTS:
                raise
            time.sleep(BACKOFF_S * attempt)
