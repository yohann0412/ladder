"""Read the replay study's pair-level CSV (`rq3_merge_replay_full.csv`)."""

import csv
from pathlib import Path

from pydantic import Field

from ladder.extracts import PrKey
from ladder.schemas import PaperLabel, Record, Stratum

REPLAY_CSV = "rq3_merge_replay_full.csv"


class ReplayRow(Record):
    """One row of the replay CSV: a pair, its agents and the paper's merge label."""

    stratum: Stratum
    repo: str
    pr_a: int = Field(validation_alias="prA")
    pr_b: int = Field(validation_alias="prB")
    agent_a: str = Field(validation_alias="agentA")
    agent_b: str = Field(validation_alias="agentB")
    label: PaperLabel
    n_files: int
    files: list[str]
    types: list[str]

    @property
    def keys(self) -> tuple[PrKey, PrKey]:
        """Return the (repository, number) keys of PR A and PR B."""
        return ((self.repo, self.pr_a), (self.repo, self.pr_b))


def read_replay(path: Path) -> list[ReplayRow]:
    """Read every row of the replay CSV, splitting `files` and `types` on `|`."""
    with path.open(newline="", encoding="utf-8") as handle:
        return [ReplayRow.model_validate(_split_lists(row)) for row in csv.DictReader(handle)]


def _split_lists(row: dict[str, str]) -> dict[str, object]:
    return {
        **row,
        "files": row["files"].split("|") if row["files"] else [],
        "types": row["types"].split("|") if row["types"] else [],
    }
