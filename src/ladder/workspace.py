"""Build a leak-proof workspace: three new commits made from three source trees, nothing else."""

import shutil
from dataclasses import dataclass
from pathlib import Path

from ladder.completion import mark_complete, unmark
from ladder.gitio import git_text, run_git
from ladder.jsonio import write_record
from ladder.layout import Layout
from ladder.schemas import HeadsKind, Pair, WorkspaceRecord
from ladder.treecopy import copy_trees
from ladder.wsverify import Verification, verify_workspace


class UnusablePairError(RuntimeError):
    """The pair's resolved refs or cache cannot give the commits a workspace needs."""


@dataclass(frozen=True)
class Sources:
    """The original commits a workspace is made from."""

    base: str
    a: str
    b: str
    criss_cross: bool

    def commits(self) -> tuple[str, str, str]:
        """Return the source commits in the order base, a, b."""
        return self.base, self.a, self.b


@dataclass(frozen=True)
class Synthetic:
    """The three commits a workspace holds."""

    base: str
    a: str
    b: str

    def refs(self) -> dict[str, str]:
        """Return the only refs the workspace may have, mapped to the commits they must name."""
        return {"refs/heads/base": self.base, "refs/heads/a": self.a, "refs/heads/b": self.b}


@dataclass(frozen=True)
class BuiltWorkspace:
    """A rebuilt workspace, its leak checks, and its record when every check passed."""

    path: Path
    verification: Verification
    record: WorkspaceRecord | None


def source_commits(pair: Pair, heads: HeadsKind) -> Sources:
    """Return the recorded merge base and heads of a pair; raise UnusablePairError without them."""
    refs = pair.refs
    if refs is None:
        raise UnusablePairError(f"{pair.pair_id} is not resolved; run `ladder pairs resolve`")
    if heads == "replay":
        if refs.status != "ok":
            raise UnusablePairError(
                f"{pair.pair_id} has status {refs.status}, so it has no replay workspace: "
                f"{refs.detail}"
            )
        base, a, b = refs.replay_merge_base, refs.a.replay_head, refs.b.replay_head
        count = refs.replay_merge_base_count
    else:
        base, a, b = refs.final_merge_base, refs.a.final_head, refs.b.final_head
        count = refs.final_merge_base_count
    if base is None or a is None or b is None:
        raise UnusablePairError(
            f"{pair.pair_id} has status {refs.status}, so it has no {heads} heads and merge base"
        )
    return Sources(base=base, a=a, b=b, criss_cross=count > 1)


def build_workspace(cache: Path, path: Path, sources: Sources) -> Synthetic:
    """Recreate a workspace from scratch: the three source trees as commits base, pr-a, pr-b."""
    if not cache.exists():
        raise UnusablePairError(f"no repository cache at {cache}; run `ladder pairs resolve`")
    trees = [git_text(["rev-parse", f"{commit}^{{tree}}"], cache) for commit in sources.commits()]
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    run_git(["init", "--quiet"], path)
    run_git(["config", "core.logAllRefUpdates", "false"], path)
    copy_trees(cache, path, trees)
    base = _commit(path, trees[0], [], "base")
    synthetic = Synthetic(
        base=base,
        a=_commit(path, trees[1], [base], "pr-a"),
        b=_commit(path, trees[2], [base], "pr-b"),
    )
    for ref, commit in synthetic.refs().items():
        run_git(["update-ref", ref, commit], path)
    run_git(["symbolic-ref", "HEAD", "refs/heads/a"], path)
    run_git(["read-tree", "--reset", "-u", "HEAD"], path)
    return synthetic


def build_recorded(layout: Layout, pair: Pair, heads: HeadsKind) -> BuiltWorkspace:
    """Rebuild and verify a pair's workspace; mark and record it only when every check passed.

    The previous record and completion mark are deleted first. Raise UnusablePairError when the
    pair has no such heads or no repository cache.
    """
    record_file = layout.result_file(pair.pair_id, f"workspace-{heads}")
    record_file.unlink(missing_ok=True)
    path = layout.workspace_dir(pair.pair_id, heads).resolve()
    unmark(path)
    sources = source_commits(pair, heads)
    synthetic = build_workspace(layout.cache_dir(pair.repo), path, sources)
    verification = verify_workspace(path, synthetic.refs())
    if not verification.passed:
        return BuiltWorkspace(path, verification, None)
    mark_complete(path)
    record = workspace_record(
        pair.pair_id,
        heads,
        path=path,
        sources=sources,
        synthetic=synthetic,
        verification=verification,
    )
    write_record(record_file, record)
    return BuiltWorkspace(path, verification, record)


def workspace_record(
    pair_id: str,
    heads: HeadsKind,
    *,
    path: Path,
    sources: Sources,
    synthetic: Synthetic,
    verification: Verification,
) -> WorkspaceRecord:
    """Return the record of a built workspace that passed verification."""
    return WorkspaceRecord(
        pair_id=pair_id,
        heads=heads,
        path=str(path),
        source_base=sources.base,
        source_a=sources.a,
        source_b=sources.b,
        base_commit=synthetic.base,
        a_commit=synthetic.a,
        b_commit=synthetic.b,
        object_count=verification.object_count,
        criss_cross=sources.criss_cross,
        checks=[check.name for check in verification.checks if check.passed],
    )


def _commit(path: Path, tree: str, parents: list[str], message: str) -> str:
    flags = [flag for parent in parents for flag in ("-p", parent)]
    return git_text(["commit-tree", tree, *flags, "-m", message], path)
