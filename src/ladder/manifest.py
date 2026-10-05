"""Record what a resolver task directory held when prepared, and find what changed since."""

import hashlib
import os
from pathlib import Path

from ladder.layout import Layout
from ladder.schemas import LlmRung, Record


class TaskManifest(Record):
    """The sha256 of every file under a resolver task directory, kept outside that directory."""

    task_dir: str
    files: dict[str, str]


def manifest_path(layout: Layout, pair_id: str, rung: LlmRung, run: int) -> Path:
    """Return where the manifest of one resolver task is stored."""
    return layout.work / "resolver-manifests" / pair_id / f"{rung}-run-{run}.json"


def take_manifest(task_dir: Path) -> TaskManifest:
    """Hash every file under a task directory; a symlink is hashed by its target."""
    files: dict[str, str] = {}
    for root, dirs, names in os.walk(task_dir):
        here = Path(root)
        linked = [name for name in dirs if (here / name).is_symlink()]
        for name in [*names, *linked]:
            path = here / name
            data = os.fsencode(path.readlink()) if path.is_symlink() else path.read_bytes()
            files[path.relative_to(task_dir).as_posix()] = hashlib.sha256(data).hexdigest()
    return TaskManifest(task_dir=str(task_dir), files=dict(sorted(files.items())))


def manifest_changes(manifest: TaskManifest) -> list[str]:
    """Return one message per file of the task directory that was added, removed or modified."""
    task_dir = Path(manifest.task_dir)
    if not task_dir.is_dir():
        return [f"task directory removed after prepare: {task_dir}"]
    before, now = manifest.files, take_manifest(task_dir).files
    return [
        f"task directory changed after prepare: {path} {_change(before.get(path), now.get(path))}"
        for path in sorted(before.keys() | now.keys())
        if before.get(path) != now.get(path)
    ]


def _change(before: str | None, now: str | None) -> str:
    if before is None:
        return "added"
    if now is None:
        return "removed"
    return "modified"
