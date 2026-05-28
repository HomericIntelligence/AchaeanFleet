"""
Static analysis tests asserting that downloaded binaries are verified with SHA256 checksums.

These tests verify:
1. Both opencode and yq Dockerfiles contain sha256sum verification lines.
2. Each per-arch ARG <TOOL>_<ARCH>_SHA256 contains a valid 64-char hex SHA256.
3. The ARG default values match the corresponding entries in versions.yml.

Run with: pytest tests/test_dockerfile_sha256_pins.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent

# Valid SHA256 is exactly 64 hex characters
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)

# ARG line matching: ARG <VAR_NAME>=<value>
ARG_PATTERN = re.compile(r"^\s*ARG\s+(\w+)=([^\s]+)$", re.MULTILINE)

# sha256sum check line: echo "..." | sha256sum --check
SHA256SUM_CHECK_PATTERN = re.compile(r"echo\s+.*\|\s*sha256sum\s+--check")


def _extract_args_from_dockerfile(text: str) -> dict[str, str]:
    """Extract all ARG declarations from Dockerfile text as {name: value}."""
    args = {}
    for match in ARG_PATTERN.finditer(text):
        name, value = match.groups()
        args[name] = value
    return args


def _load_versions_yml() -> dict:
    """Load and parse versions.yml."""
    versions_file = REPO_ROOT / "versions.yml"
    with open(versions_file, "r") as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------------------
# Test 1: Both opencode and yq Dockerfiles have sha256sum --check
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rel_path",
    ["vessels/opencode/Dockerfile", "vessels/worker/Dockerfile"],
    ids=lambda p: p.split("/")[1],
)
def test_sha256sum_check_present(rel_path: str) -> None:
    """Dockerfile must contain a sha256sum --check line."""
    dockerfile = REPO_ROOT / rel_path
    if not dockerfile.exists():
        pytest.skip(f"{rel_path} does not exist")

    text = dockerfile.read_text()
    assert SHA256SUM_CHECK_PATTERN.search(text), (
        f"{rel_path}: missing 'sha256sum --check' verification line.\n"
        "Binary downloads must verify the SHA256 checksum before extraction/installation."
    )


# ---------------------------------------------------------------------------
# Test 2: Each per-arch ARG <TOOL>_<ARCH>_SHA256 is valid 64-char hex
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rel_path,expected_args",
    [
        (
            "vessels/opencode/Dockerfile",
            ["OPENCODE_AMD64_SHA256", "OPENCODE_ARM64_SHA256"],
        ),
        ("vessels/worker/Dockerfile", ["YQ_AMD64_SHA256", "YQ_ARM64_SHA256"]),
    ],
    ids=lambda p: p[0].split("/")[1] if isinstance(p, tuple) else "",
)
def test_sha256_arg_format_valid(rel_path: str, expected_args: list[str]) -> None:
    """Each per-arch ARG must be a valid 64-char hex SHA256."""
    dockerfile = REPO_ROOT / rel_path
    if not dockerfile.exists():
        pytest.skip(f"{rel_path} does not exist")

    text = dockerfile.read_text()
    args = _extract_args_from_dockerfile(text)

    violations = []
    for arg_name in expected_args:
        if arg_name not in args:
            violations.append(f"missing ARG {arg_name}")
            continue

        sha256_value = args[arg_name]
        if not SHA256_PATTERN.match(sha256_value):
            violations.append(
                f"ARG {arg_name}={sha256_value} is not a valid 64-char hex SHA256"
            )

    assert not violations, (
        f"{rel_path}: SHA256 ARG validation failed:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ---------------------------------------------------------------------------
# Test 3: Dockerfile ARG defaults match versions.yml
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rel_path,tool_name",
    [
        ("vessels/opencode/Dockerfile", "opencode"),
        ("vessels/worker/Dockerfile", "yq"),
    ],
    ids=lambda p: p[1],
)
def test_dockerfile_args_match_versions_yml(rel_path: str, tool_name: str) -> None:
    """Verify Dockerfile SHA256 ARGs match versions.yml entries."""
    dockerfile = REPO_ROOT / rel_path
    if not dockerfile.exists():
        pytest.skip(f"{rel_path} does not exist")

    text = dockerfile.read_text()
    dockerfile_args = _extract_args_from_dockerfile(text)
    versions = _load_versions_yml()

    tool_config = versions.get("tools", {}).get(tool_name)
    if not tool_config:
        pytest.skip(f"{tool_name} not found in versions.yml")

    checksums = tool_config.get("checksums", {})
    violations = []

    for arch in ["amd64", "arm64"]:
        arch_config = checksums.get(arch)
        if not arch_config:
            violations.append(f"versions.yml missing checksum for {arch}")
            continue

        yaml_sha256 = arch_config.get("sha256")
        if yaml_sha256 is None:
            violations.append(f"versions.yml has sha256: null for {arch}")
            continue

        # Map tool names and architectures to ARG names
        if tool_name == "opencode":
            arg_name = f"OPENCODE_{arch.upper()}_SHA256"
        elif tool_name == "yq":
            arg_name = f"YQ_{arch.upper()}_SHA256"
        else:
            violations.append(f"Unknown tool: {tool_name}")
            continue

        dockerfile_sha256 = dockerfile_args.get(arg_name)
        if dockerfile_sha256 is None:
            violations.append(f"Dockerfile missing ARG {arg_name}")
            continue

        if dockerfile_sha256 != yaml_sha256:
            violations.append(
                f"ARG {arg_name}={dockerfile_sha256} does not match "
                f"versions.yml {tool_name}.checksums.{arch}.sha256={yaml_sha256}"
            )

    assert not violations, (
        f"{rel_path} vs versions.yml consistency check failed:\n"
        + "\n".join(f"  {v}" for v in violations)
    )
