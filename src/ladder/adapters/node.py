"""Node projects (npm, pnpm or yarn) tested with jest, vitest or mocha."""

import json
import os
import re
import shlex
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ladder.adapters.base import Site, Step, Strategy, SuiteCommand, Unsupported, run_steps
from ladder.procrun import Runner, StepResult
from ladder.runtime import remove_tree
from ladder.testreports import Counts, parse_jest_json, parse_mocha_json

RUNNERS = ("vitest", "jest", "mocha")
RUNNER_MENTION = re.compile(r"\b(vitest|jest|mocha)\b")
RUNNER_SCRIPT = re.compile(r"(^|/)(vitest|jest|_?mocha)(\.[cm]?js)?$")
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
SHELL_OPERATORS = ("&&", "||", "|", ";", "&")
DROPPED_FLAGS = {
    "jest": {"--watch", "--watchAll", "--coverage", "--json"},
    "vitest": {"--watch", "--coverage", "--ui"},
    "mocha": {"--watch", "-w"},
}
DROPPED_WITH_VALUE = {"--reporter", "-R", "--reporter-option", "--reporter-options", "-O"}
VITEST_SUBCOMMANDS = {"run", "watch", "dev"}
TOOL_ENV = {
    "CI": "true",
    "HUSKY": "0",
    "npm_config_audit": "false",
    "npm_config_fund": "false",
    "npm_config_update_notifier": "false",
    "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0",
    "COREPACK_ENABLE_STRICT": "0",
}
STANDARD = Strategy("standard", None)
FALLBACKS = {
    "npm": Strategy(
        "legacy-peer-deps", "npm install --legacy-peer-deps instead of a clean install"
    ),
    "pnpm": Strategy("unfrozen", "pnpm install without --frozen-lockfile"),
    "yarn": Strategy("unfrozen", "yarn install with the lockfile unfrozen and engines ignored"),
}


@dataclass(frozen=True)
class NodeAdapter:
    """A Node project, its package manager and the test runner its suite uses."""

    package_manager: str
    pinned_manager: bool
    yarn_berry: bool
    has_lockfile: bool
    test_runner: str
    runner_args: list[str]
    runner_env: dict[str, str]
    language = "node"
    toolchain = "node"
    has_tests = True

    def strategies(self) -> tuple[Strategy, Strategy]:
        """Return the frozen-lockfile install and its fallback."""
        return STANDARD, FALLBACKS[self.package_manager]

    def env_present(self, site: Site) -> bool:
        """Return True when the tree has its node_modules."""
        return (site.tree / "node_modules").is_dir()

    def install(self, runner: Runner, site: Site, strategy: Strategy) -> list[StepResult]:
        """Install the dependencies into the tree's node_modules."""
        env = dict(TOOL_ENV)
        manager = self._manager()
        if self.package_manager == "npm":
            if strategy == STANDARD:
                args = ["ci"] if self.has_lockfile else ["install"]
            else:
                args = ["install", "--legacy-peer-deps"]
        elif self.package_manager == "pnpm":
            frozen = "--frozen-lockfile" if strategy == STANDARD else "--no-frozen-lockfile"
            args = ["install", frozen]
        elif self.yarn_berry:
            args = ["install", "--immutable"] if strategy == STANDARD else ["install"]
            if strategy != STANDARD:
                env["YARN_ENABLE_IMMUTABLE_INSTALLS"] = "false"
        elif strategy == STANDARD:
            args = ["install", "--frozen-lockfile", "--non-interactive"]
        else:
            args = ["install", "--non-interactive", "--ignore-engines"]
        return run_steps(runner, [Step("install", [*manager, *args], site.tree, env)])

    def attach(
        self, runner: Runner, base: Site, tree: Path, strategy: Strategy
    ) -> tuple[Site, list[StepResult]]:
        """Hard-link every node_modules directory of the base tree into another tree."""
        if tree.resolve() == base.tree.resolve():
            return base, []
        for root, dirnames, _ in os.walk(base.tree):
            if "node_modules" in dirnames:
                source = Path(root) / "node_modules"
                target = tree / source.relative_to(base.tree)
                if target.parent.is_dir():
                    remove_tree(target)
                    shutil.copytree(source, target, symlinks=True, copy_function=os.link)
            dirnames[:] = [name for name in dirnames if name not in ("node_modules", ".git")]
        return Site(tree, base.env), []

    def suite(
        self, site: Site, strategy: Strategy, report: Path, only: list[str] | None
    ) -> SuiteCommand:
        """Return the runner command writing a JSON report."""
        binary = str(site.tree / "node_modules" / ".bin" / self.test_runner)
        files = only or []
        env = {**TOOL_ENV, **self.runner_env}
        if self.test_runner == "jest":
            narrow = ["--runTestsByPath", *files] if files else []
            argv = [
                binary,
                *self.runner_args,
                "--ci",
                "--coverage=false",
                "--json",
                f"--outputFile={report}",
                *narrow,
            ]
        elif self.test_runner == "vitest":
            argv = [
                binary,
                "run",
                *self.runner_args,
                "--coverage.enabled=false",
                "--reporter=json",
                f"--outputFile={report}",
                *files,
            ]
        else:
            output = ["--reporter", "json", "--reporter-option", f"output={report}"]
            argv = [binary, *self.runner_args, *output, *files]
        note = "spec arguments of the test script still apply" if files and self.runner_args else ""
        return SuiteCommand(argv, env, note if self.test_runner == "mocha" else "")

    def parse(self, site: Site, report: Path, log_text: str) -> Counts | None:
        """Read the runner's JSON report."""
        if self.test_runner == "mocha":
            return parse_mocha_json(report, log_text, site.tree)
        return parse_jest_json(report, site.tree)

    def _manager(self) -> list[str]:
        if self.package_manager == "npm":
            return ["npm"]
        if self.pinned_manager or shutil.which(self.package_manager) is None:
            return ["corepack", self.package_manager]
        return [self.package_manager]


