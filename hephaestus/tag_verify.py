"""Tag verification helpers for post-push GHCR validation."""

import re
import subprocess
from dataclasses import dataclass
from typing import Sequence


REGISTRY = "ghcr.io/homericintelligence"
SENTINEL_IMAGE = f"{REGISTRY}/achaean-claude"

_SHA_TAG_RE = re.compile(r"^git-[0-9a-f]{7}$")
_DATE_TAG_RE = re.compile(r"^\d{8}$")


@dataclass(frozen=True)
class ImageTags:
    """The three expected tags for a pushed image."""

    latest: str
    sha: str
    date: str

    def all_tags(self) -> list[str]:
        """Return all three expected tags in order."""
        return [self.latest, self.sha, self.date]


def build_image_tags(image: str, sha: str, date: str) -> ImageTags:
    """Build the three expected tag references for a given image, SHA, and date.

    Args:
        image: Full image name, e.g. ``ghcr.io/homericintelligence/achaean-claude``.
        sha: Short git SHA (7 hex chars), e.g. ``abc1234``.
        date: Date string in ``YYYYMMDD`` format, e.g. ``20260423``.

    Returns:
        ImageTags with :latest, :git-<sha>, and :<date> references.
    """
    if not _SHA_TAG_RE.match(f"git-{sha}"):
        raise ValueError(f"sha must be 7 lowercase hex chars, got: {sha!r}")
    if not _DATE_TAG_RE.match(date):
        raise ValueError(f"date must be YYYYMMDD format, got: {date!r}")
    return ImageTags(
        latest=f"{image}:latest",
        sha=f"{image}:git-{sha}",
        date=f"{image}:{date}",
    )


def manifest_inspect(tag: str) -> bool:
    """Return True if ``docker manifest inspect <tag>`` exits 0, False otherwise."""
    result = subprocess.run(
        ["docker", "manifest", "inspect", tag],
        capture_output=True,
    )
    return result.returncode == 0


def verify_tags(tags: ImageTags) -> dict[str, bool]:
    """Run manifest inspection for each tag and return a pass/fail mapping.

    Args:
        tags: The three expected image tag references.

    Returns:
        Dict mapping each tag string to True (present) or False (missing).
    """
    return {tag: manifest_inspect(tag) for tag in tags.all_tags()}


def assert_all_tags_present(tags: ImageTags) -> None:
    """Raise AssertionError listing any tags that failed manifest inspection.

    Args:
        tags: The three expected image tag references.
    """
    results = verify_tags(tags)
    missing = [tag for tag, ok in results.items() if not ok]
    if missing:
        raise AssertionError(
            "The following tags are missing from the registry:\n"
            + "\n".join(f"  {t}" for t in missing)
        )
