"""Syntactic checks on one file of a rung's output: present, marker-free, parseable."""

from pathlib import Path

from ladder.languages import language_for
from ladder.markers import has_markers
from ladder.schemas import ResolvedFileCheck
from ladder.syntax import parse, parses


def check_file(root: Path, path: str) -> ResolvedFileCheck:
    """Check one repository path in a working tree; an absent file with a grammar does not parse."""
    file = root / path
    language = language_for(path)
    if not file.is_file():
        return ResolvedFileCheck(
            path=path,
            present=False,
            has_markers=False,
            language=language,
            parses=None if language is None else False,
        )
    data = file.read_bytes()
    return ResolvedFileCheck(
        path=path,
        present=True,
        has_markers=has_markers(data),
        language=language,
        parses=parses(parse(data, language)),
    )
