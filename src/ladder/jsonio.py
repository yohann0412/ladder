"""Read and write schema-validated JSON records."""

from pathlib import Path

from pydantic import BaseModel


def write_record(path: Path, record: BaseModel) -> None:
    """Write a record as indented JSON, atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_record[T: BaseModel](path: Path, model: type[T]) -> T:
    """Read and validate a record."""
    return model.model_validate_json(path.read_text(encoding="utf-8"))


def read_optional[T: BaseModel](path: Path, model: type[T]) -> T | None:
    """Read and validate a record, or return None when the file does not exist."""
    if not path.exists():
        return None
    return read_record(path, model)
