"""Compare a resolution with the human one: AST-equivalent, equivalent up to order, similarity."""

from collections.abc import Iterable
from dataclasses import dataclass

from ladder.compare import compare_versions
from ladder.jsonio import read_optional
from ladder.layout import Layout
from ladder.schemas import TruthRecord


@dataclass(frozen=True)
class Truth:
    """The located human resolution of each conflicted path; None where the human deleted it."""

    files: dict[str, bytes | None]


@dataclass(frozen=True)
class Equivalence:
    """How one resolved path compares with the truth; all None without a located truth."""

    equivalent: bool | None
    unordered: bool | None
    similarity: float | None


UNKNOWN = Equivalence(None, None, None)


def load_truth(layout: Layout, pair_id: str) -> Truth | None:
    """Read a pair's located truth files, or return None when its truth is not located."""
    record = read_optional(layout.result_file(pair_id, "truth"), TruthRecord)
    if record is None or record.status != "located":
        return None
    root = layout.truth_dir(pair_id) / "files"
    return Truth(
        {
            file.path: (root / file.path).read_bytes() if file.present else None
            for file in record.files
        }
    )


def against_truth(
    path: str, resolved: bytes | None, language: str | None, truth: Truth | None
) -> Equivalence:
    """Compare one resolved path with the truth; both absent is equivalent, one absent is not."""
    if truth is None or path not in truth.files:
        return UNKNOWN
    human = truth.files[path]
    if resolved is None or human is None:
        same = resolved is None and human is None
        return Equivalence(same, same, 1.0 if same else 0.0)
    comparison = compare_versions(resolved, human, language)
    return Equivalence(
        comparison.equivalent, comparison.equivalent_unordered, comparison.similarity
    )


def every(values: Iterable[bool | None]) -> bool | None:
    """Return whether every per-file verdict holds, or None when any verdict is unknown."""
    verdicts = list(values)
    if any(verdict is None for verdict in verdicts):
        return None
    return all(verdicts)
