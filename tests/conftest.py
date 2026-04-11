"""
Pytest configuration for AchaeanFleet Dockerfile static analysis tests.

Collects all Dockerfile paths so they can be parametrized across test functions.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


def collect_dockerfiles() -> list[Path]:
    """Return all Dockerfile paths in bases/ and vessels/ directories."""
    return sorted(REPO_ROOT.glob("**/Dockerfile*"))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "dockerfile: marks tests that statically analyse Dockerfiles"
    )
