"""Python projects (pip, uv or poetry): a uv virtual environment and pytest."""

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ladder.adapters.base import Site, Step, Strategy, SuiteCommand, find_file, run_steps
from ladder.procrun import Runner, StepResult, tool_env
from ladder.testreports import Counts, parse_junit

TEST_EXTRAS = frozenset({"test", "tests", "testing", "dev", "develop", "development"})
PYTEST_MARKERS = ("pytest.ini", "conftest.py")
REQUIREMENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(\[[^\]]*\])?")
STANDARD = Strategy("standard", None)
NON_EDITABLE = Strategy(
    "non-editable", "installed the project as a regular package without test or dev extras"
)
UNPINNED = Strategy("unpinned", "ignored the version pins in the requirement files")


@dataclass(frozen=True)
class PythonAdapter:
    """A Python project and how to install it into a fresh uv virtual environment."""

    package_manager: str
    has_project: bool
    installable: bool
    dependencies: list[str]
    extras: list[str]
    groups: list[str]
    poetry_groups: list[str]
    requirement_files: list[str]
    has_tests: bool
    language = "python"
    test_runner = "pytest"
    toolchain = "uv"

    def strategies(self) -> tuple[Strategy, Strategy]:
        """Return the standard install and its fallback."""
        return STANDARD, NON_EDITABLE if self.has_project else UNPINNED

    def env_present(self, site: Site) -> bool:
        """Return True when the site's virtual environment exists."""
        return _python(site).exists()

    def install(self, runner: Runner, site: Site, strategy: Strategy) -> list[StepResult]:
        """Create the virtual environment and install the project, its test deps and pytest."""
        venv = Step("venv", ["uv", "venv", "--quiet", str(site.env)], site.tree)
        return run_steps(runner, [venv, *self._install_steps(site, strategy)])

    def attach(
        self, runner: Runner, base: Site, tree: Path, strategy: Strategy
    ) -> tuple[Site, list[StepResult]]:
        """Point the base environment's install of the project at another tree."""
        site = Site(tree, base.env)
        pip = _pip(site)
        if strategy == STANDARD and self.installable:
            step = Step("attach", [*pip, "--no-deps", "-e", str(tree)], tree)
        elif strategy == NON_EDITABLE:
            step = Step("attach", [*pip, "--no-deps", "--reinstall", str(tree)], tree)
        else:
            return site, []
        return site, run_steps(runner, [step])

    def suite(
        self, site: Site, strategy: Strategy, report: Path, only: list[str] | None
    ) -> SuiteCommand:
        """Return the pytest command writing a JUnit report."""
        argv = [
            str(_python(site)),
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-o",
            "junit_family=xunit1",
            f"--junitxml={report}",
            *(only or []),
        ]
        return SuiteCommand(argv, {**_venv_env(site), "PYTHONDONTWRITEBYTECODE": "1"})

    def parse(self, site: Site, report: Path, log_text: str) -> Counts | None:
        """Read pytest's JUnit report."""
        return parse_junit(report)

    def _install_steps(self, site: Site, strategy: Strategy) -> list[Step]:
        pip = _pip(site)
        requirements = [arg for name in self.requirement_files for arg in ("-r", name)]
        tree = site.tree
        if strategy == NON_EDITABLE:
            return [Step("install", [*pip, str(tree), *requirements, "pytest"], tree)]
        if strategy == UNPINNED:
            return [Step("install", [*pip, *self._unpinned(tree), "pytest"], tree)]
        pytest = Step("pytest", [*pip, *requirements, "pytest"], tree)
        if self.package_manager == "poetry":
            groups = ["--with", ",".join(self.poetry_groups)] if self.poetry_groups else []
            env = {**_venv_env(site), "POETRY_VIRTUALENVS_CREATE": "false"}
            install = Step("install", ["poetry", "install", "--no-interaction", *groups], tree, env)
            return [install, pytest]
        if self.package_manager == "uv":
            flags = [*_flags("--extra", self.extras), *_flags("--group", self.groups)]
            env = {"UV_PROJECT_ENVIRONMENT": str(site.env)}
            return [Step("install", ["uv", "sync", "--frozen", *flags], tree, env), pytest]
        if self.installable:
            spec = f"{tree}[{','.join(self.extras)}]" if self.extras else str(tree)
            project = ["-e", spec]
        else:
            project = self.dependencies
        groups = _flags("--group", self.groups)
        return [Step("install", [*pip, *project, *groups, *requirements, "pytest"], tree)]

    def _unpinned(self, tree: Path) -> list[str]:
        names: list[str] = []
        for file_name in self.requirement_files:
            text = (tree / file_name).read_text(encoding="utf-8", errors="replace")
            for raw in text.splitlines():
                line = raw.split(" #", 1)[0].strip()
                if not line or line.startswith(("#", "-")):
                    continue
                match = REQUIREMENT_NAME.match(line)
                names.append(line if "://" in line or match is None else match.group(0))
        return names


