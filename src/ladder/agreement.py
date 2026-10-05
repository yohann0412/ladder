"""Agreement between the two llm-raw runs of a pair (resolver variance)."""

from dataclasses import dataclass

from ladder.collect import PairRecords
from ladder.compare import compare_versions
from ladder.languages import language_for
from ladder.layout import Layout

VARIANCE_RUNG = "llm-raw"


@dataclass(frozen=True)
class RunAgreement:
    """Whether runs 1 and 2 of llm-raw left every conflicted file equivalent."""

    pair_id: str
    differing: list[str]

    @property
    def agrees(self) -> bool:
        """Return whether no conflicted file differs between the runs."""
        return not self.differing


def run_agreements(layout: Layout, pairs: list[PairRecords]) -> list[RunAgreement]:
    """Compare runs 1 and 2 of llm-raw on every pair where both finished ok."""
    return [
        RunAgreement(
            pair_id=pair.pair_id,
            differing=[
                path
                for path in pair.conflicted_paths
                if not _same_output(layout, pair.pair_id, path)
            ],
        )
        for pair in pairs
        if _both_ok(pair)
    ]


def _both_ok(pair: PairRecords) -> bool:
    runs = [pair.runs.get((VARIANCE_RUNG, number)) for number in (1, 2)]
    return all(run is not None and run.status == "ok" for run in runs)


def _same_output(layout: Layout, pair_id: str, path: str) -> bool:
    first, second = (_output(layout, pair_id, number, path) for number in (1, 2))
    if first is None or second is None:
        return first is None and second is None
    return compare_versions(first, second, language_for(path)).equivalent


def _output(layout: Layout, pair_id: str, run: int, path: str) -> bytes | None:
    file = layout.resolution_dir(pair_id, VARIANCE_RUNG, run) / "files" / path
    return file.read_bytes() if file.is_file() else None
