"""
Static regression tests for the security-override floors that close issue
#760's dependency CVEs.

These tests require no Docker daemon or network — they parse repository text
only. Run with: pytest tests/ -v

Covered assertions
------------------
* vessels/aider/requirements-security-overrides.txt pins every CVE-flagged
  package at (at least) its current override floor. The floors here mirror the
  *current* pinned values, not merely the CVE fixed versions, so a silent
  downgrade on a future aider bump fails the suite.
* protobuf additionally keeps its ``<6`` upper cap (the 5.x line litellm's
  tree resolves against).
* dagger/package.json keeps the ``tar`` override at >= 7.5.21 (clears
  GHSA-r292-9mhp-454m / CVE-2026-73566).

Scope
-----
The pinned floors and the dagger tar override pre-exist this PR on main
(landed via #765 / #761). This PR adds ONLY the regression guard plus the
.trivyignore stale-suppression pruning (issue #760 step 3); these tests
deliberately assert files that this diff itself does not modify.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent

OVERRIDES_FILE = REPO_ROOT / "vessels" / "aider" / "requirements-security-overrides.txt"
DAGGER_PACKAGE_JSON = REPO_ROOT / "dagger" / "package.json"

# Matches requirement lines like: "urllib3>=2.7.0        # CVE comment"
_REQ_LINE_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._\-]*)"
    r"(?P<spec>[<>=!~].*?)"
    r"\s*(?:#.*)?$"
)


def _parse_override_specs(text: str) -> dict[str, str]:
    """Parse requirement lines into a {package: specifier} mapping."""
    specs: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _REQ_LINE_RE.match(line)
        assert match is not None, f"Unparseable override line: {raw_line!r}"
        specs[match.group("name")] = match.group("spec").strip()
    return specs


def _version_tuple(version: str) -> tuple[int, ...]:
    """Convert a numeric dotted version string into a comparable tuple."""
    return tuple(int(part) for part in version.split("."))


def _floor_of(specifier: str) -> tuple[int, ...]:
    """Extract the >= floor version tuple from a PEP 440 specifier string.

    Raises AssertionError when the specifier carries no >= constraint.
    """
    match = re.search(r">=\s*(\d+(?:\.\d+)*)", specifier)
    assert match is not None, (
        f"No '>=' floor found in specifier {specifier!r}"
    )
    return _version_tuple(match.group(1))


def _npm_floor(specifier: str) -> tuple[int, ...]:
    """Extract the minimum version tuple from an npm range like '^7.5.21'."""
    stripped = specifier.lstrip("^~>=")
    return _version_tuple(stripped.split("-")[0])


def _load_override_specs() -> dict[str, str]:
    """Load the parsed {package: specifier} mapping from the overrides file."""
    return _parse_override_specs(OVERRIDES_FILE.read_text())


# ---------------------------------------------------------------------------
# Regression data
# ---------------------------------------------------------------------------

# (package, minimum floor) — floors are the CURRENT override values so that a
# silent downgrade below today's pins fails even if it stays above the bare
# CVE fixed versions cited in issue #760.
REQUIRED_AIDER_FLOORS: list[tuple[str, str]] = [
    ("GitPython", "3.1.49"),
    ("Pillow", "12.2.0"),
    ("aiohttp", "3.13.4"),
    ("filelock", "3.20.3"),
    ("litellm", "1.83.10"),
    ("pip", "26.0"),
    ("pyasn1", "0.6.3"),
    ("python-dotenv", "1.2.2"),
    ("requests", "2.32.4"),
    ("starlette", "1.3.1"),
    ("soupsieve", "2.8.4"),
    ("urllib3", "2.7.0"),
]

REQUIRED_TAR_NPM_FLOOR = "7.5.21"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAiderSecurityOverrides:
    """Regression guards for vessels/aider/requirements-security-overrides.txt."""

    def test_overrides_file_exists(self) -> None:
        """The security-overrides file must exist next to the aider Dockerfile."""
        assert OVERRIDES_FILE.exists(), f"{OVERRIDES_FILE} not found"

    @pytest.mark.parametrize(
        "package,floor",
        REQUIRED_AIDER_FLOORS,
        ids=[f"{pkg}>={ver}" for pkg, ver in REQUIRED_AIDER_FLOORS],
    )
    def test_package_floor(self, package: str, floor: str) -> None:
        """Each flagged package must be overridden with a >= current floor."""
        specs = _load_override_specs()
        assert package in specs, (
            f"{package} missing from {OVERRIDES_FILE.name}; "
            f"aider-chat transitive pins would regress to CVE-affected versions"
        )
        assert _floor_of(specs[package]) >= _version_tuple(floor), (
            f"{package}{specs[package]} regressed below the required floor "
            f">={floor} ({OVERRIDES_FILE.name})"
        )

    def test_protobuf_floor_and_cap(self) -> None:
        """protobuf must stay on the patched 5.x line: >=5.29.6 and <6."""
        specs = _load_override_specs()
        assert "protobuf" in specs, (
            f"protobuf missing from {OVERRIDES_FILE.name}"
        )
        spec = specs["protobuf"]
        assert _floor_of(spec) >= _version_tuple("5.29.6"), (
            f"protobuf{spec} regressed below >=5.29.6 (CVE-2026-0994/-4565)"
        )
        assert re.search(r"<\s*6\b", spec) is not None, (
            f"protobuf{spec} lost its '<6' cap that keeps the 5.x line "
            f"litellm's dependency tree resolves against"
        )


class TestDaggerTarOverride:
    """Regression guard for the dagger lockfile tar override (#761 / #760)."""

    def test_tar_override_floor(self) -> None:
        """dagger/package.json must keep tar overridden at >= 7.5.21."""
        assert DAGGER_PACKAGE_JSON.exists(), f"{DAGGER_PACKAGE_JSON} not found"
        package_json = json.loads(DAGGER_PACKAGE_JSON.read_text())
        overrides = package_json.get("overrides", {})
        assert "tar" in overrides, (
            "dagger/package.json lost its 'tar' override "
            "(GHSA-r292-9mhp-454m / CVE-2026-73566 regression)"
        )
        assert _npm_floor(overrides["tar"]) >= _version_tuple(
            REQUIRED_TAR_NPM_FLOOR
        ), (
            f"dagger tar override {overrides['tar']!r} is below the required "
            f"floor >={REQUIRED_TAR_NPM_FLOOR}"
        )
