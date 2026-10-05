"""F1a acceptance: the vendored pair sources load into pairs.json and match the paper."""

from collections import Counter
from pathlib import Path

from conftest import LADDER, read_json, run


def test_pairs_load_reproduces_paper_totals(tmp_path: Path) -> None:
    out = tmp_path / "pairs.json"
    proc = run([LADDER, "--pairs", str(out), "pairs", "load", "--source", "data/source"])
    pairs = read_json(out)["pairs"]

    assert len(pairs) == 747
    assert len({p["pair_id"] for p in pairs}) == 747
    labels = Counter((p["paper"]["stratum"], p["paper"]["label"]) for p in pairs)
    assert labels[("same", "CONFLICT")] == 119
    assert labels[("same", "CONFLICT")] + labels[("same", "CLEAN")] == 601
    assert labels[("cross", "CONFLICT")] == 48
    assert labels[("cross", "CONFLICT")] + labels[("cross", "CLEAN")] == 115

    types = Counter(
        t for p in pairs if p["paper"]["label"] == "CONFLICT" for t in p["paper"]["types"]
    )
    assert (types["content"], types["modify/delete"], types["add/add"]) == (952, 442, 249)
    assert sum(len(p["paper"]["files"]) for p in pairs) == 1646

    for p in pairs:
        assert p["origin"] == "paper"
        assert p["clone_url"] == f"https://github.com/{p['repo']}.git"
        assert p["a"]["agent"] and p["b"]["agent"]
        assert p["refs"] is None
    with_text = [p for p in pairs if p["a"]["title"] and p["b"]["title"]]
    assert len(with_text) >= 727

    for line in ("119/601", "48/115", "952", "442", "249"):
        assert line in proc.stdout, line
