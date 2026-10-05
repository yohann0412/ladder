"""Render what `pairs resolve` found as a rich table."""

from collections import Counter
from collections.abc import Sequence
from typing import get_args

from rich.console import Console
from rich.table import Table

from ladder.schemas import PairRefs, PrRefs, ResolveStatus, TruthLocator, TruthStatus


def render_resolve(console: Console, results: Sequence[PairRefs]) -> None:
    """Print pair counts per status, contamination, rewinds, criss-crosses and truth commits."""
    table = Table(title=f"Resolved {len(results)} pairs")
    table.add_column("outcome")
    table.add_column("pairs", justify="right")
    statuses = Counter(refs.status for refs in results)
    for status in get_args(ResolveStatus):
        table.add_row(f"status {status}", str(statuses[status]))
    table.add_section()
    table.add_row("a contaminated", str(sum(refs.a.contaminated for refs in results)))
    table.add_row("b contaminated", str(sum(refs.b.contaminated for refs in results)))
    rewound = sum(_rewound(refs.a) or _rewound(refs.b) for refs in results)
    table.add_row("rewound to a PR commit", str(rewound))
    table.add_row("unrecoverable (rebased)", str(statuses["unrecoverable_rebased"]))
    criss_cross = sum(refs.replay_merge_base_count > 1 for refs in results)
    table.add_row("criss-cross at replay heads", str(criss_cross))
    table.add_section()
    truths = Counter(refs.truth_status for refs in results)
    methods = Counter(refs.truth_method for refs in results)
    for status in get_args(TruthStatus):
        table.add_row(f"truth {status}", str(truths[status]))
    for method in get_args(TruthLocator):
        table.add_row(f"  located by {method}", str(methods[method]))
    console.print(table)


def _rewound(refs: PrRefs) -> bool:
    return refs.replay_head is not None and refs.rewound_commits > 0
