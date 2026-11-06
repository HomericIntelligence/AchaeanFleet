"""Assert versions.yml base-image pins match the digest-pinned FROM lines.

``versions.yml`` records the tag and digest of every external base image the
Dockerfiles build FROM. The monthly digest-bump workflow
(``.github/workflows/digest-bump.yml``) rewrites both sides in one pass; these
tests fail when only one side moves.

That drift is not hypothetical: ``base_images.node`` recorded tag ``25-slim``
and digest ``sha256:67134eb...`` while all three base Dockerfiles pinned
``node:26-slim@sha256:14bf3ea...``, and ``base_images.python`` recorded a digest
no Dockerfile used. The manifest is the record of what is built, so it has to
agree with the FROM lines, not with what some earlier bump intended.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
VERSIONS_FILE = REPO_ROOT / "versions.yml"

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
# `FROM <repo>:<tag>@sha256:...`, with an optional `AS <stage>` suffix.
FROM_RE = re.compile(r"^FROM\s+(?P<image>[^\s@]+)@(?P<digest>sha256:[0-9a-f]{64})(?:\s+AS\s+\S+)?\s*$")


def _versions() -> dict:
    return yaml.safe_load(VERSIONS_FILE.read_text(encoding="utf-8")) or {}


def _base_images() -> dict[str, dict]:
    return _versions().get("base_images") or {}


def _athena_python_image() -> str:
    """The athena vessel pins a version-qualified python image of its own."""
    return (_versions().get("athena_tools") or {}).get("python_image", "")


def _recorded_pins() -> set[tuple[str, str]]:
    """Every (tag, digest) pair recorded anywhere in the manifest.

    The repository half is not recorded separately: the Dockerfile FROM line
    carries it and the tag+digest pair is what must agree.
    """
    pins = {(config["tag"], config["digest"]) for config in _base_images().values()}
    athena = _athena_python_image()
    if athena:
        ref, _, digest = athena.partition("@")
        pins.add((ref.split(":", 1)[-1], digest))
    return pins


def _dockerfiles() -> list[Path]:
    paths = sorted((REPO_ROOT / "bases").glob("Dockerfile.*"))
    paths.extend(sorted((REPO_ROOT / "vessels").rglob("Dockerfile")))
    return paths


def _pinned_from_lines() -> list[tuple[Path, str, str]]:
    """Yield (dockerfile, image, digest) for every digest-pinned FROM line."""
    found: list[tuple[Path, str, str]] = []
    for path in _dockerfiles():
        for line in path.read_text(encoding="utf-8").splitlines():
            match = FROM_RE.match(line.strip())
            if match:
                found.append((path, match.group("image"), match.group("digest")))
    return found


@pytest.mark.parametrize("name", sorted(_base_images()))
def test_consumer_pins_the_recorded_digest(name: str) -> None:
    """Each ``used_by`` Dockerfile must contain the recorded tag and digest."""
    config = _base_images()[name]
    tag, digest = config["tag"], config["digest"]
    assert DIGEST_RE.match(digest), f"base_images.{name}.digest is not a sha256 digest: {digest!r}"
    assert config["used_by"], f"base_images.{name} lists no consumers"

    for rel_path in config["used_by"]:
        path = REPO_ROOT / rel_path
        assert path.exists(), f"base_images.{name} names a missing file: {rel_path}"
        pinned = f"{tag}@{digest}"
        assert pinned in path.read_text(encoding="utf-8"), (
            f"{rel_path} does not pin {name} at {pinned}. The manifest and the "
            f"Dockerfile disagree; run the digest-bump workflow or update both."
        )


def test_every_pinned_from_is_recorded() -> None:
    """A digest-pinned FROM that no manifest entry records cannot be maintained."""
    recorded = _recorded_pins()
    unrecorded = [
        f"{path.relative_to(REPO_ROOT)}: FROM {image}@{digest}"
        for path, image, digest in _pinned_from_lines()
        if (image.split(":", 1)[-1], digest) not in recorded
    ]
    assert not unrecorded, (
        "digest-pinned FROM lines missing from versions.yml: " + "; ".join(unrecorded)
    )
