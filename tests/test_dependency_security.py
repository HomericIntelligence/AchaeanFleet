"""Check dependency artifacts against the security gates used by CI."""

from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
ADM_ZIP_FIXED = (0, 6, 1)
SMOL_TOML_FIXED = (1, 7, 1)


def version_floor(value: str) -> tuple[int, ...]:
    """Read the numeric floor from an exact version or a minimum range."""
    match = re.fullmatch(r"(?:\^|~|>=)?(\d+)\.(\d+)\.(\d+)", value)
    if match is None:
        raise ValueError(f"Unsupported dependency version: {value!r}")
    return tuple(int(part) for part in match.groups())


class DependencySecurityTests(unittest.TestCase):
    def test_adm_zip_override_excludes_affected_versions(self) -> None:
        """Resolution must exclude versions affected by GHSA-7q85-xj36-vmfc."""
        manifest = json.loads((ROOT / "dagger/package.json").read_text())
        self.assertGreaterEqual(
            version_floor(manifest["overrides"]["adm-zip"]), ADM_ZIP_FIXED
        )

    def test_locked_adm_zip_excludes_affected_versions(self) -> None:
        """Every installed adm-zip instance must include the published fix."""
        lock = json.loads((ROOT / "dagger/package-lock.json").read_text())
        packages = {
            path: entry for path, entry in lock["packages"].items()
            if path.endswith("/adm-zip")
        }
        self.assertTrue(packages, "The Dagger archive dependency is absent from the lock")
        for path, entry in packages.items():
            with self.subTest(path=path):
                self.assertGreaterEqual(version_floor(entry["version"]), ADM_ZIP_FIXED)

    def test_locked_ci_smol_toml_excludes_affected_versions(self) -> None:
        """Every CI TOML parser instance must include the CVE-2026-85730 fix."""
        lock = json.loads((ROOT / "ci/package-lock.json").read_text())
        packages = {
            path: entry for path, entry in lock["packages"].items()
            if path.endswith("/smol-toml")
        }
        self.assertTrue(packages, "The CI TOML dependency is absent from the lock")
        for path, entry in packages.items():
            with self.subTest(path=path):
                self.assertGreaterEqual(version_floor(entry["version"]), SMOL_TOML_FIXED)
