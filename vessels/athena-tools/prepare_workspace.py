"""Prepare a fresh Athena environment from the image's immutable uv cache."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

DEPENDENCY_FILES = ("pyproject.toml", "uv.lock", ".python-version")


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def cache_sha256(root: Path) -> str:
    """Bind the logical files, including only links within the cache seed."""
    root = root.resolve(strict=True)
    files: list[list[str]] = []

    def visit(directory: Path, ancestors: frozenset[Path]) -> None:
        resolved = directory.resolve(strict=True)
        if not resolved.is_relative_to(root) or resolved in ancestors:
            raise ValueError("cache seed has an external or cyclic directory link")
        for path in sorted(directory.iterdir()):
            target = path.resolve(strict=True)
            if not target.is_relative_to(root):
                raise ValueError("cache seed has an external file link")
            if path.is_dir():
                visit(path, ancestors | {resolved})
            elif path.is_file():
                files.append([path.relative_to(root).as_posix(), file_sha256(path)])
            else:
                raise ValueError("cache seed contains a non-file entry")

    visit(root, frozenset())
    manifest = json.dumps(sorted(files), separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(manifest.encode()).hexdigest()


def prepare(arguments: argparse.Namespace) -> dict[str, object]:
    workspace = arguments.workspace.resolve(strict=True)
    seed = arguments.seed.resolve(strict=True)
    binding = json.loads(arguments.binding.read_text())
    if not re.fullmatch(r"[0-9a-f]{64}", arguments.snapshot_sha256):
        raise ValueError("snapshot must be a SHA-256 digest")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", arguments.image_digest):
        raise ValueError("image must be a pinned SHA-256 digest")
    if not re.fullmatch(r"[0-9a-f]{40}", binding["upstream_revision"]):
        raise ValueError("upstream revision must be an immutable commit")
    hashes = {name: file_sha256(workspace / name) for name in DEPENDENCY_FILES}
    if hashes != binding["dependency_files"]:
        raise ValueError("dependency files do not match the image binding")
    if cache_sha256(seed) != binding["cache_sha256"]:
        raise ValueError("cache seed does not match the image binding")

    cache_home = Path(os.environ["XDG_CACHE_HOME"]).resolve()
    if not cache_home.is_relative_to(workspace):
        raise ValueError("XDG_CACHE_HOME must be inside the private workspace")
    cache = cache_home / "athena-uv"
    environment = workspace / ".venv"
    receipt = workspace / ".fleet-runtime" / "athena-preparation.json"
    for path in (cache, environment, receipt):
        if path.exists() or path.is_symlink():
            raise ValueError(f"preparation requires a fresh output: {path}")

    cache_home.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copytree(seed, cache, symlinks=False)
    # Image files are immutable. Their private copies must be writable by uv;
    # preserve executability for cached wheel scripts and native executables.
    for path in (cache, *cache.rglob("*")):
        executable = path.stat().st_mode & stat.S_IXUSR
        path.chmod(0o700 if path.is_dir() or executable else 0o600)
    env = {
        key: value for key, value in os.environ.items()
        if key in {
            "PATH", "HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME",
            "TMPDIR", "TMP", "LANG", "LC_ALL",
        }
    }
    env.update({
        "UV_OFFLINE": "1",
        "UV_PYTHON_DOWNLOADS": "never",
        "UV_PYTHON": sys.executable,
        "UV_CACHE_DIR": str(cache),
        "UV_PROJECT_ENVIRONMENT": str(environment),
        "UV_LINK_MODE": "copy",
        "UV_CONCURRENT_BUILDS": "1",
        "UV_CONCURRENT_INSTALLS": "1",
        "RAYON_NUM_THREADS": "1",
    })
    subprocess.run(
        ["uv", "sync", "--locked", "--offline"], cwd=workspace, env=env,
        check=True, timeout=180,
    )
    if {name: file_sha256(workspace / name) for name in DEPENDENCY_FILES} != hashes:
        raise ValueError("dependency files changed during preparation")
    result: dict[str, object] = {
        "snapshot_sha256": arguments.snapshot_sha256,
        "image_digest": arguments.image_digest,
        "upstream_revision": binding["upstream_revision"],
        "dependency_files": hashes,
        "cache_sha256": binding["cache_sha256"],
        "uv_cache_dir": str(cache),
        "environment": str(environment),
        "python_executable": sys.executable,
    }
    receipt.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with receipt.open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=Path("/workspace"))
    parser.add_argument("--seed", type=Path, default=Path("/opt/athena/cache"))
    parser.add_argument("--binding", type=Path, default=Path("/opt/athena/inputs.json"))
    parser.add_argument("--snapshot-sha256", required=True)
    parser.add_argument("--image-digest", required=True)
    arguments = parser.parse_args()
    try:
        print(json.dumps(prepare(arguments), sort_keys=True))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"Athena workspace preparation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
