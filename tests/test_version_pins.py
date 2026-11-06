"""Assert that base-image tool pins are generated from versions.yml.

versions.yml is the single source of truth for the versions consumed by the
base Dockerfiles: scripts/render_version_pins.py writes each Dockerfile's
``ENV <TOOL>_VERSION`` block from it. These tests fail when the committed
blocks drift from the manifest — the failure mode that previously left
versions.yml at npm 11.18.0 while all three Dockerfiles installed 11.19.1.

Regenerate with: pixi run python scripts/render_version_pins.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
RENDER_SCRIPT = REPO_ROOT / "scripts" / "render_version_pins.py"
BEGIN_MARKER = "# BEGIN GENERATED TOOL PINS (source: versions.yml)"


def test_generated_pin_blocks_match_versions_yml() -> None:
    """Every base Dockerfile's generated block must equal versions.yml."""
    result = subprocess.run(
        [sys.executable, str(RENDER_SCRIPT), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "Base Dockerfile pins are out of sync with versions.yml.\n"
        "Regenerate with: pixi run python scripts/render_version_pins.py\n\n"
        f"{result.stdout}{result.stderr}"
    )


def test_every_base_dockerfile_declares_a_pin_block() -> None:
    """The renderer skips files without a block, so assert one is present."""
    dockerfiles = sorted((REPO_ROOT / "bases").glob("Dockerfile.*"))
    assert dockerfiles, "no base Dockerfiles found"

    missing = [
        path.name for path in dockerfiles if BEGIN_MARKER not in path.read_text()
    ]
    assert not missing, (
        f"base Dockerfiles missing the generated pin block: {missing}\n"
        f"Add '{BEGIN_MARKER}' .. '# END GENERATED TOOL PINS' where the pins go."
    )
