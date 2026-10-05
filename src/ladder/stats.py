"""Proportions with Wilson 95% intervals."""

from collections.abc import Callable, Iterable
from math import sqrt

from ladder.schemas import Rate

Z95 = 1.96


def wilson(numerator: int, denominator: int, z: float = Z95) -> tuple[float, float]:
    """Return the Wilson score interval of numerator/denominator as proportions."""
    p = numerator / denominator
    z2 = z * z
    scale = 1 + z2 / denominator
    centre = (p + z2 / (2 * denominator)) / scale
    half = z * sqrt(p * (1 - p) / denominator + z2 / (4 * denominator * denominator)) / scale
    return max(0.0, centre - half), min(1.0, centre + half)


def rate(numerator: int, denominator: int) -> Rate:
    """Return a Rate with percent to 1 decimal and interval bounds to 4 decimals."""
    if denominator == 0:
        return Rate(numerator=numerator, denominator=0, pct=None, ci_low=None, ci_high=None)
    low, high = wilson(numerator, denominator)
    return Rate(
        numerator=numerator,
        denominator=denominator,
        pct=round(100 * numerator / denominator, 1),
        ci_low=round(low, 4),
        ci_high=round(high, 4),
    )


def share[T](items: Iterable[T], hit: Callable[[T], bool]) -> Rate:
    """Return the Rate of items for which hit is true."""
    flags = [hit(item) for item in items]
    return rate(sum(flags), len(flags))
