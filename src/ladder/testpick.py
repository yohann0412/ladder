"""Pick the test files a PR added or modified, by common test file naming conventions."""

from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from ladder.gitio import run_git

TEST_NAMES = ("test_*.py", "*_test.py", "*_test.go", "*.test.*", "*.spec.*")
TEST_DIRS = frozenset({"test", "tests", "__tests__"})
SUITE_SUFFIXES = frozenset(
    {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".go", ".rs"}
)


def is_test_file(path: str) -> bool:
    """Return whether a path is a Python, Node, Go or Rust test file by name or directory."""
    posix = PurePosixPath(path)
    if posix.suffix.lower() not in SUITE_SUFFIXES:
        return False
    in_test_dir = any(part in TEST_DIRS for part in posix.parts[:-1])
    return in_test_dir or any(fnmatch(posix.name, pattern) for pattern in TEST_NAMES)


def added_or_modified_tests(repo: Path, side: str) -> list[str]:
    """Return the test files a side added or modified relative to base, renames split."""
    args = ["diff", "--name-only", "--no-renames", "--diff-filter=AM", "-z", "base", side]
    out = run_git(args, repo).stdout.decode("utf-8", "replace")
    return sorted(path for path in out.split("\0") if path and is_test_file(path))
