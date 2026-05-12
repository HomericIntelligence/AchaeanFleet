"""
Image tag generation utilities for AchaeanFleet.

Produces collision-safe tags per image push:
  :latest                   — mutable, always the most recent main build
  :git-<7-char-sha>         — immutable, precise rollback identifier
  :YYYY-MM-DD-<7-char-sha>  — immutable, date-keyed with SHA suffix to guard
                              against same-day collision
"""

from __future__ import annotations

import re
from datetime import date
from typing import Sequence

_DATE_TAG_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-[0-9a-f]{7}$")
_SHA_RE = re.compile(r"^[0-9a-f]{4,40}$", re.IGNORECASE)


def short_sha(full_sha: str) -> str:
    """Return the first 7 hex characters of *full_sha*.

    Raises ValueError if the input does not look like a hex SHA.
    """
    if not _SHA_RE.match(full_sha):
        raise ValueError(f"Not a valid git SHA: {full_sha!r}")
    return full_sha[:7].lower()


def build_date_tag(build_date: date, full_sha: str) -> str:
    """Return a collision-safe date tag of the form ``YYYY-MM-DD-<7sha>``."""
    return f"{build_date.isoformat()}-{short_sha(full_sha)}"


def is_valid_date_tag(tag: str) -> bool:
    """Return True if *tag* matches the expected ``YYYY-MM-DD-<7sha>`` format."""
    return bool(_DATE_TAG_RE.match(tag))


def image_tags(
    registry: str,
    image_name: str,
    full_sha: str,
    build_date: date | None = None,
) -> list[str]:
    """Return all three tags that should be pushed for *image_name*.

    Args:
        registry: Registry prefix, e.g. ``ghcr.io/homericintelligence``.
        image_name: Bare image name, e.g. ``achaean-claude``.
        full_sha: Full 40-char (or at least 7-char) git commit SHA.
        build_date: UTC build date; defaults to today.

    Returns:
        A list of three fully-qualified tag strings:
        ``[latest, git-<sha>, YYYY-MM-DD-<sha>]``.
    """
    if build_date is None:
        build_date = date.today()

    sha7 = short_sha(full_sha)
    base = f"{registry.rstrip('/')}/{image_name}"
    return [
        f"{base}:latest",
        f"{base}:git-{sha7}",
        f"{base}:{build_date.isoformat()}-{sha7}",
    ]


def parse_tags_from_env(
    registry: str,
    image_names: Sequence[str],
    git_sha: str,
    build_date_str: str,
) -> dict[str, list[str]]:
    """Build tag lists for multiple images from CI environment strings.

    Args:
        registry: Registry URL prefix.
        image_names: Iterable of bare image names.
        git_sha: Full or short git SHA string (must be hex, ≥7 chars).
        build_date_str: ISO-format date string (``YYYY-MM-DD``).

    Returns:
        Mapping of image name → list of three tags.

    Raises:
        ValueError: If *build_date_str* is not a valid ISO date.
    """
    try:
        build_date = date.fromisoformat(build_date_str)
    except ValueError:
        raise ValueError(f"build_date_str must be YYYY-MM-DD, got {build_date_str!r}")

    return {
        name: image_tags(registry, name, git_sha, build_date)
        for name in image_names
    }
