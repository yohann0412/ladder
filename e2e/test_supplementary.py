"""S acceptance: the supplementary sample follows the pre-registered rule and is deterministic."""

from datetime import datetime
from pathlib import Path
from typing import Any

from conftest import LADDER, read_json, run


def _sample(out: Path, seed: int) -> list[dict[str, Any]]:
    argv = [LADDER, "--pairs", str(out), "pairs", "sample-supplementary"]
    run([*argv, "--source", "data/source", "--seed", str(seed)])
    return read_json(out)["pairs"]


def _time(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00"))


def test_supplementary_sample(tmp_path: Path) -> None:
    first = _sample(tmp_path / "one.json", 42)
    second = _sample(tmp_path / "two.json", 42)
    assert first == second
    assert len(first) >= 900

    paper_out = tmp_path / "paper.json"
    run([LADDER, "--pairs", str(paper_out), "pairs", "load", "--source", "data/source"])
    paper_keys = {
        (p["repo"], p["a"]["number"], p["b"]["number"]) for p in read_json(paper_out)["pairs"]
    }

    repos = [p["repo"] for p in first]
    assert len(repos) == len(set(repos))
    for pair in first:
        a, b = pair["a"], pair["b"]
        assert pair["origin"] == "supplementary" and pair["paper"] is None
        assert pair["stratum"] == ("same" if a["agent"] == b["agent"] else "cross")
        assert a["merged_at"] and b["merged_at"]
        assert _time(a["created_at"]) <= _time(b["created_at"]) <= _time(a["merged_at"])
        assert (pair["repo"], a["number"], b["number"]) not in paper_keys
        assert pair["pair_id"] == f"{pair['repo'].replace('/', '__')}__{a['number']}-{b['number']}"

    reshuffled = _sample(tmp_path / "three.json", 7)
    assert sorted(p["pair_id"] for p in reshuffled) == sorted(p["pair_id"] for p in first)
    assert [p["pair_id"] for p in reshuffled] != [p["pair_id"] for p in first]
