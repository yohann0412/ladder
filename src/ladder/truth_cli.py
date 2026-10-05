"""The `ladder truth` commands: extract a pair's human resolution."""

import typer
from rich.console import Console
from rich.markup import escape

from ladder.cli_support import PairArgument, load_pair, refused
from ladder.context import layout_from
from ladder.refusal import RefusedError
from ladder.schemas import TruthRecord
from ladder.truth import extract_truth

app = typer.Typer(
    help="Extract human resolutions, only after every planned resolver run is settled.",
    no_args_is_help=True,
)


@app.command()
def extract(ctx: typer.Context, pair_id: PairArgument) -> None:
    """Extract a conflicting pair's human resolution; refuse while its resolver runs are open."""
    layout = layout_from(ctx)
    _, pair = load_pair(layout, pair_id)
    try:
        record = extract_truth(layout, pair)
    except RefusedError as error:
        raise refused(error) from error
    _render(Console(soft_wrap=True, highlight=False), record)


def _render(console: Console, record: TruthRecord) -> None:
    if record.status != "located":
        console.print(f"{record.pair_id}: truth {record.status}")
        return
    present = sum(file.present for file in record.files)
    console.print(
        f"{record.pair_id}: truth located by {record.method} at {record.commit}; "
        f"files present: {present}, absent: {len(record.files) - present}"
    )
    touched = ", ".join(record.touched_beyond_conflict) or "-"
    outside = ", ".join(record.outside_region_edit) or "-"
    console.print(escape(f"  touched beyond conflict: {touched}"))
    console.print(escape(f"  edited outside regions: {outside}"))
    console.print(
        f"  rewrite: {'yes' if record.rewrite else 'no'}; "
        f"leak (head equals truth): {'yes' if record.leak_head_equals_truth else 'no'}"
    )
