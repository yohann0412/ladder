"""Audit a finished resolver run and ingest its output as the run's record."""

from datetime import UTC, datetime
from pathlib import Path

from ladder.audit import audit_transcript
from ladder.ingest import ingest_output
from ladder.jsonio import read_optional, write_record
from ladder.layout import Layout
from ladder.manifest import TaskManifest, manifest_changes, manifest_path
from ladder.refusal import RefusedError
from ladder.resolver_records import read_task, run_exists, run_label, run_name
from ladder.schemas import LlmRung, ResolverFailure, ResolverRun
from ladder.transcript import Transcript, TranscriptError, read_transcript


def finalize_run(
    layout: Layout, pair_id: str, rung: LlmRung, run: int, transcript_path: Path | None
) -> ResolverRun:
    """Write the run record: audit the transcript and task directory, then validate the output."""
    label = run_label(rung, run)
    if run_exists(layout, pair_id, rung, run):
        raise RefusedError(f"{pair_id} {label} is already finalized; runs never repeat")
    task = read_task(layout, pair_id, rung, run)
    if task is None:
        raise RefusedError(f"{pair_id} {label} was never prepared; run `ladder resolve prepare`")
    if task.status != "pending":
        raise RefusedError(f"{pair_id} {label} has status {task.status}, so no subagent ran")
    impossible: list[str] = []
    transcript: Transcript | None = None
    if transcript_path is None:
        impossible.append("audit impossible: no transcript was given")
    else:
        try:
            transcript = read_transcript(transcript_path)
        except TranscriptError as error:
            impossible.append(f"audit impossible: {error}")
    manifest = read_optional(manifest_path(layout, pair_id, rung, run), TaskManifest)
    if manifest is None:
        impossible.append("audit impossible: the task manifest is missing")
    violations = audit_transcript(transcript, task) if transcript is not None else []
    violations += manifest_changes(manifest) if manifest is not None else []
    ingested = ingest_output(Path(task.output_dir), task.files)
    failure: ResolverFailure | None = ingested.failure
    if impossible:
        failure = "audit_impossible"
    elif violations:
        failure = "protocol_violation"
    record = ResolverRun(
        pair_id=pair_id,
        rung=rung,
        run=run,
        status="ok" if failure is None else "failed",
        failure=failure,
        violations=[*impossible, *violations, *ingested.problems],
        duration_ms=transcript.duration_ms if transcript is not None else None,
        tokens=transcript.tokens if transcript is not None else None,
        tool_calls=len(transcript.tool_calls) if transcript is not None else 0,
        files=ingested.files,
        finalized_at=datetime.now(UTC),
    )
    write_record(layout.result_file(pair_id, run_name(rung, run)), record)
    return record
