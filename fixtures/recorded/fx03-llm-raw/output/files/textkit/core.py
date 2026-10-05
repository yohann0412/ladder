"""Small helpers for comma-separated text."""

from textkit.helpers import normalize


def parse(source):
    """Split comma-separated text into normalized fields."""
    fields = source.replace(";", ",").split(",")
    return [normalize(f) for f in fields if f]


def format(fields):
    """Join fields back into comma-separated text."""
    return ",".join(fields)


def validate(fields):
    """Return True when every field is non-empty."""
    return all(fields)


def summarize(text):
    """Return the number of fields in the text."""
    return len(parse(text))
