"""Helpers the resolver, trap and truth commands share: loading a pair and reporting refusals."""

from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape

from ladder.jsonio import read_record
from ladder.layout import Layout
from ladder.pairselect import UnknownPairError, find_pair
from ladder.schemas import Pair, PairSet

PairArgument = Annotated[str, typer.Argument(help="Pair id.")]


def load_pair(layout: Layout, pair_id: str) -> tuple[PairSet, Pair]:
    """Return pairs.json and the pair with this id; a usage error when there is none."""
    pair_set = read_record(layout.pairs_file, PairSet)
    try:
        return pair_set, find_pair(pair_set, pair_id)
    except UnknownPairError as error:
        raise typer.BadParameter(str(error)) from error


def refused(error: Exception) -> typer.Exit:
    """Print why a command refused to act and return the exit to raise."""
    Console(stderr=True, soft_wrap=True, highlight=False).print(f"refused: {escape(str(error))}")
    return typer.Exit(1)
