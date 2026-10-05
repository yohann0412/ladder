"""The free-disk floor installers and test runners keep, read from LADDER_MIN_FREE_GIB."""

import math
import os

FLOOR_ENV = "LADDER_MIN_FREE_GIB"
DEFAULT_FLOOR_GIB = 3.0
FREE_DISK = "free disk below the"


def min_free_gib() -> float:
    """Return the GiB floor from LADDER_MIN_FREE_GIB, 3 when unset; raise unless it is positive."""
    raw = os.environ.get(FLOOR_ENV)
    if raw is None:
        return DEFAULT_FLOOR_GIB
    problem = f"{FLOOR_ENV} must be a positive number of GiB, got {raw!r}"
    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError(problem) from error
    if not math.isfinite(value) or value <= 0:
        raise ValueError(problem)
    return value


def stopped_below(floor: float) -> str:
    """Return the words saying a step was stopped because free disk fell below a floor."""
    return f"stopped, {FREE_DISK} {floor:g} GiB floor"
