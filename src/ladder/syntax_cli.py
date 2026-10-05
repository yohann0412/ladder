"""Commands that compare two files syntactically and list a file's definitions, as JSON."""

from pathlib import Path
from typing import Annotated

import typer

from ladder.compare import compare_versions
from ladder.entities import list_entities
from ladder.languages import language_for
from ladder.syntax import parse

app = typer.Typer()

ExistingFile = Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)]


@app.command()
def compare(left: ExistingFile, right: ExistingFile) -> None:
    """Print whether two files are AST-equivalent, and how similar, using LEFT's language."""
    result = compare_versions(left.read_bytes(), right.read_bytes(), language_for(left))
    typer.echo(result.model_dump_json())


@app.command()
def entities(file: ExistingFile) -> None:
    """Print a file's named definitions with qualified names and line ranges."""
    listing = list_entities(parse(file.read_bytes(), language_for(file)))
    typer.echo(listing.model_dump_json())
