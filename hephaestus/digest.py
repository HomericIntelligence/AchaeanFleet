"""
Utilities for capturing and validating Docker image digests before registry push.

Used by the push-to-registry CI job to provide auditor traceability between
built artifacts and pushed registry images.
"""

from __future__ import annotations

import re
import subprocess


_SHA256_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")


def is_valid_digest(digest: str) -> bool:
    """Return True if digest is a valid sha256 content-addressable ID."""
    return bool(_SHA256_PATTERN.match(digest))


def inspect_digest(image_ref: str) -> str:
    """
    Return the content-addressable digest of a locally loaded Docker image.

    Runs ``docker inspect --format '{{.Id}}'`` and returns the result.

    Raises:
        ValueError: if docker inspect returns an empty string.
        subprocess.CalledProcessError: if docker inspect exits non-zero.
    """
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{.Id}}", image_ref],
        capture_output=True,
        text=True,
        check=True,
    )
    digest = result.stdout.strip()
    if not digest:
        raise ValueError(
            f"docker inspect returned empty digest for {image_ref!r}"
        )
    return digest


def format_summary_table(image_name: str, digest: str, commit_sha: str) -> str:
    """
    Return a Markdown summary table for a single image digest record.

    Suitable for appending to ``$GITHUB_STEP_SUMMARY``.
    """
    lines = [
        f"## Image Digest: `{image_name}:latest`",
        "| Field | Value |",
        "| --- | --- |",
        f"| Image | `{image_name}:latest` |",
        f"| Digest | `{digest}` |",
        f"| Commit | `{commit_sha}` |",
    ]
    return "\n".join(lines) + "\n"
