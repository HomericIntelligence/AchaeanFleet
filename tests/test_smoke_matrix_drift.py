"""
Drift guard: assert every enabled AI-agent vessel directory is represented in
the ``test-smoke-vessels`` matrix in ``.github/workflows/ci.yml``.

Prevents new vessels from silently bypassing runtime smoke coverage.

Design notes
------------
- Uses ``yaml.safe_load`` (pyyaml ≥6, available via pixi.lock).
- Fails loudly if the workflow file, the job, or the matrix key is absent —
  a silent pass on a missing structure would defeat the purpose.
- ``worker`` is excluded: it has its own HTTP health-poll smoke test
  (``test-smoke`` job).
- ``aider`` is excluded: currently disabled in CI — see issue #665.  When
  aider is re-enabled, remove it from ``DISABLED_VESSELS`` and add the
  matrix row in ci.yml; this test will then enforce coverage automatically.
- ``codebuff`` is excluded from the read-only smoke matrix: the ``codebuff``
  npm package is a self-updating launcher that downloads its ~48 MB runtime
  on first invocation and cannot persist/execute it under
  ``docker run --read-only``, so even ``codebuff --version`` re-downloads and
  exits 1.  The image is still built and validated by the build-vessels
  matrix.  Remove from EXCLUDED_VESSELS and restore the matrix row once
  codebuff ships a self-contained binary.

Run locally:
    pixi run pytest tests/test_smoke_matrix_drift.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
SMOKE_JOB_NAME = "test-smoke-vessels"

# Vessels excluded from the smoke matrix intentionally:
#   worker      — has a dedicated HTTP /health smoke job (test-smoke)
#   aider       — disabled in CI per #665; re-enable there first
#   hello-world — C++ E2E integration test binary, not an AI-agent vessel;
#                 it has its own CMD and is not part of the agent mesh smoke set
#   codebuff    — self-updating launcher that re-downloads its runtime on every
#                 invocation; incompatible with the read-only smoke test. Still
#                 built/validated by build-vessels. Restore when it ships a
#                 self-contained binary.
# ``mesh`` is excluded until its pip git dependencies (hephaestus[mesh],
# telemachy register-epic) are merged to their main branches — the image
# build would fail in CI before then. Activation tracked in #713.
EXCLUDED_VESSELS = {"worker", "aider", "hello-world", "codebuff", "mesh"}


def _load_workflow() -> dict:
    """Load ci.yml and raise an informative error if it is missing or malformed."""
    if not CI_WORKFLOW.exists():
        pytest.fail(
            f"Workflow file not found: {CI_WORKFLOW}. "
            "This test cannot guard drift without it."
        )
    raw = CI_WORKFLOW.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        pytest.fail(
            f"Unexpected top-level type in {CI_WORKFLOW}: {type(data).__name__}. "
            "Expected a YAML mapping."
        )
    return data


def _get_smoke_matrix_vessels(workflow: dict) -> list[str]:
    """
    Extract the list of vessel ``name`` values from the test-smoke-vessels matrix.

    Raises pytest.fail (not KeyError/AttributeError) so the test output is clear.
    """
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        pytest.fail(
            f"'jobs' key missing or not a mapping in {CI_WORKFLOW}. "
            "Cannot locate the smoke matrix."
        )

    job = jobs.get(SMOKE_JOB_NAME)
    if job is None:
        pytest.fail(
            f"Job '{SMOKE_JOB_NAME}' not found in {CI_WORKFLOW}. "
            "Add the job or update SMOKE_JOB_NAME in this test."
        )

    strategy = job.get("strategy")
    if not isinstance(strategy, dict):
        pytest.fail(
            f"Job '{SMOKE_JOB_NAME}' has no 'strategy' key in {CI_WORKFLOW}. "
            "The matrix job must have a strategy.matrix.vessel list."
        )

    matrix = strategy.get("matrix")
    if not isinstance(matrix, dict):
        pytest.fail(
            f"Job '{SMOKE_JOB_NAME}' strategy has no 'matrix' key in {CI_WORKFLOW}."
        )

    vessel_rows = matrix.get("vessel")
    if not isinstance(vessel_rows, list) or len(vessel_rows) == 0:
        pytest.fail(
            f"Job '{SMOKE_JOB_NAME}' matrix.vessel is missing or empty in {CI_WORKFLOW}. "
            "Expected a list of vessel objects each with a 'name' field."
        )

    names: list[str] = []
    for row in vessel_rows:
        if not isinstance(row, dict) or "name" not in row:
            pytest.fail(
                f"Malformed matrix row in '{SMOKE_JOB_NAME}': {row!r}. "
                "Each row must be a mapping with at least a 'name' key."
            )
        names.append(row["name"])
    return names


def _vessel_dirs() -> list[str]:
    """Return vessel directory names (stems) under vessels/, excluding disabled ones."""
    vessels_path = REPO_ROOT / "vessels"
    if not vessels_path.is_dir():
        pytest.fail(f"vessels/ directory not found at {vessels_path}")
    return [
        d.name
        for d in sorted(vessels_path.iterdir())
        if d.is_dir() and d.name not in EXCLUDED_VESSELS
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_vessels_have_smoke_matrix_entry() -> None:
    """Every enabled vessel directory must appear in the test-smoke-vessels matrix."""
    workflow = _load_workflow()
    matrix_names = _get_smoke_matrix_vessels(workflow)

    # Strip the 'achaean-' prefix from matrix names to get the vessel slug
    # (e.g. 'achaean-claude' → 'claude') so we can compare with directory names.
    matrix_slugs = set()
    for name in matrix_names:
        if name.startswith("achaean-"):
            matrix_slugs.add(name[len("achaean-"):])
        else:
            matrix_slugs.add(name)

    vessel_dirs = _vessel_dirs()
    missing = [v for v in vessel_dirs if v not in matrix_slugs]

    assert not missing, (
        f"The following vessel directories are NOT in the '{SMOKE_JOB_NAME}' matrix:\n"
        + "\n".join(f"  vessels/{v}" for v in missing)
        + "\n\nAdd them to the matrix in .github/workflows/ci.yml, or add them to "
        "EXCLUDED_VESSELS in this test if they are intentionally excluded."
    )


def test_no_phantom_matrix_entries() -> None:
    """Every matrix entry must correspond to an existing vessel directory."""
    workflow = _load_workflow()
    matrix_names = _get_smoke_matrix_vessels(workflow)

    vessels_path = REPO_ROOT / "vessels"
    existing_dirs = {d.name for d in vessels_path.iterdir() if d.is_dir()}

    phantoms: list[str] = []
    for name in matrix_names:
        slug = name[len("achaean-"):] if name.startswith("achaean-") else name
        if slug not in existing_dirs:
            phantoms.append(name)

    assert not phantoms, (
        f"The following matrix entries in '{SMOKE_JOB_NAME}' have no matching "
        "vessel directory:\n"
        + "\n".join(f"  {n}" for n in phantoms)
        + "\n\nRemove the stale matrix entries from .github/workflows/ci.yml."
    )


def test_matrix_rows_have_required_fields() -> None:
    """Each matrix row must define name, program, version_flag, base, and dockerfile."""
    workflow = _load_workflow()
    strategy = workflow["jobs"][SMOKE_JOB_NAME]["strategy"]
    vessel_rows = strategy["matrix"]["vessel"]

    required_fields = {"name", "program", "version_flag", "base", "dockerfile"}
    incomplete: list[str] = []
    for row in vessel_rows:
        missing_fields = required_fields - set(row.keys())
        if missing_fields:
            incomplete.append(f"{row.get('name', '<unknown>')}: missing {missing_fields}")

    assert not incomplete, (
        f"Incomplete matrix rows in '{SMOKE_JOB_NAME}':\n"
        + "\n".join(f"  {m}" for m in incomplete)
    )
