"""Read pass, fail, error and skip counts from test runners' machine-readable reports."""

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ValidationError

from ladder.jsonlines import json_lines

CARGO_TEST_LINE = re.compile(r"^test (?P<name>.+?) \.\.\. (?P<result>ok|FAILED|ignored)\b", re.M)
CARGO_TARGET = re.compile(
    r"^\s+(?:Running (?:unittests )?(?P<target>\S+)|Doc-tests (?P<doc>\S+))", re.M
)
CARGO_BUILD_ERROR = re.compile(r"^error(?:\[E\d+\]: |: could not compile)", re.M)
MOCHA_JSON_START = '{\n  "stats"'


@dataclass(frozen=True)
class Counts:
    """Test counts of one run and the ids of every failing or erroring test."""

    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    failing: list[str] = field(default_factory=list[str])

    @property
    def total(self) -> int:
        """Return the number of reported test cases."""
        return self.passed + self.failed + self.errors + self.skipped


def parse_junit(report: Path) -> Counts | None:
    """Read a pytest JUnit XML report written with junit_family=xunit1."""
    if not report.exists():
        return None
    try:
        root = ET.parse(report).getroot()
    except ET.ParseError:
        return None
    passed = failed = errors = skipped = 0
    failing: list[str] = []
    for case in root.iter("testcase"):
        test_id = _junit_id(case)
        if case.find("failure") is not None:
            failed += 1
            failing.append(test_id)
        elif case.find("error") is not None:
            errors += 1
            failing.append(test_id)
        elif case.find("skipped") is not None:
            skipped += 1
        else:
            passed += 1
    return Counts(passed, failed, errors, skipped, failing)


def _junit_id(case: ET.Element) -> str:
    name = case.get("name", "")
    classname = case.get("classname", "")
    file = case.get("file")
    if not file:
        return f"{classname}::{name}" if classname else name
    module = file.removesuffix(".py").replace("/", ".")
    rest = classname.removeprefix(module).lstrip(".")
    return "::".join(part for part in (file, rest, name) if part)


class _JestAssertion(BaseModel):
    fullName: str = ""
    title: str = ""
    status: str


class _JestFile(BaseModel):
    name: str
    status: str = ""
    message: str = ""
    assertionResults: list[_JestAssertion] = []


class _JestReport(BaseModel):
    testResults: list[_JestFile] = []


def parse_jest_json(report: Path, tree: Path) -> Counts | None:
    """Read a jest --json or vitest --reporter=json report."""
    if not report.exists():
        return None
    try:
        data = _JestReport.model_validate_json(report.read_bytes())
    except ValidationError:
        return None
    passed = failed = errors = skipped = 0
    failing: list[str] = []
    for test_file in data.testResults:
        path = _relative(test_file.name, tree)
        if test_file.status == "failed" and not test_file.assertionResults:
            errors += 1
            failing.append(path)
        for result in test_file.assertionResults:
            if result.status == "passed":
                passed += 1
            elif result.status == "failed":
                failed += 1
                failing.append(f"{path}::{result.fullName or result.title}")
            else:
                skipped += 1
    return Counts(passed, failed, errors, skipped, failing)


class _MochaTest(BaseModel):
    fullTitle: str = ""
    file: str | None = None


class _MochaReport(BaseModel):
    passes: list[_MochaTest] = []
    failures: list[_MochaTest] = []
    pending: list[_MochaTest] = []


def parse_mocha_json(report: Path, log_text: str, tree: Path) -> Counts | None:
    """Read a mocha json report from its output file, or from the log for older mocha."""
    if report.exists():
        raw = report.read_text(encoding="utf-8", errors="replace")
    elif MOCHA_JSON_START in log_text:
        raw = log_text[log_text.index(MOCHA_JSON_START) :]
    else:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(raw)
        data = _MochaReport.model_validate(obj)
    except (ValueError, ValidationError):
        return None
    failing = [
        f"{_relative(test.file, tree)}::{test.fullTitle}" if test.file else test.fullTitle
        for test in data.failures
    ]
    return Counts(len(data.passes), len(data.failures), 0, len(data.pending), failing)


class _GoEvent(BaseModel):
    Action: str
    Package: str = ""
    Test: str = ""


def parse_go_json(log_text: str) -> Counts | None:
    """Read the event stream of go test -json; a package that fails without a test is an error."""
    events: list[_GoEvent] = []
    for line in json_lines(log_text):
        if not line.startswith("{"):
            continue
        try:
            events.append(_GoEvent.model_validate_json(line))
        except ValidationError:
            continue
    if not events:
        return None
    outcomes: dict[tuple[str, str], str] = {}
    failed_packages: list[str] = []
    for event in events:
        if event.Action not in ("pass", "fail", "skip"):
            continue
        if event.Test:
            outcomes[(event.Package, event.Test)] = event.Action
        elif event.Action == "fail":
            failed_packages.append(event.Package)
    failing = [f"{pkg}::{test}" for (pkg, test), action in outcomes.items() if action == "fail"]
    packages_with_failing_tests = {pkg for (pkg, _), action in outcomes.items() if action == "fail"}
    broken = [pkg for pkg in failed_packages if pkg not in packages_with_failing_tests]
    actions = list(outcomes.values())
    return Counts(
        passed=actions.count("pass"),
        failed=actions.count("fail"),
        errors=len(broken),
        skipped=actions.count("skip"),
        failing=failing + broken,
    )


def parse_cargo_text(log_text: str) -> Counts | None:
    """Read the per-test lines cargo test prints; a compile error is one error."""
    passed = failed = skipped = 0
    failing: list[str] = []
    marks = [
        (m.start(), m.group("target") or f"doc-tests {m.group('doc')}")
        for m in CARGO_TARGET.finditer(log_text)
    ]
    for match in CARGO_TEST_LINE.finditer(log_text):
        target = next((t for start, t in reversed(marks) if start < match.start()), "")
        result = match.group("result")
        if result == "ok":
            passed += 1
        elif result == "FAILED":
            failed += 1
            failing.append(f"{target}::{match.group('name')}" if target else match.group("name"))
        else:
            skipped += 1
    errors = 1 if CARGO_BUILD_ERROR.search(log_text) else 0
    if passed + failed + skipped + errors == 0:
        return None
    return Counts(passed, failed, errors, skipped, failing + (["build"] if errors else []))


def _relative(path: str, tree: Path) -> str:
    candidate = Path(path)
    if candidate.is_absolute() and candidate.is_relative_to(tree):
        return candidate.relative_to(tree).as_posix()
    return path
