"""The `ladder score` command."""

from typing import Annotated

import typer
from rich.console import Console

from ladder.context import layout_from
from ladder.rungoutputs import ScoreError
from ladder.score import score_pair
from ladder.score_view import render_scores


def score(
    ctx: typer.Context,
    pair: Annotated[str, typer.Argument(help="Conflicting pair whose rung outputs are scored.")],
) -> None:
    """Score every rung output of a conflicting pair: mergeable, human-equivalent, intent, tests."""
    try:
        scores = score_pair(layout_from(ctx), pair)
    except (ScoreError, FileNotFoundError) as error:
        Console(stderr=True).print(str(error), style="red", markup=False, highlight=False)
        raise typer.Exit(1) from error
    render_scores(Console(), pair, scores)
