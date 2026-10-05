"""F9 acceptance: the report's numbers equal those implied by the expected outcomes table."""

import json
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


def _rewrite_claim_c(fx: Experiment, pair_id: str, **sides: dict[str, Any]) -> None:
    """Replace outcomes of a pair's Claim C record, as a real run that went that way would."""
    path = fx.results / "pairs" / pair_id / "claim-c.json"
    record = read_json(path)
    reasons: list[str] = []
    for side, change in sides.items():
        record[side] = {**record[side], **change}
        reasons.append(f"error at {side}: {change['detail'][:200]}")
    record["fails_together"] = None
    record["excluded_reason"] = "; ".join(reasons)
    path.write_text(json.dumps(record, indent=2) + "\n")


def test_report_groups_claim_c_exclusions_and_cut(fx: Experiment, tmp_path: Path) -> None:
    fx.ladder("run", "--all", "--no-llm")
    assert fx.result("fx09", "claim-c")["a"]["status"] == "passed"
    install_error: dict[str, Any] = {
        "status": "error",
        "failing_tests": [],
        "passed": 0,
        "failed": 0,
    }
    _rewrite_claim_c(
        fx,
        "fx09",
        merge={
            **install_error,
            "detail": "dependency manifests differ from base (pyproject.toml); installed "
            "again; install failed: uv sync: exit 1 in 3.1 s: No solution found",
        },
    )
    _rewrite_claim_c(
        fx,
        "fx06",
        a={
            **install_error,
            "detail": "environment reused from base; install failed: build: stopped, free "
            "disk below the 3 GiB floor",
        },
    )

    out = tmp_path / "RESULTS.md"
    fx.ladder("report", "--out", str(out))
    summary = read_json(fx.results / "summary.json")
    assert summary["claim_c_exclusions"] == {
        "merge breaks dependency installation": 1,
        "stopped at the free-disk floor": 1,
    }
    assert (summary["claim_c_clean_pairs"], summary["claim_c_attempted"]) == (2, 2)
    assert summary["claim_c_not_attempted"] == 0
    rate = summary["claim_c_fails_together"]
    assert (rate["numerator"], rate["denominator"]) == (0, 0)
    claim_c = out.read_text().split("## Claim C")[1].split("\n## ")[0]
    assert "merge breaks dependency installation" in claim_c
    assert "stopped at the free-disk floor" in claim_c
    assert "No solution found" not in claim_c

    (fx.results / "pairs" / "fx06" / "claim-c.json").unlink()
    fx.ladder("report", "--out", str(out))
    summary = read_json(fx.results / "summary.json")
    assert summary["claim_c_exclusions"] == {"merge breaks dependency installation": 1}
    assert (summary["claim_c_attempted"], summary["claim_c_not_attempted"]) == (1, 1)
    report = out.read_text()
    assert "not attempted: cut" in report.split("## Claim C")[1].split("\n## ")[0]
    fx06_row = next(line for line in report.splitlines() if line.startswith("| fx06 "))
    assert "not attempted: cut" in fx06_row


def test_report_counts_records_redone_under_d23(fx: Experiment, tmp_path: Path) -> None:
    fx.ladder("run", "--all", "--no-llm")
    redo = {
        "rule": "D23",
        "pairs": [
            {
                "pair_id": "fx09",
                "records": ["runnability.json", "claim-c.json"],
                "redone_at": "2026-10-05T14:30:00Z",
            },
            {
                "pair_id": "fx03",
                "records": ["runnability.json", "score-git.json", "score-weave.json"],
                "redone_at": "2026-10-05T14:31:00Z",
            },
        ],
    }
    (fx.results / "redo-d23.json").write_text(json.dumps(redo, indent=2) + "\n")
    out = tmp_path / "RESULTS.md"
    fx.ladder("report", "--out", str(out))
    summary = read_json(fx.results / "summary.json")
    assert summary["d23_redone_pairs"] == 2
    assert summary["d23_replaced_records"] == 5
    report = out.read_text()
    assert "D23" in report and "5 records" in report and "2 pairs" in report

    (fx.results / "redo-d23.json").unlink()
    fx.ladder("report", "--out", str(out))
    summary = read_json(fx.results / "summary.json")
    assert (summary["d23_redone_pairs"], summary["d23_replaced_records"]) == (0, 0)


def test_report_splits_calibration_and_qualifies_claim_b(
    fx_resolved: Experiment, tmp_path: Path
) -> None:
    fx = fx_resolved
    fx.ladder("run", "fx03", check=False)
    for rung in ("llm-raw", "llm-post-weave"):
        task = fx.result("fx03", f"resolver-{rung}-run-1-task")
        transcript = tmp_path / f"{rung}.jsonl"
        _install_recorded_run(task, transcript, extra_read=None)
        fx.ladder(
            "resolve", "finalize", "fx03", "--rung", rung, "--run", "1",
            "--transcript", str(transcript),
        )  # fmt: skip
    fx.ladder("run", "--all", "--no-llm")

    def verdict(rung: str, metric: str, agrees: bool) -> dict[str, Any]:
        return {
            "pair_id": "fx03",
            "rung": rung,
            "run": 1,
            "metric": metric,
            "harness_verdict": True,
            "reviewer_agrees": agrees,
            "note": "test",
        }

    calibration = {
        "seed": 42,
        "verdicts": [
            verdict("llm-raw", "intent_dropped", False),
            verdict("llm-post-weave", "intent_dropped", False),
            verdict("weave", "intent_dropped", True),
            verdict("git", "intent_dropped", True),
            verdict("mergiraf", "intent_dropped", False),
            verdict("llm-raw", "human_equivalent", True),
        ],
    }
    (fx.results / "calibration.json").write_text(json.dumps(calibration, indent=2) + "\n")
    out = tmp_path / "RESULTS.md"
    fx.ladder("report", "--out", str(out))
    summary = read_json(fx.results / "summary.json")

    split = summary["calibration_agreement"]
    rate = split["intent_dropped"]["llm"]
    assert (rate["numerator"], rate["denominator"]) == (0, 2)
    rate = split["intent_dropped"]["structural"]
    assert (rate["numerator"], rate["denominator"]) == (2, 3)
    rate = split["human_equivalent"]["llm"]
    assert (rate["numerator"], rate["denominator"]) == (1, 1)
    assert "structural" not in split["human_equivalent"]

    claim_b = summary["verdicts"]["B"]
    assert "calibration" in claim_b.lower() and "0/2" in claim_b
    report = out.read_text()
    calibration_section = report.split("## Calibration")[1].split("\n## ")[0]
    assert "LLM" in calibration_section and "structural" in calibration_section
