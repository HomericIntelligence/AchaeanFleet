"""
Guard tests asserting that achaean-aider remains disabled in CI per issue #665.

These tests are intentionally inverted: they PASS when aider is absent from CI
matrices and FAIL when it reappears, signalling that the PR needs to also update
this file (removing it) as part of the re-enable process.

Re-enabling aider:
  1. Verify upstream aider-chat has cleaner transitive pins (see #665 body).
  2. Revert every #665-marked hunk in: ci.yml, release.yml, justfile, scripts/,
     nomad/mesh.nomad.hcl, dependabot.yml.
  3. Delete this file (tests/test_aider_disabled.py).
  4. Run: pixi run pytest

Run with: pytest tests/ -v
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_yaml(rel_path: str) -> dict:
    """Load a YAML file relative to REPO_ROOT."""
    path = REPO_ROOT / rel_path
    assert path.exists(), f"Expected file not found: {rel_path}"
    with path.open() as fh:
        return yaml.safe_load(fh)


def _vessel_names_from_matrix(matrix_vessels: list[dict]) -> list[str]:
    """Extract vessel names from a YAML matrix list (skipping None entries)."""
    return [entry["name"] for entry in matrix_vessels if entry is not None]


# ---------------------------------------------------------------------------
# ci.yml assertions
# ---------------------------------------------------------------------------


def test_aider_absent_from_ci_build_matrix() -> None:
    """achaean-aider must not appear in ci.yml build-vessels matrix."""
    ci = _load_yaml(".github/workflows/ci.yml")
    build_vessels_job = ci["jobs"]["build-vessels"]
    matrix_vessels = build_vessels_job["strategy"]["matrix"]["vessel"]
    names = _vessel_names_from_matrix(matrix_vessels)
    assert "achaean-aider" not in names, (
        "achaean-aider found in ci.yml build-vessels matrix — "
        "vessel must remain disabled per #665."
    )


def test_aider_absent_from_ci_push_matrix() -> None:
    """achaean-aider must not appear in ci.yml push-to-registry matrix."""
    ci = _load_yaml(".github/workflows/ci.yml")
    push_job = ci["jobs"]["push-to-registry"]
    matrix_vessels = push_job["strategy"]["matrix"]["vessel"]
    names = _vessel_names_from_matrix(matrix_vessels)
    assert "achaean-aider" not in names, (
        "achaean-aider found in ci.yml push-to-registry matrix — "
        "vessel must remain disabled per #665."
    )


def test_aider_absent_from_ci_verify_array() -> None:
    """achaean-aider must not appear as an active entry in the ci.yml
    verify-registry vessels shell array (comment lines are acceptable)."""
    ci_path = REPO_ROOT / ".github/workflows/ci.yml"
    assert ci_path.exists(), "ci.yml not found"
    in_verify = False
    in_vessels_array = False
    for line in ci_path.read_text().splitlines():
        stripped = stripped_no_comment = line.strip()
        # Remove inline comments for the active-entry check
        if "#" in stripped:
            stripped_no_comment = stripped[: stripped.index("#")].strip()

        if "verify-registry:" in stripped:
            in_verify = True
        if in_verify and 'vessels=(' in stripped_no_comment:
            in_vessels_array = True
        if in_vessels_array and stripped_no_comment == ")":
            in_vessels_array = False
            in_verify = False
        if in_vessels_array:
            # Active (non-comment) line containing achaean-aider is a failure
            if "achaean-aider" in stripped_no_comment:
                pytest.fail(
                    "achaean-aider is an active entry in ci.yml verify-registry "
                    "vessels array — must remain disabled per #665."
                )


# ---------------------------------------------------------------------------
# release.yml assertions
# ---------------------------------------------------------------------------


def test_aider_absent_from_release_matrix() -> None:
    """achaean-aider must not appear in release.yml release job matrix."""
    release = _load_yaml(".github/workflows/release.yml")
    release_job = release["jobs"]["release"]
    matrix_vessels = release_job["strategy"]["matrix"]["vessel"]
    names = _vessel_names_from_matrix(matrix_vessels)
    assert "achaean-aider" not in names, (
        "achaean-aider found in release.yml matrix — "
        "vessel must remain disabled per #665 to prevent CVE-exposed image pushes."
    )


# ---------------------------------------------------------------------------
# Artifact retention assertions (re-enable precondition)
# ---------------------------------------------------------------------------


_AIDER_ARTIFACTS = [
    "vessels/aider/Dockerfile",
    "vessels/aider/requirements.txt",
    "vessels/aider/requirements-security-overrides.txt",
]


@pytest.mark.parametrize("rel_path", sorted(_AIDER_ARTIFACTS))
def test_aider_artifacts_retained(rel_path: str) -> None:
    """Retained aider artifacts must still exist on disk.

    These files are intentionally kept so that re-enabling aider is a
    mechanical revert of #665 CI changes rather than a reconstruction.
    If any of these files are accidentally deleted, the re-enable path
    becomes significantly more expensive.
    """
    assert (REPO_ROOT / rel_path).exists(), (
        f"Aider artifact unexpectedly deleted: {rel_path}. "
        "This file must be retained on disk per #665 — restore it."
    )
