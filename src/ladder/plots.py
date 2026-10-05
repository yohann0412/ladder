"""Draw one PNG per claim from the summary with matplotlib's Agg backend.

matplotlib types its styling keyword arguments as unknown, so the unknown-member check is
relaxed in this module alone.
"""
# pyright: reportUnknownMemberType=false

from dataclasses import dataclass
from pathlib import Path

from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from ladder.schemas import Rate, Summary
from ladder.verdicts import (
    CLAIM_A_THRESHOLD,
    HUMAN_BASE_RATE,
    INTENT_DROPPED_THRESHOLD,
    TESTS_PASS_DROPPED_THRESHOLD,
)

SERIES = ("#2a78d6", "#eb6834")
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
LARGE_TEAM_BASE_RATE = 12.5
BAR = 0.36
DPI = 120

CLAIM_A_PLOT = "claim-a-ladder.png"
CLAIM_B_PLOT = "claim-b-intent.png"
CLAIM_C_PLOT = "claim-c-rate.png"


@dataclass(frozen=True)
class Plot:
    """A written plot and the alt text the report shows for it."""

    path: Path
    caption: str


def _ratio(rate: Rate) -> str:
    return f"{rate.numerator}/{rate.denominator}"


def _axes(rows: int, title: str) -> tuple[Figure, Axes]:
    figure = Figure(figsize=(8, 1.6 + 0.5 * rows), dpi=DPI, layout="constrained")
    FigureCanvasAgg(figure)
    axes = figure.add_subplot()
    axes.set_title(title, loc="left", fontsize=11, color=INK, pad=14)
    axes.set_xlim(0, 100)
    axes.set_xlabel("percent (whiskers: Wilson 95% interval)", color=MUTED)
    axes.grid(axis="x", color=GRID, linewidth=1)
    axes.set_axisbelow(True)
    for side in ("top", "right"):
        axes.spines[side].set_visible(False)
    axes.tick_params(colors=MUTED)
    return figure, axes


def _bars(axes: Axes, offsets: list[float], rates: list[Rate], color: str, label: str) -> None:
    values = [rate.pct or 0.0 for rate in rates]
    lows = [v - 100 * (r.ci_low or 0.0) for v, r in zip(values, rates, strict=True)]
    highs = [100 * (r.ci_high or 0.0) - v for v, r in zip(values, rates, strict=True)]
    axes.barh(
        offsets,
        values,
        height=BAR,
        color=color,
        label=label,
        xerr=[[max(0.0, low) for low in lows], [max(0.0, high) for high in highs]],
        error_kw={"ecolor": INK, "elinewidth": 1, "capsize": 3},
    )


def _rows(axes: Axes, labels: list[str]) -> list[float]:
    offsets = [float(index) for index in range(len(labels))]
    axes.set_yticks(offsets, labels)
    axes.set_ylim(max(len(labels), 1) - 0.5, -0.5)
    return offsets


def _threshold(axes: Axes, value: float, label: str, *, left: bool = False) -> None:
    axes.axvline(value, color=MUTED, linewidth=1)
    axes.text(
        value,
        1.0,
        f"{label} " if left else f" {label}",
        transform=axes.get_xaxis_transform(),
        fontsize=8,
        color=MUTED,
        va="bottom",
        ha="right" if left else "left",
    )


def _save(figure: Figure, path: Path) -> None:
    figure.savefig(path, format="png", metadata={"Software": None})


def claim_a(summary: Summary, path: Path) -> Plot:
    """Plot human-equivalent rates per rung and for the practical and oracle ladders."""
    practical = summary.practical_ladder_human_equivalent
    named = [(row.rung, row.human_equivalent) for row in summary.rungs] + [
        ("practical ladder", practical),
        ("oracle ladder", summary.oracle_ladder_human_equivalent),
    ]
    figure, axes = _axes(
        len(named), f"Claim A: human-equivalent resolutions, practical ladder {_ratio(practical)}"
    )
    offsets = _rows(axes, [f"{name} ({_ratio(rate)})" for name, rate in named])
    _bars(axes, offsets, [rate for _, rate in named], SERIES[0], "human-equivalent")
    _threshold(axes, CLAIM_A_THRESHOLD, "90% rule")
    _save(figure, path)
    return Plot(path, "Claim A: human-equivalent share per rung and ladder")


def claim_b(summary: Summary, path: Path) -> Plot:
    """Plot intent-dropped and tests-pass-but-intent-dropped rates per rung."""
    rows = summary.rungs
    raw = next((row for row in rows if row.rung == "llm-raw"), None)
    focus = "no llm-raw score" if raw is None else f"llm-raw {_ratio(raw.intent_dropped)}"
    figure, axes = _axes(len(rows), f"Claim B: intent dropped, {focus}")
    offsets = _rows(
        axes,
        [
            f"{row.rung} ({_ratio(row.intent_dropped)}; {_ratio(row.tests_pass_intent_dropped)})"
            for row in rows
        ],
    )
    _bars(
        axes,
        [offset - BAR / 2 for offset in offsets],
        [row.intent_dropped for row in rows],
        SERIES[0],
        "intent dropped, over available outputs",
    )
    _bars(
        axes,
        [offset + BAR / 2 for offset in offsets],
        [row.tests_pass_intent_dropped for row in rows],
        SERIES[1],
        "tests pass but intent dropped, over outputs with a decided suite",
    )
    _threshold(axes, TESTS_PASS_DROPPED_THRESHOLD, "10%", left=True)
    _threshold(axes, INTENT_DROPPED_THRESHOLD, "15%")
    figure.legend(loc="outside lower center", fontsize=8, frameon=False)
    _save(figure, path)
    return Plot(path, "Claim B: intent dropped and tests pass but intent dropped per rung")


def claim_c(summary: Summary, path: Path) -> Plot:
    """Plot the fails-together rate against the human base rates."""
    rate = summary.claim_c_fails_together
    figure, axes = _axes(1, f"Claim C: pass alone, fail together, {_ratio(rate)} clean pairs")
    offsets = _rows(axes, [f"fails together ({_ratio(rate)})"])
    _bars(axes, offsets, [rate], SERIES[0], "fails together")
    _threshold(axes, HUMAN_BASE_RATE, "1%")
    _threshold(axes, LARGE_TEAM_BASE_RATE, "12.5%")
    _save(figure, path)
    return Plot(path, "Claim C: fails-together rate against the 1% and 12.5% human base rates")


def write_plots(summary: Summary, directory: Path) -> list[Plot]:
    """Write the three claim plots into a directory and return them."""
    directory.mkdir(parents=True, exist_ok=True)
    return [
        claim_a(summary, directory / CLAIM_A_PLOT),
        claim_b(summary, directory / CLAIM_B_PLOT),
        claim_c(summary, directory / CLAIM_C_PLOT),
    ]
