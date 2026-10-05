"""The scratch layout of one pair's runtime directory: trees, environments, logs, reports."""

import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path

from ladder.completion import unmark
from ladder.layout import Layout

BASE_LABEL = "base"


def remove_tree(path: Path) -> None:
    """Delete a directory tree, including read-only directories; a missing path is fine."""
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
    except PermissionError:
        path.chmod(stat.S_IRWXU)
        for root, dirnames, _ in os.walk(path):
            for name in dirnames:
                directory = Path(root) / name
                if not directory.is_symlink():
                    directory.chmod(stat.S_IRWXU)
        shutil.rmtree(path)


@dataclass(frozen=True)
class RuntimeDir:
    """Where a pair's exported trees, installed environments, logs and reports live."""

    root: Path

    def tree(self, label: str) -> Path:
        """Return the directory a labelled source tree is exported into."""
        return self.root / "trees" / label

    def env(self, label: str) -> Path:
        """Return the environment directory installed for a labelled tree."""
        return self.root / "envs" / label

    def logs(self, label: str) -> Path:
        """Return the log directory of a labelled tree's installs and runs."""
        return self.root / "logs" / label

    def reports(self, label: str) -> Path:
        """Return the directory of a labelled tree's machine-readable test reports."""
        return self.root / "reports" / label

    def scratch_repo(self) -> Path:
        """Return the scratch bare clone in which the clean merge is re-created."""
        return self.root / "merge.git"

    def clear(self, label: str) -> None:
        """Delete everything stored for a labelled tree."""
        for path in (self.tree(label), self.env(label), self.logs(label), self.reports(label)):
            remove_tree(path)

    def reset(self) -> None:
        """Delete the whole runtime directory, the base tree's completion mark first."""
        unmark(self.tree(BASE_LABEL))
        remove_tree(self.root)


def runtime_for(layout: Layout, record_id: str) -> RuntimeDir:
    """Return the runtime directory of a pair or directory id, as an absolute path."""
    return RuntimeDir(layout.runtime_dir(record_id).resolve())
