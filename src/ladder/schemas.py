"""Pydantic schemas for every artifact the harness reads or writes."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class Record(BaseModel):
    """Base model that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")


# ----------------------------------------------------------------------------- pairs

Stratum = Literal["same", "cross"]
PairOrigin = Literal["paper", "supplementary", "fixture"]
PaperLabel = Literal["CLEAN", "CONFLICT", "UNAVAIL_fetch", "UNAVAIL_nobase"]
HeadsKind = Literal["final", "replay"]
Side = Literal["a", "b"]


class PullRequest(Record):
    """One pull request as described by the pair sources."""

    number: int
    agent: str
    title: str
    body: str
    state: str | None
    created_at: datetime | None
    closed_at: datetime | None
    merged_at: datetime | None


class PaperRecord(Record):
    """The replay study's own row for a pair."""

    stratum: Stratum
    label: PaperLabel
    n_files: int
    files: list[str]
    types: list[str]


class SourceFile(Record):
    """A downloaded source file and its checksum."""

    name: str
    url: str
    md5: str


MergeLocator = Literal["merge_parent", "subject_time", "time_only"]
TruthLocator = Literal["absorption", "merge_parent", "subject_time", "time_only"]
ResolveStatus = Literal["ok", "fetch_failed", "no_merge_base", "unrecoverable_rebased"]
TruthStatus = Literal["located", "unlocated", "not_both_merged"]


class PrRefs(Record):
    """Commit-level facts about one PR, derived by fetching it."""

    final_head: str | None
    replay_head: str | None
    rewound_commits: int
    contaminated: bool
    merge_commit: str | None
    merge_commit_method: MergeLocator | None
    merge_time_delta_s: float | None


class PairRefs(Record):
    """Commit-level facts about a pair: heads, bases, contamination, truth commit."""

    status: ResolveStatus
    detail: str
    fetched_at: datetime
    default_branch: str | None
    final_merge_base: str | None
    final_merge_base_count: int
    replay_merge_base: str | None
    replay_merge_base_count: int
    a: PrRefs
    b: PrRefs
    truth_commit: str | None
    truth_method: TruthLocator | None
    truth_status: TruthStatus


class Pair(Record):
    """A pair of concurrent PRs in one repository; the merge is always b into a."""

    pair_id: str
    origin: PairOrigin
    stratum: Stratum
    repo: str
    clone_url: str
    a: PullRequest
    b: PullRequest
    paper: PaperRecord | None
    refs: PairRefs | None = None


class PairSet(Record):
    """The validated contents of pairs.json."""

    sources: list[SourceFile]
    pairs: list[Pair]


# ----------------------------------------------------------------------------- workspace


class WorkspaceRecord(Record):
    """A built and verified leak-proof workspace."""

    pair_id: str
    heads: HeadsKind
    path: str
    source_base: str
    source_a: str
    source_b: str
    base_commit: str
    a_commit: str
    b_commit: str
    object_count: int
    criss_cross: bool
    checks: list[str]


# ----------------------------------------------------------------------------- rungs

FileCategory = Literal["source", "config_ci", "manifest_lockfile", "docs_text", "other"]


class ConflictedFile(Record):
    """One file git could not merge."""

    path: str
    types: list[str]
    regions: int
    category: FileCategory


class GitRungResult(Record):
    """Outcome of merging b into a with git's ort strategy."""

    pair_id: str
    heads: HeadsKind
    status: Literal["clean", "conflicted", "error"]
    detail: str
    messages: list[str]
    types: list[str]
    files: list[ConflictedFile]
    merged_tree: str | None


class ResolvedFileCheck(Record):
    """Syntactic checks on one file of a rung's output."""

    path: str
    present: bool
    has_markers: bool
    language: str | None
    parses: bool | None


StructuralTool = Literal["weave", "mergiraf"]


class StructuralResult(Record):
    """Outcome of retrying the merge with a structural merge driver."""

    pair_id: str
    tool: StructuralTool
    tool_version: str
    status: Literal["resolved", "conflicted", "error"]
    detail: str
    remaining_conflicted: list[str]
    files: list[ResolvedFileCheck]
    output_dir: str


# ----------------------------------------------------------------------------- resolver

LlmRung = Literal["llm-raw", "llm-post-weave"]
ResolverFailure = Literal[
    "input_cap", "protocol_violation", "no_output", "malformed_output", "audit_impossible"
]
TaskStatus = Literal["pending", "input_cap", "identical_input"]


class ResolverTask(Record):
    """A prepared resolver task awaiting one fresh-context subagent run."""

    pair_id: str
    rung: LlmRung
    run: int
    task_dir: str
    snapshot_dir: str
    output_dir: str
    spawn_line: str
    files: list[str]
    input_bytes: int
    pr_text_flags: list[str]
    template_sha256: str
    status: TaskStatus
    identical_to: str | None
    prepared_at: datetime


class ResolvedFile(Record):
    """One conflicted path as the resolver left it."""

    path: str
    action: Literal["keep", "delete"]
    sha256: str | None
    rationale: str


class TokenUsage(Record):
    """Token counts summed over a subagent transcript."""

    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int


class ResolverRun(Record):
    """The audited, ingested result of one resolver subagent run."""

    pair_id: str
    rung: LlmRung
    run: int
    status: Literal["ok", "failed"]
    failure: ResolverFailure | None
    violations: list[str]
    duration_ms: int | None
    tokens: TokenUsage | None
    tool_calls: int
    files: list[ResolvedFile]
    finalized_at: datetime


