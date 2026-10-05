"""Render a workspace's leak checks."""

from pathlib import Path

from rich.console import Console
from rich.markup import escape

from ladder.wsverify import Verification


def render_checks(console: Console, path: Path, verification: Verification) -> None:
    """Print every leak check of a workspace with its outcome and what it saw."""
    console.print(f"Workspace {escape(str(path))}", soft_wrap=True)
    for check in verification.checks:
        outcome = "[green]pass[/green]" if check.passed else "[bold red]FAIL[/bold red]"
        console.print(
            f"  {outcome} {check.name}: {escape(check.detail)}", soft_wrap=True, highlight=False
        )
    verdict = "passed" if verification.passed else "[bold red]failed[/bold red]"
    console.print(f"Verification {verdict}")
