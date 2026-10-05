"""Check that a workspace holds its three synthetic commits and nothing that leads elsewhere."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ladder.gitio import run_git

ABSENT = {
    "no_alternates": "objects/info/alternates",
    "no_fetch_head": "FETCH_HEAD",
    "no_logs": "logs",
    "no_shallow": "shallow",
}


@dataclass(frozen=True)
class Check:
    """One leak check of a workspace and what it saw."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class Verification:
    """Every leak check of a workspace, and how many objects it stores."""

    checks: list[Check]
    object_count: int

    @property
    def passed(self) -> bool:
        """Return whether every check passed."""
        return all(check.passed for check in self.checks)


def verify_workspace(path: Path, refs: Mapping[str, str]) -> Verification:
    """Run every leak check on a workspace whose only refs must be these, naming these commits."""
    stored = _lines(path, "cat-file", "--batch-all-objects", "--batch-check")
    reachable = _lines(path, "rev-list", "--objects", "--all")
    checks = [
        *_history_checks(path, refs),
        Check(
            "all_objects_reachable",
            len(stored) == len(reachable),
            f"{len(stored)} stored, {len(reachable)} reachable",
        ),
    ]
    return Verification(checks, len(stored))


def verify_snapshot(path: Path, refs: Mapping[str, str]) -> Verification:
    """Run the leak checks on a merge-state copy of a workspace.

    A merge writes derived blobs and trees that no ref reaches, so reachability is not
    checked; instead every pseudo-ref such as MERGE_HEAD must name one of the commits.
    """
    stored = _lines(path, "cat-file", "--batch-all-objects", "--batch-check")
    checks = [*_history_checks(path, refs), _pseudo_refs(path, set(refs.values()))]
    return Verification(checks, len(stored))


def _history_checks(path: Path, refs: Mapping[str, str]) -> list[Check]:
    return [
        _commits(path, sorted(refs.values())),
        _refs(path, refs),
        _remote(path),
        *(_absent(path, name, relative) for name, relative in ABSENT.items()),
    ]


def _commits(path: Path, expected: list[str]) -> Check:
    listed = _lines(path, "rev-list", "--all")
    unexpected = sorted(set(listed) - set(expected))
    detail = f"{len(listed)} commits" + "".join(f", unexpected {sha}" for sha in unexpected)
    return Check("three_commits", sorted(listed) == expected, detail)


def _refs(path: Path, expected: Mapping[str, str]) -> Check:
    listed = _lines(path, "for-each-ref", "--format=%(refname) %(objectname)")
    found = {name: sha for name, sha in (line.split(" ") for line in listed)}
    problems = [f"unexpected {name}" for name in sorted(found.keys() - expected.keys())]
    problems += [f"missing {name}" for name in sorted(expected.keys() - found.keys())]
    problems += [
        f"{name} names {found[name]}, not {sha}"
        for name, sha in sorted(expected.items())
        if name in found and found[name] != sha
    ]
    return Check("three_refs", not problems, "; ".join(problems) or ", ".join(sorted(found)))


def _pseudo_refs(path: Path, commits: set[str]) -> Check:
    named: list[str] = []
    problems: list[str] = []
    for file in sorted((path / ".git").glob("*_HEAD")):
        if file.name == ABSENT["no_fetch_head"]:
            continue
        named.append(file.name)
        for line in file.read_text(encoding="utf-8", errors="replace").splitlines():
            target = line.split(maxsplit=1)[0] if line.strip() else ""
            if target and target not in commits:
                problems.append(f"{file.name} names {target}, not one of the three commits")
    detail = "; ".join(problems) or ", ".join(named) or "no pseudo-refs"
    return Check("pseudo_refs", not problems, detail)


def _remote(path: Path) -> Check:
    remotes = _lines(path, "remote")
    return Check("no_remote", not remotes, ", ".join(remotes) or "none")


def _absent(path: Path, name: str, relative: str) -> Check:
    present = (path / ".git" / relative).exists()
    return Check(name, not present, f".git/{relative} {'exists' if present else 'absent'}")


def _lines(path: Path, *args: str) -> list[str]:
    return run_git(args, path).stdout.decode("utf-8", "replace").splitlines()