def detect(tree: Path) -> PythonAdapter | None:
    """Recognise a Python project by its pyproject.toml, setup.py, setup.cfg or requirements."""
    pyproject_file = tree / "pyproject.toml"
    setup_py = (tree / "setup.py").exists()
    requirement_files = sorted(
        path.name for path in tree.glob("*requirements*.txt") if path.is_file()
    )
    if not (
        pyproject_file.exists() or setup_py or (tree / "setup.cfg").exists() or requirement_files
    ):
        return None
    pyproject = _load_toml(pyproject_file)
    project = _table(pyproject, "project")
    poetry = _table(pyproject, "tool", "poetry")
    optional = _table(project, "optional-dependencies")
    extras = sorted(name for name in optional if name.lower() in TEST_EXTRAS)
    dependencies = _strings(project.get("dependencies"))
    for extra in extras:
        dependencies.extend(_strings(optional[extra]))
    if (tree / "uv.lock").exists():
        manager = "uv"
    elif (tree / "poetry.lock").exists() or poetry:
        manager = "poetry"
    else:
        manager = "pip"
    return PythonAdapter(
        package_manager=manager,
        has_project=bool(project) or bool(poetry) or setup_py,
        installable=setup_py or "build-system" in pyproject,
        dependencies=dependencies,
        extras=extras,
        groups=sorted(
            name for name in _table(pyproject, "dependency-groups") if name in TEST_EXTRAS
        ),
        poetry_groups=sorted(name for name in _table(poetry, "group") if name in TEST_EXTRAS),
        requirement_files=requirement_files,
        has_tests=_has_tests(tree, pyproject),
    )


def _has_tests(tree: Path, pyproject: dict[str, Any]) -> bool:
    if _table(pyproject, "tool", "pytest") or any((tree / n).exists() for n in PYTEST_MARKERS):
        return True
    return find_file(
        tree,
        lambda name: (
            name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py"))
        ),
    )


def _python(site: Site) -> Path:
    return site.env / "bin" / "python"


def _pip(site: Site) -> list[str]:
    return ["uv", "pip", "install", "--python", str(_python(site))]


def _venv_env(site: Site) -> dict[str, str]:
    path = f"{site.env / 'bin'}{os.pathsep}{tool_env()['PATH']}"
    return {"VIRTUAL_ENV": str(site.env), "PATH": path}


def _flags(flag: str, values: list[str]) -> list[str]:
    return [arg for value in values for arg in (flag, value)]


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    except tomllib.TOMLDecodeError:
        return {}


def _table(data: dict[str, Any], *keys: str) -> dict[str, Any]:
    current: object = data
    for key in keys:
        if not isinstance(current, dict):
            return {}
        current = cast(dict[str, object], current).get(key)
    return cast(dict[str, Any], current) if isinstance(current, dict) else {}


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in cast(list[object], value) if isinstance(item, str)]
