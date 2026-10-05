"""Split failed resolver runs by the causes D20 and D21 single out for the Claim A bound."""

from ladder.audit import read_inside
from ladder.collect import PairRecords
from ladder.layout import Layout
from ladder.schemas import ResolverRun
from ladder.transcript import cut_off

OWN_OUTPUT_READS = "protocol_violation: own output reads only"
OTHER_VIOLATION = "protocol_violation: other"
CUT_TRANSCRIPT = "audit_impossible: transcript cut off"
OTHER_IMPOSSIBLE = "audit_impossible: other"
EXCUSED = frozenset({OWN_OUTPUT_READS, CUT_TRANSCRIPT})


def failure_cause(layout: Layout, run: ResolverRun) -> str | None:
    """Return a run's failure cause, splitting violations and impossible audits; None if ok."""
    if run.failure == "protocol_violation":
        output_dir = layout.resolution_dir(run.pair_id, run.rung, run.run).resolve()
        own = bool(run.violations) and all(read_inside(v, output_dir) for v in run.violations)
        return OWN_OUTPUT_READS if own else OTHER_VIOLATION
    if run.failure == "audit_impossible":
        return CUT_TRANSCRIPT if any(cut_off(v) for v in run.violations) else OTHER_IMPOSSIBLE
    return run.failure


def excused(layout: Layout, pair: PairRecords) -> bool:
    """Return whether any LLM run of a pair failed only for a cause of D20 or D21."""
    return any(failure_cause(layout, run) in EXCUSED for run in pair.runs.values())
