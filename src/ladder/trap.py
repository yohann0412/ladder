"""Install a fixture scenario's planted wrong resolution as the output of the trap rung."""

import shutil
from pathlib import Path

from ladder.layout import Layout
from ladder.refusal import RefusedError
from ladder.schemas import Pair

TRAP_RUNG = "trap"
TRAP_RUN = 1


def install_trap(layout: Layout, pair: Pair) -> Path:
    """Copy the pair's trap files/ and rationale.json into the trap rung's resolution directory."""
    if pair.trap_dir is None:
        raise RefusedError(f"{pair.pair_id} has no trap directory; only trap scenarios have one")
    source = Path(pair.trap_dir)
    target = layout.resolution_dir(pair.pair_id, TRAP_RUNG, TRAP_RUN)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    shutil.copytree(source / "files", target / "files")
    shutil.copy2(source / "rationale.json", target / "rationale.json")
    return target
