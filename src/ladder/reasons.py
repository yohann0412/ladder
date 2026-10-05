"""Name why a suite could not run, from the setup steps and the output they left."""

import re
from dataclasses import dataclass

from ladder.adapters.base import INSTALL_CAP_S, TEST_CAP_S
from ladder.diskfloor import FREE_DISK
from ladder.procrun import StepResult
from ladder.schemas import TestOutcome, UnrunnableReason

LOCAL_HOST = r"(?:localhost|127\.0\.0\.1|0\.0\.0\.0|\[?::1\]?)"
SERVICE_PORT = r"(?:5432|3306|6379|27017|9200|9300|5672|11211|9092|2181|8086|4566|1433|1521)"
NEEDS_SERVICES = re.compile(
    rf"(?:connection refused|econnrefused|could not connect|error 111 connecting|"
    rf"connect: connection refused|failed to connect)[^\n]{{0,160}}{LOCAL_HOST}"
    rf"|{LOCAL_HOST}[^\n]{{0,80}}(?:connection refused|econnrefused)"
    rf"|{LOCAL_HOST}:{SERVICE_PORT}\b"
    r"|cannot connect to the docker daemon|is the docker daemon running"
    r"|could not find a valid docker environment|docker: (?:command )?not found"
    r"|testcontainers",
    re.IGNORECASE,
)
NEEDS_SECRETS = re.compile(
    r"\b[A-Z][A-Z0-9_]*(?:API_KEY|_TOKEN|_SECRET|SECRET_KEY|ACCESS_KEY|PRIVATE_KEY|CREDENTIALS)"
    r"\b[^\n]{0,80}(?:not set|undefined|missing|is required|must be set|not found|empty)"
    r"|(?i:(?:missing|no|set the|provide an?|requires? an?)\s+(?:[a-z]+ )?"
    r"(?:api[ _-]?key|access token|secret key|credentials)\b)"
    r"|KeyError: '[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET)[A-Z0-9_]*'",
)
NO_TESTS = re.compile(r"no tests (?:ran|found|collected)|no test files|0 tests", re.IGNORECASE)
TAIL_CHARS = 600


@dataclass(frozen=True)
class AttemptTrace:
    """What one setup attempt ran and the suite outcome it reached, if any."""

    steps: list[StepResult]
    outcome: TestOutcome | None


def unrunnable_reason(attempts: list[AttemptTrace]) -> tuple[UnrunnableReason, str]:
    """Return the reason category and a short detail for attempts that never passed the suite."""
    steps = [step for attempt in attempts for step in attempt.steps]
    outcomes = [attempt.outcome for attempt in attempts if attempt.outcome is not None]
    text = "\n".join(step.output() for step in steps)
    return _limits(steps, outcomes) or _environment(text) or _suite(steps, outcomes)


Reason = tuple[UnrunnableReason, str]


def _limits(steps: list[StepResult], outcomes: list[TestOutcome]) -> Reason | None:
    timed_out = next((step for step in steps if step.timed_out), None)
    if timed_out is not None:
        return "exceeds_cap", f"{timed_out.name} exceeded the {INSTALL_CAP_S} s install cap"
    starved = next((step for step in steps if step.disk_floor), None)
    if starved is not None:
        return "exceeds_cap", starved.summary()
    capped = next((result for result in outcomes if result.status == "capped"), None)
    if capped is not None and FREE_DISK in capped.detail:
        return "exceeds_cap", capped.detail
    if capped is not None:
        return "exceeds_cap", f"suite exceeded the {TEST_CAP_S} s cap"
    missing = next((step for step in steps if step.missing), None)
    return ("missing_toolchain", missing.summary()) if missing is not None else None


def _environment(text: str) -> Reason | None:
    if match := NEEDS_SERVICES.search(text):
        return "needs_services", f"output mentions a service: {match.group(0).strip()}"
    if match := NEEDS_SECRETS.search(text):
        return "needs_secrets", f"output mentions a secret: {match.group(0).strip()}"
    return None


def _suite(steps: list[StepResult], outcomes: list[TestOutcome]) -> Reason:
    if not outcomes:
        failing = next(step for step in reversed(steps) if not step.ok)
        if failing.name == "venv":
            return "missing_toolchain", f"no Python interpreter for the project: {_tail(failing)}"
        return "build_fails", f"{failing.summary()}: {_tail(failing)}"
    result = outcomes[0]
    if result.status == "failed" and result.passed == 0 and result.failed == 0:
        return "build_fails", f"suite does not load at base: {result.errors} errors"
    if result.status == "failed":
        return "other", f"suite fails at base: {result.failed} failed, {result.errors} errors"
    if NO_TESTS.search(result.detail):
        return "other", "no tests found at base"
    return "build_fails", f"test runner produced no results at base: {result.detail[:TAIL_CHARS]}"


def _tail(step: StepResult) -> str:
    lines = [line for line in step.output().strip().splitlines() if line.strip()]
    return " | ".join(lines[-6:])[-TAIL_CHARS:]
