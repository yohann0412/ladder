"""Download over HTTPS; proxy and CA settings come from the standard environment variables."""

import hashlib
import http.client
import time
import urllib.error
import urllib.request
from pathlib import Path

TIMEOUT_S = 300
CHUNK_BYTES = 1 << 20
USER_AGENT = "ladder-research-harness"
ATTEMPTS = 8
RETRY_DELAY_S = 5
PARTIAL_CONTENT = 206
RANGE_NOT_SATISFIABLE = 416
FIRST_SERVER_ERROR = 500


class DownloadError(RuntimeError):
    """A download was still incomplete after every resume attempt."""


def fetch_bytes(url: str) -> bytes:
    """Return the body of a small HTTPS response."""
    with urllib.request.urlopen(_request(url), timeout=TIMEOUT_S) as response:
        return response.read()


def download(url: str, dest: Path) -> str:
    """Download a URL into dest, resuming cut-off transfers with range requests; return its md5.

    A file already at dest is kept. The body accumulates in a `.part` file next to dest, which a
    later call also resumes, and replaces dest atomically once it is complete.
    """
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_name(dest.name + ".part")
        _complete(url, partial)
        partial.replace(dest)
    return _md5(dest)


def _complete(url: str, partial: Path) -> None:
    for attempt in range(ATTEMPTS):
        if attempt:
            time.sleep(RETRY_DELAY_S)
        try:
            if _transfer(url, partial):
                return
        except urllib.error.HTTPError as error:
            if error.code == RANGE_NOT_SATISFIABLE:
                partial.unlink()
            elif error.code < FIRST_SERVER_ERROR:
                raise
        except (OSError, http.client.HTTPException):
            continue
    raise DownloadError(f"{url}: incomplete after {ATTEMPTS} attempts")


def _transfer(url: str, partial: Path) -> bool:
    """Append what partial lacks of the body; return whether the body is now complete."""
    offset = partial.stat().st_size if partial.exists() else 0
    request = _request(url)
    if offset:
        request.add_header("Range", f"bytes={offset}-")
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        resumed = response.status == PARTIAL_CONTENT
        total = _total_size(response.headers, resumed)
        with partial.open("ab" if resumed else "wb") as sink:
            while chunk := response.read(CHUNK_BYTES):
                sink.write(chunk)
    return total is None or partial.stat().st_size == total


def _total_size(headers: http.client.HTTPMessage, resumed: bool) -> int | None:
    if resumed:
        return int(headers["Content-Range"].rsplit("/", 1)[1])
    length = headers.get("Content-Length")
    return None if length is None else int(length)


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