def detect(tree: Path) -> NodeAdapter | Unsupported | None:
    """Recognise a Node project by its package.json and find its test runner."""
    manifest = tree / "package.json"
    if not manifest.exists():
        return None
    try:
        package = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        package = {}
    data = cast(dict[str, Any], package) if isinstance(package, dict) else {}
    manager, version = _manager_field(data)
    if (tree / "pnpm-lock.yaml").exists():
        package_manager = "pnpm"
    elif (tree / "yarn.lock").exists():
        package_manager = "yarn"
    elif (tree / "package-lock.json").exists() or (tree / "npm-shrinkwrap.json").exists():
        package_manager = "npm"
    else:
        package_manager = manager if manager in FALLBACKS else "npm"
    pinned = manager == package_manager
    major = version.split(".", 1)[0]
    berry = package_manager == "yarn" and (
        (tree / ".yarnrc.yml").exists() or (pinned and major.isdigit() and int(major) >= 2)
    )
    lockfiles = ("pnpm-lock.yaml", "yarn.lock", "package-lock.json", "npm-shrinkwrap.json")
    script = _dict(data.get("scripts")).get("test")
    runner, args, env = _from_script(script) if isinstance(script, str) else (None, [], {})
    if runner is None:
        dependencies = {**_dict(data.get("dependencies")), **_dict(data.get("devDependencies"))}
        runner = next((name for name in RUNNERS if name in dependencies), None)
    if runner is None:
        detail = "no jest, vitest or mocha test runner in package.json"
        return Unsupported("node", package_manager, None, "other", detail)
    return NodeAdapter(
        package_manager=package_manager,
        pinned_manager=pinned,
        yarn_berry=berry,
        has_lockfile=any((tree / name).exists() for name in lockfiles),
        test_runner=runner,
        runner_args=args,
        runner_env=env,
    )


def _from_script(script: str) -> tuple[str | None, list[str], dict[str, str]]:
    mention = RUNNER_MENTION.search(script)
    mentioned = mention.group(1) if mention else None
    try:
        tokens = shlex.split(script)
    except ValueError:
        return mentioned, [], {}
    if any(token in SHELL_OPERATORS or token.endswith(";") for token in tokens):
        return mentioned, [], {}
    if tokens[:1] == ["cross-env"]:
        tokens = tokens[1:]
    env: dict[str, str] = {}
    while tokens and ENV_ASSIGNMENT.match(tokens[0]):
        key, value = tokens[0].split("=", 1)
        env[key] = value
        tokens = tokens[1:]
    if tokens[:1] == ["node"]:
        script_at = next((i for i, t in enumerate(tokens) if RUNNER_SCRIPT.search(t)), None)
        if script_at is None:
            return mentioned, [], {}
        env["NODE_OPTIONS"] = " ".join(tokens[1:script_at])
        tokens = tokens[script_at:]
    match = RUNNER_SCRIPT.search(tokens[0]) if tokens else None
    if match is None:
        return mentioned, [], {}
    runner = match.group(2).lstrip("_")
    return runner, _clean_args(runner, tokens[1:]), env


def _clean_args(runner: str, args: list[str]) -> list[str]:
    if runner == "vitest" and args[:1] and args[0] in VITEST_SUBCOMMANDS:
        args = args[1:]
    kept: list[str] = []
    skip_value = False
    for arg in args:
        if skip_value:
            skip_value = False
            continue
        flag = arg.split("=", 1)[0]
        if runner == "mocha" and flag in DROPPED_WITH_VALUE:
            skip_value = "=" not in arg
            continue
        if flag in DROPPED_FLAGS[runner] or flag == "--outputFile":
            continue
        kept.append(arg)
    return kept


def _manager_field(data: dict[str, Any]) -> tuple[str | None, str]:
    field = data.get("packageManager")
    if not isinstance(field, str) or "@" not in field:
        return None, ""
    name, version = field.split("@", 1)
    return name, version


def _dict(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}
