"""Carry the experiment layout from the top-level CLI options to every command."""

from typing import cast

import typer

from ladder.layout import Layout


def layout_from(ctx: typer.Context) -> Layout:
    """Return the layout the top-level callback stored on the CLI context."""
    root = ctx.find_root()
    return cast(Layout, root.obj)
