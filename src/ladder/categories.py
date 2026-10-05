"""Assign a conflicted path to the replay study's file category.

The rule is the replay study's `categorize()` from its replication package
(Zenodo 10.5281/zenodo.21186464, CC-BY-4.0), so taxonomy numbers are comparable.
"""

import re

from ladder.schemas import FileCategory

MANIFEST_BASENAMES = frozenset(
    {
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "npm-shrinkwrap.json",
        "cargo.toml",
        "cargo.lock",
        "go.mod",
        "go.sum",
        "poetry.lock",
        "pipfile",
        "pipfile.lock",
        "uv.lock",
        "gemfile",
        "gemfile.lock",
        "pom.xml",
        "composer.json",
        "composer.lock",
        "pubspec.yaml",
        "pubspec.lock",
        "mix.exs",
        "mix.lock",
        "podfile",
        "podfile.lock",
        "bun.lock",
        "bun.lockb",
        "packages.lock.json",
        "gradle.lockfile",
    }
)
CONFIG_BASENAMES = frozenset(
    {
        "dockerfile",
        "makefile",
        "tsconfig.json",
        ".gitignore",
        ".dockerignore",
        ".npmrc",
        ".eslintrc",
        ".eslintrc.js",
        ".eslintrc.json",
        ".prettierrc",
        ".editorconfig",
        "vite.config.js",
        "vite.config.ts",
        "webpack.config.js",
        "rollup.config.js",
        "next.config.js",
        "next.config.mjs",
        "jest.config.js",
        "babel.config.js",
        ".env",
        ".env.example",
    }
)
SOURCE_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".jsx",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".kts",
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".h",
        ".hpp",
        ".rb",
        ".php",
        ".cs",
        ".swift",
        ".scala",
        ".m",
        ".mm",
        ".dart",
        ".ex",
        ".exs",
        ".lua",
        ".r",
        ".jl",
        ".vue",
        ".svelte",
        ".sh",
        ".bash",
        ".ps1",
        ".sql",
        ".pl",
        ".clj",
        ".hs",
        ".elm",
    }
)
DOC_EXTENSIONS = frozenset({".md", ".mdx", ".rst", ".txt", ".adoc"})
CONFIG_EXTENSIONS = frozenset(
    {".yml", ".yaml", ".json", ".toml", ".ini", ".cfg", ".conf", ".properties", ".xml", ".env"}
)


def _is_manifest(basename: str) -> bool:
    if basename in MANIFEST_BASENAMES:
        return True
    if basename.startswith("requirements") and basename.endswith(".txt"):
        return True
    if basename.endswith((".csproj", ".gemspec")):
        return True
    return re.search(r"build\.gradle(\.kts)?$", basename) is not None


def categorize(path: str) -> FileCategory:
    """Return the replay study's category for a repository path."""
    basename = path.rsplit("/", 1)[-1].lower()
    extension = "." + basename.rsplit(".", 1)[-1] if "." in basename else ""
    if _is_manifest(basename):
        return "manifest_lockfile"
    lowered = path.lower()
    if basename in CONFIG_BASENAMES or "/.github/" in "/" + lowered:
        return "config_ci"
    if extension in SOURCE_EXTENSIONS:
        return "source"
    if extension in DOC_EXTENSIONS or basename in ("license", "changelog", "readme"):
        return "docs_text"
    if extension in CONFIG_EXTENSIONS:
        return "config_ci"
    return "other"
