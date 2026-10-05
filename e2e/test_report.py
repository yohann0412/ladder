"""F9 acceptance: the report's numbers equal those implied by the expected outcomes table."""

from pathlib import Path
from typing import Any

from conftest import REPO_ROOT, Experiment, read_json
from test_resolver import install_recorded_run as _install_recorded_run


def _count(scenarios: list[dict[str, Any]], rung: str, **want: object) -> int:
    return sum(
        1
        for s in scenarios
        if all(s["rungs"][rung].get(key) == value for key, value in want.items())
    )


def test_report_numbers_match_expected_table(fx: Experiment, tmp_path: Path) -> None:
    fx.ladder("run", "--all", "--no-llm")
    out = tmp_path / "RESULTS.md"
    fx.ladder("report", "--out", str(out))
    summary = read_json(fx.results / "summary.json")
    expected = read_json(REPO_ROOT / "fixtures" / "expected.json")["scenarios"]
    ladder_set = [s for s in expected if s["rungs"]["git"]["status"] == "conflicted"]
    replayable = [s for s in expected if s["rungs"]["git"]["status"] != "absent"]

    assert summary["pairs_attempted"] == len(expected)
    assert summary["ladder_set"] == len(ladder_set)
    assert summary["truth_located"] == len(ladder_set)
    pool = summary["replay_conflict_rate"]["pool"]
    assert (pool["numerator"], pool["denominator"]) == (len(ladder_set), len(replayable))
    assert summary["resolve_status"] == {"ok": 9, "unrecoverable_rebased": 1}

    rows = {row["rung"]: row for row in summary["rungs"]}
    git_row = rows["git"]
    assert (git_row["mergeable"]["numerator"], git_row["mergeable"]["denominator"]) == (
        0,
        len(ladder_set),
    )
    for tool in ("weave", "mergiraf"):
        row = rows[tool]
        resolved = _count(ladder_set, tool, status="resolved")
        assert row["mergeable"]["numerator"] == resolved, tool
        assert row["mergeable"]["denominator"] == len(ladder_set), tool
        equivalent = _count(ladder_set, tool, human_equivalent=True)
        assert row["human_equivalent"]["numerator"] == equivalent, tool

    trap = rows["trap"]
    assert (
        trap["tests_pass_intent_dropped"]["numerator"],
        trap["tests_pass_intent_dropped"]["denominator"],
    ) == (1, 1)
    assert trap["intent_dropped"]["numerator"] == 1

    assert rows["llm-raw"]["available"]["numerator"] == 0
    claim_c = summary["claim_c_fails_together"]
    assert (claim_c["numerator"], claim_c["denominator"]) == (1, 2)
    assert 0 <= claim_c["ci_low"] <= 0.5 <= claim_c["ci_high"] <= 1

    text = out.read_text()
    first_paragraph = text.split("\n\n")[1] if text.startswith("#") else text.split("\n\n")[0]
    for claim in ("Claim A", "Claim B", "Claim C"):
        assert claim in first_paragraph, claim
    assert set(summary["verdicts"]) == {"A", "B", "C"}
    assert (fx.results / "plots").is_dir() and len(list((fx.results / "plots").glob("*.png"))) >= 3


def test_report_separates_own_output_reads_and_cut_transcripts(
    fx_resolved: Experiment, tmp_path: Path
) -> None:
    fx = fx_resolved
    fx.ladder("run", "fx03", check=False)
    raw = fx.result("fx03", "resolver-llm-raw-run-1-task")
    post = fx.result("fx03", "resolver-llm-post-weave-run-1-task")

    own_read = tmp_path / "raw.jsonl"
    _install_recorded_run(raw, own_read, extra_read=str(Path(raw["output_dir"]) / "rationale.json"))
    cut = tmp_path / "post.jsonl"
    _install_recorded_run(post, cut, extra_read=None)
    text = cut.read_text()
    cut.write_text(text[: len(text) - 40])
    for rung, transcript in (("llm-raw", own_read), ("llm-post-weave", cut)):
        fx.ladder(
            "resolve",
            "finalize",
            "fx03",
            "--rung",
            rung,
            "--run",
            "1",
            "--transcript",
            str(transcript),
        )
    assert fx.result("fx03", "resolver-llm-raw-run-1")["failure"] == "protocol_violation"
    assert fx.result("fx03", "resolver-llm-post-weave-run-1")["failure"] == "audit_impossible"

    fx.ladder("run", "--all", "--no-llm")
    out = tmp_path / "RESULTS.md"
    fx.ladder("report", "--out", str(out))
    summary = read_json(fx.results / "summary.json")

    causes = summary["llm_failure_causes"]
    assert causes["protocol_violation: own output reads only"] == 1
    assert causes["audit_impossible: transcript cut off"] == 1
    primary = summary["practical_ladder_human_equivalent"]
    bound = summary["claim_a_best_case"]
    assert bound["denominator"] == primary["denominator"]
    assert bound["numerator"] == primary["numerator"] + 1
    assert "A best case" in summary["verdicts"]
    report = out.read_text()
    assert "own output reads only" in report and "transcript cut off" in report
    assert "best-case" in report
