"""Report sections about the LLM rungs, Claim C and calibration."""

from collections import Counter

from ladder.agreement import RunAgreement
from ladder.collect import PairRecords
from ladder.failure_causes import CUT_TRANSCRIPT, OWN_OUTPUT_READS
from ladder.md import section, table
from ladder.ratefmt import cell
from ladder.schemas import CalibrationRecord, Summary
from ladder.stats import share

SETTLED_TASKS = frozenset({"input_cap", "identical_input"})


def _unfinished_runs(pairs: list[PairRecords]) -> int:
    return sum(
        1
        for pair in pairs
        if pair.plan is not None
        for planned in pair.plan.runs
        if (key := (planned.rung, planned.run)) not in pair.runs
        and not (key in pair.tasks and pair.tasks[key].status in SETTLED_TASKS)
    )


def llm_failures_section(summary: Summary, pairs: list[PairRecords]) -> str:
    """Return failed resolver runs by finer cause and the planned runs that never finished."""
    causes = table(["cause", "runs"], [list(item) for item in summary.llm_failure_causes.items()])
    split = (
        "Protocol violations and impossible audits are split as D20 and D21 ask: "
        f"`{OWN_OUTPUT_READS}` when every violation is a Read, Grep or Glob outside the task "
        "directory whose path lies inside the run's own output directory; "
        f"`{CUT_TRANSCRIPT}` when a transcript line is unparseable with `EOF while parsing`, "
        "which is what a transcript truncated mid-line looks like. A pair with a run that failed "
        "for either cause counts as human-equivalent in the Claim A best-case bound."
    )
    unfinished = (
        "Planned resolver runs with no finalized record (not counting input-capped tasks and "
        f"post-weave tasks that reused the raw run): {_unfinished_runs(pairs)}."
    )
    return section("LLM failures", causes, split, unfinished)


def variance_section(summary: Summary, agreements: list[RunAgreement]) -> str:
    """Return the run-1 versus run-2 agreement of llm-raw and every pair's differing files."""
    rows = [
        [item.pair_id, "yes" if item.agrees else "no", ", ".join(item.differing) or "-"]
        for item in agreements
    ]
    return section(
        "Resolver variance",
        "Pairs where llm-raw runs 1 and 2 both finished ok; agreement means every conflicted "
        "file is AST-equivalent between the runs (deleted in both counts as equivalent). "
        f"Agreement: {cell(summary.resolver_agreement)}.",
        table(["pair", "agree", "differing files"], rows),
    )


def claim_c_section(summary: Summary, pairs: list[PairRecords]) -> str:
    """Return the Claim C rate, exclusions, and every positive pair with tests and files."""
    records = [pair.claim_c for pair in pairs if pair.claim_c is not None]
    excluded = Counter(
        record.excluded_reason for record in records if record.excluded_reason is not None
    )
    positives = [
        [
            record.pair_id,
            ", ".join(record.merge.failing_tests) or "-",
            ", ".join(record.files_a) or "-",
            ", ".join(record.files_b) or "-",
        ]
        for record in records
        if record.fails_together
    ]
    return section(
        "Claim C: passes alone, fails together",
        f"Fails together: {cell(summary.claim_c_fails_together)}, over Claim C records with a "
        f"decided outcome ({len(records)} records in all).",
        table(["excluded because", "pairs"], [list(item) for item in sorted(excluded.items())]),
        "### Positive pairs\n\n"
        + table(
            ["pair", "failing tests at the merge", "files A touched", "files B touched"], positives
        ),
    )


def calibration_section(record: CalibrationRecord | None) -> str:
    """Return reviewer agreement per calibrated metric, or `not run`."""
    if record is None:
        return section("Calibration", "Calibration: not run.")
    metrics = sorted({verdict.metric for verdict in record.verdicts})
    rates = table(
        ["metric", "reviewer agrees"],
        [
            [
                metric,
                cell(
                    share(
                        [v for v in record.verdicts if v.metric == metric],
                        lambda verdict: verdict.reviewer_agrees,
                    )
                ),
            ]
            for metric in metrics
        ],
    )
    disagreements = table(
        ["pair", "rung", "run", "metric", "harness verdict", "note"],
        [
            [v.pair_id, v.rung, v.run, v.metric, "yes" if v.harness_verdict else "no", v.note]
            for v in record.verdicts
            if not v.reviewer_agrees
        ],
    )
    return section(
        "Calibration",
        f"Seed {record.seed}, {len(record.verdicts)} verdicts read.",
        rates,
        "### Disagreements\n\n" + disagreements,
    )
