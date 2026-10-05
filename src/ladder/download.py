"""Download over HTTPS; proxy and CA settings come from the standard environment variables."""

import hashlib
import urllib.request
from pathlib import Path

TIMEOUT_S = 300
CHUNK_BYTES = 1 << 20
USER_AGENT = "ladder-research-harness"


def fetch_bytes(url: str) -> bytes:
    """Return the body of a small HTTPS response."""
    with urllib.request.urlopen(_request(url), timeout=TIMEOUT_S) as response:
        return response.read()


def download(url: str, dest: Path) -> str:
    """Stream a URL into a file, replacing it atomically, and return the file's md5."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    digest = hashlib.md5(usedforsecurity=False)
    with (
        urllib.request.urlopen(_request(url), timeout=TIMEOUT_S) as response,
        partial.open("wb") as sink,
    ):
        while chunk := response.read(CHUNK_BYTES):
            digest.update(chunk)
            sink.write(chunk)
    partial.replace(dest)
    return digest.hexdigest()


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
