"""The `ladder rung trap` command, registered in the rung sub-app."""

import typer
from rich.console import Console
from rich.markup import escape

from ladder.cli_support import PairArgument, load_pair, refused
from ladder.context import layout_from
from ladder.refusal import RefusedError
from ladder.trap import install_trap


def trap_command(ctx: typer.Context, pair_id: PairArgument) -> None:
    """Install a trap scenario's planted resolution as the output of the trap rung."""
    layout = layout_from(ctx)
    _, pair = load_pair(layout, pair_id)
    try:
        target = install_trap(layout, pair)
    except RefusedError as error:
        raise refused(error) from error
    Console(soft_wrap=True, highlight=False).print(
        f"Installed the planted resolution of {pair_id} at {escape(str(target))}"
    )
