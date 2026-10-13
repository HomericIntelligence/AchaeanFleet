"""Regression guard for yq Go-standard-library vulnerability cleanup."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]

# These exact v4.53.6 release artifacts were independently checksum-verified and
# report go1.27.0 via ``go version -m``. Pinning the artifact bytes keeps suppression
# removal tied to the inspected binaries rather than to a mutable version label.
PATCHED_YQ_ARTIFACTS = {
    "amd64": {
        "asset": "yq_linux_amd64",
        "sha256": "c5f056448f973ae7d39b5401949648a78f2dc1947d6a8eb65be60d5c504b9385",
    },
    "arm64": {
        "asset": "yq_linux_arm64",
        "sha256": "88a1016bc1d657375a35864e4f44b6f333df8ff97b559f51bba0adcb2169df09",
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

    assert yq["version"] == "v4.53.6"
    assert yq["checksums"] == PATCHED_YQ_ARTIFACTS

    ignored_ids = {
        line.strip()
        for line in (ROOT / ".trivyignore").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert FIXED_YQ_CVES.isdisjoint(ignored_ids)
