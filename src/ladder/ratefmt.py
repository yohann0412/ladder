"""Render rates as text for the report and the terminal."""

from ladder.schemas import Rate
from ladder.stats import wilson


def interval(rate: Rate) -> str:
    """Return the Wilson interval in percent as `[lo%, hi%]`, or `-` when undefined."""
    if rate.denominator == 0:
        return "-"
    low, high = wilson(rate.numerator, rate.denominator)
    return f"[{100 * low:.1f}%, {100 * high:.1f}%]"


def cell(rate: Rate) -> str:
    """Return `k/n (pct%, [lo%, hi%])`, or `k/0 (-)` for an empty denominator."""
    if rate.pct is None:
        return f"{rate.numerator}/{rate.denominator} (-)"
    return f"{rate.numerator}/{rate.denominator} ({rate.pct:.1f}%, {interval(rate)})"


def phrase(rate: Rate) -> str:
    """Return `k/n (pct%, 95% CI [lo%, hi%])` for use inside a sentence."""
    if rate.pct is None:
        return f"{rate.numerator}/{rate.denominator}"
    return f"{rate.numerator}/{rate.denominator} ({rate.pct:.1f}%, 95% CI {interval(rate)})"
