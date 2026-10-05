"""Load the pairs file and every result record of every pair."""

import re
from dataclasses import dataclass
from pathlib import Path

from ladder.jsonio import read_optional, read_record
from ladder.layout import Layout
from ladder.schemas import (
    CalibrationRecord,
    ClaimCRecord,
    GitRungResult,
    Pair,
    PairSet,
    ResolverPlan,
    ResolverRun,
    ResolverTask,
    RungScore,
    Runnability,
    StructuralResult,
    TruthRecord,
)

RUN_RECORD = re.compile(r"resolver-.+-run-\d+")
CALIBRATION_FILE = "calibration.json"

type RunKey = tuple[str, int]


@dataclass(frozen=True)
class PairRecords:
    """A pair and every result record written for it; absent records are None or missing keys."""

    pair: Pair
    git_final: GitRungResult | None
    git: GitRungResult | None
    weave: StructuralResult | None
    mergiraf: StructuralResult | None
    plan: ResolverPlan | None
    tasks: dict[RunKey, ResolverTask]
    runs: dict[RunKey, ResolverRun]
    truth: TruthRecord | None
    runnability: Runnability | None
    claim_c: ClaimCRecord | None
    scores: dict[RunKey, RungScore]

    @property
    def pair_id(self) -> str:
        """Return the pair id."""
        return self.pair.pair_id

    @property
    def in_ladder(self) -> bool:
        """Return whether the pair conflicts under the git rung at replay heads."""
        return self.git is not None and self.git.status == "conflicted"

    @property
    def truth_located(self) -> bool:
        """Return whether the pair's human resolution was located."""
        return self.truth is not None and self.truth.status == "located"

    @property
    def conflicted_paths(self) -> list[str]:
        """Return the paths git left conflicted at replay heads."""
        return [] if self.git is None else [file.path for file in self.git.files]

    def score(self, rung: str, run: int = 1) -> RungScore | None:
        """Return the score of one rung run, or None."""
        return self.scores.get((rung, run))

    def planned(self, rung: str, run: int = 1) -> bool:
        """Return whether the resolver plan includes one rung run."""
        return self.plan is not None and any(
            planned.rung == rung and planned.run == run for planned in self.plan.runs
        )


@dataclass(frozen=True)
class Collected:
    """Every pair's records, the calibration sample, and result directories of unknown pairs."""

    pairs: list[PairRecords]
    calibration: CalibrationRecord | None
    unknown_dirs: list[str]


def collect(layout: Layout) -> Collected:
    """Read pairs.json and every record under the results directory."""
    pair_set = read_record(layout.pairs_file, PairSet)
    pairs = [_pair_records(layout, pair) for pair in pair_set.pairs]
    known = {pair.pair_id for pair in pair_set.pairs}
    pairs_dir = layout.results / "pairs"
    present = sorted(path.name for path in pairs_dir.iterdir()) if pairs_dir.is_dir() else []
    return Collected(
        pairs=pairs,
        calibration=read_optional(layout.results / CALIBRATION_FILE, CalibrationRecord),
        unknown_dirs=[name for name in present if name not in known],
    )


def _pair_records(layout: Layout, pair: Pair) -> PairRecords:
    pair_dir = layout.result_dir(pair.pair_id)

    def file(name: str) -> Path:
        return layout.result_file(pair.pair_id, name)

    tasks = [read_record(path, ResolverTask) for path in _matching(pair_dir, "resolver-*-task")]
    runs = [
        read_record(path, ResolverRun)
        for path in _matching(pair_dir, "resolver-*-run-*")
        if RUN_RECORD.fullmatch(path.stem)
    ]
    scores = [read_record(path, RungScore) for path in _matching(pair_dir, "score-*")]
    return PairRecords(
        pair=pair,
        git_final=read_optional(file("rung-git-final"), GitRungResult),
        git=read_optional(file("rung-git"), GitRungResult),
        weave=read_optional(file("rung-weave"), StructuralResult),
        mergiraf=read_optional(file("rung-mergiraf"), StructuralResult),
        plan=read_optional(file("resolver-plan"), ResolverPlan),
        tasks={(task.rung, task.run): task for task in tasks},
        runs={(run.rung, run.run): run for run in runs},
        truth=read_optional(file("truth"), TruthRecord),
        runnability=read_optional(file("runnability"), Runnability),
        claim_c=read_optional(file("claim-c"), ClaimCRecord),
        scores={(score.rung, score.run): score for score in scores},
    )


def _matching(directory: Path, pattern: str) -> list[Path]:
    return sorted(directory.glob(f"{pattern}.json"))
