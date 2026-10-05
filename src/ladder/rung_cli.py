"""The `ladder rung` commands: merge one pair at one rung of the ladder and record the outcome."""

from collections import Counter
from typing import Annotated, NoReturn

import typer
from rich.console import Console
from rich.text import Text

from ladder.context import layout_from
from ladder.gitrung import run_git_rung
from ladder.mergework import RungError
from ladder.schemas import GitRungResult, HeadsKind, StructuralResult, StructuralTool
from ladder.structural import run_structural_rung
from ladder.trap_cli import trap_command

app = typer.Typer(
    help="Merge one pair at one rung of the ladder and record the outcome.", no_args_is_help=True
)

STATUS_STYLES = {"clean": "green", "resolved": "green", "conflicted": "yellow", "error": "red"}

PairArgument = Annotated[str, typer.Argument(help="Pair id, as in pairs.json.")]


@app.command("git")
def git_command(
    ctx: typer.Context,
    pair: PairArgument,
    heads: Annotated[HeadsKind, typer.Option(help="Which PR heads the workspace holds.")] = (
        "replay"
    ),
) -> None:
    """Merge b into a with git on a fresh workspace copy and record the conflict taxonomy."""
    try:
        result = run_git_rung(layout_from(ctx), pair, heads)
    except RungError as error:
        _fail(error)
    Console().print(_git_line(result))


@app.command()
def structural(
    ctx: typer.Context,
    pair: PairArgument,
    tool: Annotated[StructuralTool, typer.Option(help="Structural merge driver to merge with.")],
) -> None:
    """Retry a conflicted replay merge with a structural merge driver on a fresh workspace copy."""
    try:
        result = run_structural_rung(layout_from(ctx), pair, tool)
    except RungError as error:
        _fail(error)
    Console().print(_structural_line(result))


def _structural_line(result: StructuralResult) -> Text:
    line = Text(f"{result.pair_id} {result.tool} {result.tool_version}: ")
    line.append(result.status, style=STATUS_STYLES[result.status])
    marked = sum(file.has_markers for file in result.files)
    unparsed = sum(file.parses is False for file in result.files)
    line.append(
        f", still conflicted: {len(result.remaining_conflicted)} of {len(result.files)}"
        f", with markers: {marked}, not parsing: {unparsed}"
    )
    if result.status == "error":
        line.append(f": {result.detail}")
    return line


def _git_line(result: GitRungResult) -> Text:
    line = Text(f"{result.pair_id} git ({result.heads}): ")
    line.append(result.status, style=STATUS_STYLES[result.status])
    if result.status == "clean":
        line.append(f", merged tree {result.merged_tree}")
    elif result.status == "conflicted":
        types = ", ".join(f"{kind} {count}" for kind, count in Counter(result.types).items())
        line.append(f", conflicted files: {len(result.files)}, conflict types: {types}")
    else:
        line.append(f": {result.detail}")
    return line


def _fail(error: Exception) -> NoReturn:
    Console(stderr=True).print(str(error), style="red", markup=False, highlight=False)
    raise typer.Exit(1)


app.command("trap")(trap_command)
