"""Read-only commit-graph queries on a local repository."""

from dataclasses import dataclass
from pathlib import Path

from ladder.gitio import GitError, git_text, run_git

FIELD = "\0"
HEADS = "refs/heads/"


@dataclass(frozen=True)
class ChainCommit:
    """One commit of a first-parent chain, with what merge-commit location needs."""

    sha: str
    parents: tuple[str, ...]
    time: int
    subject: str


def default_branch(repo: Path) -> str:
    """Return the branch a bare clone's HEAD names, such as main."""
    ref = git_text(["symbolic-ref", "HEAD"], repo)
    if not ref.startswith(HEADS):
        raise GitError(f"HEAD names {ref}, not a branch under {HEADS}")
    return ref.removeprefix(HEADS)


def chain_log(repo: Path, ref: str) -> list[ChainCommit]:
    """Return a ref's first-parent chain, newest first, with parents, committer time, subject."""
    fields = "%x00".join(("%H", "%P", "%ct", "%s"))
    args = ["rev-list", "--first-parent", "--no-commit-header", f"--format={fields}", ref]
    out = run_git(args, repo).stdout.decode("utf-8", "replace")
    commits: list[ChainCommit] = []
    for line in filter(None, out.split("\n")):
        sha, parents, stamp, subject = line.split(FIELD, 3)
        commits.append(ChainCommit(sha, tuple(parents.split()), int(stamp), subject))
    return commits


def first_parents(repo: Path, head: str) -> list[str]:
    """Return the first-parent chain from a commit, newest first."""
    return git_text(["rev-list", "--first-parent", head], repo).split()


def merge_bases(repo: Path, left: str, right: str) -> list[str]:
    """Return every merge base of two commits; empty when they share no history."""
    proc = run_git(["merge-base", "--all", left, right], repo, ok_codes=(0, 1))
    return proc.stdout.decode("ascii").split()


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    """Return whether a commit is reachable from another; every commit reaches itself."""
    proc = run_git(["merge-base", "--is-ancestor", ancestor, descendant], repo, ok_codes=(0, 1))
    return proc.returncode == 0