# ----------------------------------------------------------------------------- truth


class TruthFile(Record):
    """The human resolution of one conflicted path."""

    path: str
    present: bool
    sha256: str | None


class TruthRecord(Record):
    """The human resolution of a pair and how trustworthy it is."""

    pair_id: str
    status: TruthStatus
    commit: str | None
    method: TruthLocator | None
    files: list[TruthFile]
    touched_beyond_conflict: list[str]
    outside_region_edit: list[str]
    rewrite: bool
    leak_head_equals_truth: bool
    extracted_at: datetime


# ----------------------------------------------------------------------------- tests

TestStatus = Literal["passed", "failed", "flaky", "capped", "error", "not_run"]


class TestOutcome(Record):
    """One test-suite run, after the single flaky retry."""

    status: TestStatus
    command: list[str]
    passed: int
    failed: int
    errors: int
    skipped: int
    duration_s: float
    retried: bool
    failing_tests: list[str]
    detail: str


UnrunnableReason = Literal[
    "missing_toolchain", "needs_services", "needs_secrets", "build_fails", "exceeds_cap", "other"
]


class SetupAttempt(Record):
    """One attempt to install dependencies and run the suite."""

    command: list[str]
    exit_code: int | None
    duration_s: float
    detail: str


class Runnability(Record):
    """Whether a repository's suite runs at the pair's merge base, and how."""

    pair_id: str
    commit: str
    language: str | None
    package_manager: str | None
    test_runner: str | None
    status: Literal["runnable", "runnable_with_modifications", "unrunnable"]
    reason: UnrunnableReason | None
    reason_detail: str
    modifications: list[str]
    attempts: list[SetupAttempt]
    test_count: int | None
    base_outcome: TestOutcome | None
    timeout_s: int


class ClaimCRecord(Record):
    """Suite outcomes at a, at b and at their clean merge."""

    pair_id: str
    a: TestOutcome
    b: TestOutcome
    merge: TestOutcome
    fails_together: bool | None
    excluded_reason: str | None
    files_a: list[str]
    files_b: list[str]


# ----------------------------------------------------------------------------- scoring


class FileScore(Record):
    """Per-file scores of one rung output."""

    path: str
    mode: Literal["ast", "token"]
    language: str | None
    present: bool
    has_markers: bool
    parses: bool | None
    new_duplicates: list[str]
    human_equivalent: bool | None
    human_equivalent_unordered: bool | None
    similarity: float | None


class IntentDrop(Record):
    """One change a PR made that the resolution lost."""

    path: str
    entity: str
    loser: Side
    reason: str
    loser_touched_unconflicted_files: bool


class RungScore(Record):
    """Every metric for one rung's output on one conflicting pair."""

    pair_id: str
    rung: str
    run: int
    available: bool
    unavailable_reason: str | None
    mergeable: bool
    human_equivalent: bool | None
    human_equivalent_unordered: bool | None
    intent_preserved_a: bool | None
    intent_preserved_b: bool | None
    intent_drops: list[IntentDrop]
    files: list[FileScore]
    tests_full: TestOutcome | None
    tests_a: TestOutcome | None
    tests_b: TestOutcome | None


# ----------------------------------------------------------------------------- report


class Rate(Record):
    """A proportion with its Wilson 95% interval."""

    numerator: int
    denominator: int
    pct: float | None
    ci_low: float | None
    ci_high: float | None


# ----------------------------------------------------------------------------- fixture

ExpectationBasis = Literal["design", "prediction", "observed"]


class ExpectedRung(Record):
    """What one rung must produce on one fixture scenario; None means not asserted."""

    basis: ExpectationBasis
    status: Literal["clean", "conflicted", "resolved", "absent"] | None = None
    conflicted_paths: list[str] | None = None
    types: list[str] | None = None
    parses: bool | None = None
    mergeable: bool | None = None
    human_equivalent: bool | None = None
    intent_loser: Literal["a", "b", "none"] | None = None
    tests_pass: bool | None = None


class ExpectedScenario(Record):
    """The expected outcomes table row for one fixture scenario."""

    pair_id: str
    title: str
    resolve_status: ResolveStatus
    contaminated: Literal["none", "a", "b"]
    truth_status: TruthStatus
    truth_method: TruthLocator | None
    truth_rewrite: bool | None
    rungs: dict[str, ExpectedRung]
    claim_c_fails_together: bool | None


class FixtureExpectations(Record):
    """The full expected outcomes table for the fixture."""

    scenarios: list[ExpectedScenario]


class FixturePr(Record):
    """One emulated pull request of a fixture scenario."""

    number: int
    agent: str
    title: str
    body: str
    branch: str
    head: str
    created_at: datetime
    closed_at: datetime | None
    merged_at: datetime | None


class FixtureScenario(Record):
    """One fixture scenario: two concurrent PRs from one base, and how they were merged."""

    pair_id: str
    title: str
    description: str
    stratum: Stratum
    base: str
    a: FixturePr
    b: FixturePr
    resolved_branch: str | None
    resolved: str | None
    trap_dir: str | None
    origin: str


class FixtureManifest(Record):
    """The contents of fixtures/pairs.json."""

    scenarios: list[FixtureScenario]
