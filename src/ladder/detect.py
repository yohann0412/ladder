"""Detect a source tree's language, package manager and test runner."""

import shutil
from pathlib import Path

from ladder.adapters import go, node, python, rust
from ladder.adapters.base import Adapter, Unsupported

OTHER_LANGUAGES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("java", ("pom.xml",), "mvn"),
    ("java", ("build.gradle", "build.gradle.kts"), "gradle"),
    ("kotlin", ("settings.gradle.kts",), "gradle"),
    ("ruby", ("Gemfile",), "bundle"),
    ("php", ("composer.json",), "composer"),
    ("csharp", ("*.sln", "*.csproj", "*.fsproj"), "dotnet"),
    ("elixir", ("mix.exs",), "mix"),
    ("dart", ("pubspec.yaml",), "dart"),
    ("swift", ("Package.swift",), "swift"),
    ("scala", ("build.sbt",), "sbt"),
    ("deno", ("deno.json", "deno.jsonc"), "deno"),
    ("cpp", ("CMakeLists.txt",), "cmake"),
)


def detect(tree: Path) -> Adapter | Unsupported:
    """Return the adapter for the tree's suite, or why the tree cannot be run."""
    found = [python.detect(tree), node.detect(tree), go.detect(tree), rust.detect(tree)]
    adapters: list[Adapter] = [
        item for item in found if item is not None and not isinstance(item, Unsupported)
    ]
    with_tests = [adapter for adapter in adapters if adapter.has_tests]
    if with_tests:
        return with_tests[0]
    if adapters:
        return adapters[0]
    unsupported = [item for item in found if isinstance(item, Unsupported)]
    if unsupported:
        return unsupported[0]
    return _other_language(tree)


def _other_language(tree: Path) -> Unsupported:
    for language, patterns, toolchain in OTHER_LANGUAGES:
        if any(next(tree.glob(pattern), None) is not None for pattern in patterns):
            if shutil.which(toolchain) is None:
                detail = f"{language} project; {toolchain} is not installed"
                return Unsupported(language, toolchain, None, "missing_toolchain", detail)
            detail = f"{language} project; no adapter for {language} ({toolchain} is installed)"
            return Unsupported(language, toolchain, None, "other", detail)
    return Unsupported(None, None, None, "other", "no recognised project manifest")
