"""Fetch the replay study's replication package from Zenodo and unpack what the loader reads."""

import zipfile
from pathlib import Path

from ladder.download import download
from ladder.replaycsv import REPLAY_CSV
from ladder.schemas import SourceFile

RECORD_ID = "21186464"
PACKAGE_URL = f"https://zenodo.org/api/records/{RECORD_ID}/files/replication_package.zip/content"
PACKAGE_MD5 = "59a99c9cf58793957806a7fa5e712f8f"
PACKAGE_NAME = f"zenodo-{RECORD_ID}/replication_package.zip"
PACKAGE_README = "replication_README.md"
VENDORED_MEMBERS = {REPLAY_CSV: REPLAY_CSV, "README.md": PACKAGE_README}


class ChecksumError(RuntimeError):
    """A downloaded file does not have its published checksum."""


def fetch_replication_package(downloads: Path, out: Path) -> SourceFile:
    """Download and verify the replication package, then copy the replay CSV and README out."""
    archive = downloads / "replication_package.zip"
    md5 = download(PACKAGE_URL, archive)
    if md5 != PACKAGE_MD5:
        raise ChecksumError(f"{PACKAGE_URL}: md5 {md5}, expected {PACKAGE_MD5}")
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        for member, name in VENDORED_MEMBERS.items():
            (out / name).write_bytes(package.read(member))
    return SourceFile(name=PACKAGE_NAME, url=PACKAGE_URL, md5=md5)
