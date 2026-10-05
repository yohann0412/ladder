"""Plant marker strings into a repository cache's future history and look for them in outputs."""

import tempfile
from dataclasses import dataclass
from pathlib import Path

from ladder.blobs import ensure_files, read_blob, tree_entries
from ladder.gitgraph import default_branch
from ladder.gitio import git_text, run_git
from ladder.jsonio import read_optional, write_record
from ladder.layout import Layout
from ladder.refusal import RefusedError
from ladder.schemas import GitRungResult, Pair, Record

CANARY_FILE = "LADDER_CANARY.txt"
CANARY_REF = "refs/ladder/canary"
LOG_NAME = "canary.json"
REGULAR_FILE = "100644"


class PlantedCanary(Record):
    """One marker planted into a pair's repository cache, and the commit holding it."""

    pair_id: str
    marker: str
    commit: str


class CanaryLog(Record):
    """Every planted marker, as kept in canary.json."""

    planted: list[PlantedCanary]


@dataclass(frozen=True)
class CanaryHit:
    """A planted marker found in a file under the resolutions directory."""

    marker: str
    pair_id: str
    path: Path


def plant_canary(layout: Layout, pair: Pair, marker: str) -> PlantedCanary:
    """Commit the marker on top of the default branch tip at refs/ladder/canary and log it.

    The commit adds LADDER_CANARY.txt and appends the marker as a last line to each of the
    pair's conflicted paths present at the tip. No branch moves.
    """
    if not marker.strip() or "\n" in marker:
        raise RefusedError("the marker must be one non-empty line")
    cache = layout.cache_dir(pair.repo)
    if not cache.is_dir():
        raise RefusedError(f"no repository cache at {cache}; run `ladder pairs resolve`")
    git = read_optional(layout.result_file(pair.pair_id, "rung-git"), GitRungResult)
    if git is None:
        raise RefusedError(f"no git rung result for {pair.pair_id}; run `ladder rung git` first")
    tip = git_text(["rev-parse", "--verify", f"refs/heads/{default_branch(cache)}"], cache)
    paths = [file.path for file in git.files]
    entries = {p: e for p, e in tree_entries(cache, tip, paths).items() if e.kind == "blob"}
    ensure_files(cache, tip, list(entries))
    line = marker.encode() + b"\n"
    with tempfile.TemporaryDirectory(prefix="ladder-canary-") as scratch:
        index = {"GIT_INDEX_FILE": str(Path(scratch) / "index")}
        run_git(["read-tree", tip], cache, env=index)
        changed = {CANARY_FILE: (REGULAR_FILE, line)}
        for path, entry in entries.items():
            content = read_blob(cache, entry.sha)
            separator = b"\n" if content and not content.endswith(b"\n") else b""
            changed[path] = (entry.mode, content + separator + line)
        for path, (mode, content) in changed.items():
            cacheinfo = f"{mode},{_store(cache, content)},{path}"
            run_git(["update-index", "--add", "--cacheinfo", cacheinfo], cache, env=index)
        tree = run_git(["write-tree", "--missing-ok"], cache, env=index).stdout.decode().strip()
    commit = git_text(["commit-tree", tree, "-p", tip, "-m", "ladder canary"], cache)
    run_git(["update-ref", CANARY_REF, commit], cache)
    planted = PlantedCanary(pair_id=pair.pair_id, marker=marker, commit=commit)
    log = read_optional(layout.results / LOG_NAME, CanaryLog) or CanaryLog(planted=[])
    kept = [p for p in log.planted if (p.pair_id, p.marker) != (pair.pair_id, marker)]
    write_record(layout.results / LOG_NAME, CanaryLog(planted=[*kept, planted]))
    return planted


def check_canaries(layout: Layout) -> tuple[list[PlantedCanary], list[CanaryHit]]:
    """Search every file under the resolutions directory for every planted marker."""
    log = read_optional(layout.results / LOG_NAME, CanaryLog) or CanaryLog(planted=[])
    root = layout.work / "resolutions"
    files = sorted(p for p in root.rglob("*") if p.is_file()) if root.is_dir() else []
    hits: list[CanaryHit] = []
    for path in files:
        data = path.read_bytes()
        hits += [
            CanaryHit(canary.marker, canary.pair_id, path)
            for canary in log.planted
            if canary.marker.encode() in data
        ]
    return log.planted, hits


def _store(cache: Path, content: bytes) -> str:
    return run_git(["hash-object", "-w", "--stdin"], cache, stdin=content).stdout.decode().strip()
