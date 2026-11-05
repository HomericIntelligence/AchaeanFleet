"""Install declared CI executables after verifying their complete release bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import tarfile
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


def install_archive(source: Path, expected: str, kind: str, member: str, destination: Path) -> None:
    with source.open("rb") as file:
        actual = hashlib.file_digest(file, "sha256").hexdigest()
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or actual != expected:
        raise ValueError("CI tool checksum mismatch")
    if destination.is_symlink():
        raise ValueError("CI executable destination must be a regular file")
    if kind == "raw":
        shutil.copyfile(source, destination)
    elif kind == "tar.gz":
        with tarfile.open(source, "r:gz") as archive:
            entry = archive.getmember(member)
            if not entry.isfile():
                raise ValueError("CI archive executable must be a regular file")
            stream = archive.extractfile(entry)
            if stream is None:
                raise ValueError("CI archive executable has no content")
            with stream, destination.open("wb") as output:
                shutil.copyfileobj(stream, output)
    elif kind == "zip":
        with zipfile.ZipFile(source) as archive:
            zip_entry = archive.getinfo(member)
            if zip_entry.is_dir() or stat.S_ISLNK(zip_entry.external_attr >> 16):
                raise ValueError("CI archive executable must be a regular file")
            with archive.open(zip_entry) as stream, destination.open("wb") as output:
                shutil.copyfileobj(stream, output)
    else:
        raise ValueError("unsupported CI archive format")
    destination.chmod(0o755)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("linux/amd64", "linux/arm64"), required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    for name, variants in json.loads(args.artifacts.read_text()).items():
        if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
            raise ValueError("invalid CI executable name")
        artifact = variants[args.platform]
        url = urllib.parse.urlparse(artifact["url"])
        if url.scheme != "https" or url.netloc not in ("github.com", "releases.hashicorp.com"):
            raise ValueError("CI tools require a declared upstream HTTPS release")
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "archive"
            with (
                urllib.request.urlopen(artifact["url"], timeout=120) as response,
                archive.open("wb") as output,
            ):
                shutil.copyfileobj(response, output)
            install_archive(
                archive,
                artifact["sha256"],
                artifact["format"],
                artifact.get("member", name),
                args.destination / name,
            )
        print(f"Installed {name} {variants['version']} ({artifact['sha256']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
