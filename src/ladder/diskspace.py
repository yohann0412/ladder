"""Wait for free disk space before a pair's working copies are built."""

import shutil
import time
from collections.abc import Callable
from pathlib import Path

GIB = 1024**3
POLL_S = 20.0


def free_gib(path: Path) -> float:
    """Return the free space, in GiB, of the file system holding a path or its nearest parent."""
    probe = path.absolute()
    while not probe.exists():
        probe = probe.parent
    return shutil.disk_usage(probe).free / GIB


def wait_for_disk(path: Path, min_free_gib: float, say: Callable[[str], None]) -> None:
    """Poll every 20 s, saying why, while less than min_free_gib is free under a path."""
    while (free := free_gib(path)) < min_free_gib:
        say(
            f"waiting: {free:.1f} GiB free under {path}, below the {min_free_gib:g} GiB minimum; "
            f"checking again in {POLL_S:g} s"
        )
        time.sleep(POLL_S)
