#!/usr/bin/env python3
"""Render base-image tool pins from versions.yml into the base Dockerfiles.

``versions.yml`` is the single source of truth for tool versions. The base
Dockerfiles do not carry their own copies of those version strings; each one
holds a generated block::

    # BEGIN GENERATED TOOL PINS (source: versions.yml)
    ENV NPM_VERSION=11.21.2
    # END GENERATED TOOL PINS

This script rewrites that block from ``tools.<name>.version`` for every tool
whose ``used_by`` lists the Dockerfile. Tool ``foo`` becomes ``ENV FOO_VERSION``,
which the install commands reference as ``${FOO_VERSION}``.

Usage:
    python scripts/render_version_pins.py          # rewrite the blocks
    python scripts/render_version_pins.py --check  # exit 1 if a block is stale
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSIONS_FILE = REPO_ROOT / "versions.yml"
BASE_DIR = REPO_ROOT / "bases"

BEGIN_MARKER = "# BEGIN GENERATED TOOL PINS (source: versions.yml)"
END_MARKER = "# END GENERATED TOOL PINS"


def load_versions() -> dict:
    """Load versions.yml as a mapping."""
    with VERSIONS_FILE.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def env_var_for(tool_name: str) -> str:
    """Return the ENV variable that carries *tool_name*'s pinned version."""
    return f"{tool_name.upper().replace('-', '_')}_VERSION"


def pins_for(rel_path: str, versions: dict) -> list[tuple[str, str]]:
    """Return [(ENV_NAME, version)] for the tools that *rel_path* consumes."""
    pins: list[tuple[str, str]] = []
    for tool_name, config in (versions.get("tools") or {}).items():
        if not isinstance(config, dict) or "version" not in config:
            continue
        if rel_path not in (config.get("used_by") or []):
            continue
        pins.append((env_var_for(tool_name), str(config["version"])))
    return sorted(pins)


def render_block(pins: list[tuple[str, str]]) -> str:
    """Render the generated block for *pins*, markers included."""
    lines = [BEGIN_MARKER]
    lines.extend(f"ENV {name}={version}" for name, version in pins)
    lines.append(END_MARKER)
    return "\n".join(lines)


def replace_block(text: str, block: str) -> str:
    """Replace the generated block in *text*; raise ValueError if it is absent."""
    start = text.find(BEGIN_MARKER)
    stop = text.find(END_MARKER)
    if start == -1 or stop == -1 or stop < start:
        raise ValueError(f"missing generated pin block ({BEGIN_MARKER!r} .. {END_MARKER!r})")
    return text[:start] + block + text[stop + len(END_MARKER) :]


def main(argv: list[str] | None = None) -> int:
    """Rewrite or verify every base Dockerfile's generated pin block."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="report stale blocks and exit non-zero instead of rewriting",
    )
    args = parser.parse_args(argv)

    versions = load_versions()
    stale: list[str] = []
    failed = False

    for path in sorted(BASE_DIR.glob("Dockerfile.*")):
        rel_path = str(path.relative_to(REPO_ROOT))
        original = path.read_text(encoding="utf-8")
        block = render_block(pins_for(rel_path, versions))
        try:
            updated = replace_block(original, block)
        except ValueError as exc:
            print(f"{rel_path}: {exc}", file=sys.stderr)
            failed = True
            continue
        if updated == original:
            continue
        if args.check:
            stale.append(rel_path)
            sys.stdout.writelines(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    updated.splitlines(keepends=True),
                    fromfile=f"{rel_path} (committed)",
                    tofile=f"{rel_path} (from versions.yml)",
                )
            )
        else:
            path.write_text(updated, encoding="utf-8")
            print(f"updated {rel_path}")

    if failed:
        return 1
    if args.check:
        if stale:
            print(
                "\nStale base-image pins: "
                + ", ".join(stale)
                + "\nRegenerate with: pixi run python scripts/render_version_pins.py",
                file=sys.stderr,
            )
            return 1
        print("Base-image pin blocks match versions.yml.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
