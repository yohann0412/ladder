"""Claim C acceptance: fx06 fails together, fx09 passes together, a disk floor stops a suite."""

from conftest import Experiment


def test_claim_c_runner(fx_resolved: Experiment) -> None:
    fx = fx_resolved
    for pair_id in ("fx06", "fx09"):
        fx.ladder("workspace", "build", pair_id)
        fx.ladder("rung", "git", pair_id)
        fx.ladder("runnable", pair_id)
        fx.ladder("claim-c", pair_id)

    positive = fx.result("fx06", "claim-c")
    assert positive["a"]["status"] == "passed" and positive["b"]["status"] == "passed"
    assert positive["merge"]["status"] == "failed"
    assert positive["fails_together"] is True and positive["excluded_reason"] is None
    assert positive["merge"]["failing_tests"]
    assert all("report" in t for t in positive["merge"]["failing_tests"])
    assert "textkit/report.py" in positive["files_b"]
    assert "textkit/core.py" in positive["files_a"]

    negative = fx.result("fx09", "claim-c")
    assert negative["merge"]["status"] == "passed"
    assert negative["fails_together"] is False

    conflicted = fx.ladder("claim-c", "fx01", check=False)
    assert conflicted.returncode != 0

    floor = {"LADDER_MIN_FREE_GIB": "1000000"}
    fx.ladder("runnable", "fx09", extra_env=floor)
    starved = fx.result("fx09", "runnability")
    assert starved["status"] == "unrunnable" and starved["reason"] == "exceeds_cap"
    assert "free disk" in starved["reason_detail"]
