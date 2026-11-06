"""Regression guard for yq Go-standard-library vulnerability cleanup."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]

# These exact v4.54.2 release artifacts were independently checksum-verified and
# embed go1.27.3 in their build info (``strings <binary> | grep -Eo 'go1\.[0-9]+\.[0-9]+'``
# on both downloaded assets). Pinning the artifact bytes keeps suppression removal
# tied to the inspected binaries rather than to a mutable version label.
PATCHED_YQ_ARTIFACTS = {
    "amd64": {
        "asset": "yq_linux_amd64",
        "sha256": "44c7759059b4910827a0059a2757b22001e59360cdecdb2ef8dedc4b6c7e9f32",
    },
    "arm64": {
        "asset": "yq_linux_arm64",
        "sha256": "bd44211dcd29a5f0eb701d4b7eb5ccd0cfff3bd3966cb4f7f9bd5b13701d997e",
    },
}
FIXED_YQ_CVES = {
    "CVE-2026-39823",
    "CVE-2026-39825",
    "CVE-2026-39826",
    "CVE-2026-56852",
}


def test_fixed_yq_artifacts_do_not_retain_trivy_suppressions() -> None:
    """Known-patched yq bytes must not carry obsolete vulnerability ignores."""
    versions = yaml.safe_load((ROOT / "versions.yml").read_text())
    yq = versions["tools"]["yq"]

    assert yq["version"] == "v4.54.2"
    assert yq["checksums"] == PATCHED_YQ_ARTIFACTS

    ignored_ids = {
        line.strip()
        for line in (ROOT / ".trivyignore").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert FIXED_YQ_CVES.isdisjoint(ignored_ids)
