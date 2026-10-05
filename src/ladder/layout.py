"""Filesystem locations of every artifact of one experiment."""

from dataclasses import dataclass
from pathlib import Path

from ladder.schemas import HeadsKind


@dataclass(frozen=True)
class Layout:
    """Where an experiment keeps its pairs, its git work and its result records."""

    pairs_file: Path
    work: Path
    results: Path

    def cache_dir(self, repo: str) -> Path:
        """Return the bare partial clone directory for an owner/name repository."""
        return self.work / "cache" / (repo.replace("/", "__") + ".git")

    def workspace_dir(self, pair_id: str, heads: HeadsKind) -> Path:
        """Return the canonical leak-proof workspace of a pair."""
        return self.work / "workspaces" / heads / pair_id

    def rung_dir(self, pair_id: str, rung: str) -> Path:
        """Return the scratch copy of the workspace in which a rung merges."""
        return self.work / "rungs" / pair_id / rung

    def resolver_task_dir(self, pair_id: str, rung: str, run: int) -> Path:
        """Return the directory a resolver subagent may read for one run."""
        return self.work / "resolver" / pair_id / rung / f"run-{run}"

    def resolution_dir(self, pair_id: str, rung: str, run: int) -> Path:
        """Return the directory a resolver subagent writes its output into."""
        return self.work / "resolutions" / pair_id / rung / f"run-{run}"

    def truth_dir(self, pair_id: str) -> Path:
        """Return the directory holding the human resolution of a pair."""
        return self.work / "truth" / pair_id

    def runtime_dir(self, pair_id: str) -> Path:
        """Return the scratch directory for dependency installs and test runs."""
        return self.work / "runtime" / pair_id

    def result_dir(self, pair_id: str) -> Path:
        """Return the directory of a pair's committed result records."""
        return self.results / "pairs" / pair_id

    def result_file(self, pair_id: str, name: str) -> Path:
        """Return the path of one named result record of a pair."""
        return self.result_dir(pair_id) / f"{name}.json"
