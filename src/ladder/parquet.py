"""Read selected rows of a parquet file as plain dictionaries.

pyarrow ships without type information, so this module is its only importer and the
untyped-library checks are relaxed here alone; callers validate the rows with pydantic.
"""
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false

from collections.abc import Collection
from pathlib import Path
from typing import cast

import pyarrow.parquet as pq


def read_matching(
    path: Path, columns: list[str], key: str, values: Collection[str | int]
) -> list[dict[str, object]]:
    """Return the named columns of every row whose `key` column holds one of `values`."""
    if not values:
        return []
    table = pq.read_table(path, columns=columns, filters=[(key, "in", list(values))])
    return cast(list[dict[str, object]], table.to_pylist())


def read_all(path: Path, columns: list[str]) -> list[dict[str, object]]:
    """Return the named columns of every row."""
    return cast(list[dict[str, object]], pq.read_table(path, columns=columns).to_pylist())


def read_distinct(path: Path, columns: list[str]) -> dict[str, list[object]]:
    """Return every distinct combination of the named columns, as one value list per column."""
    table = pq.read_table(path, columns=columns).group_by(columns).aggregate([])
    return {name: cast(list[object], table.column(name).to_pylist()) for name in columns}
