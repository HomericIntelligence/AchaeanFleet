"""
Tests for cap_drop=ALL validation of the achaean-claude vessel.

Unit tests cover the failure-classification logic that decides whether a
non-zero exit code is a capability gap, an env/harness error, or a timeout.

Integration test (gated on RUN_INTEGRATION=1 and Docker being reachable) runs
``claude --version`` inside a fresh achaean-claude:latest container with
``--cap-drop=ALL --security-opt=no-new-privileges`` and asserts exit 0.

Related: issue #305, scripts/validate_claude_caps.sh, nomad/PATTERNS.md §Capability validation
"""

from __future__ import annotations

import os
import re
import subprocess
import shutil

import pytest

# ---------------------------------------------------------------------------
# Failure classification logic (mirrors scripts/validate_claude_caps.sh)
# ---------------------------------------------------------------------------

_CAP_ERROR_PATTERN = re.compile(
    r"EPERM|Operation not permitted|capset|prctl|permission denied",
    re.IGNORECASE,
)


def classify_failure(stderr: str, exit_code: int) -> str:
    """
    Classify the outcome of a ``docker run --cap-drop=ALL`` probe.

    Returns one of:
      "pass"       — exit_code == 0
      "capability" — exit_code != 0 AND stderr matches a capability-shaped error
      "timeout"    — exit_code == 124 (timeout(1) sentinel)
      "env"        — exit_code != 0 AND no cap-shaped stderr (harness / image error)
    """
    if exit_code == 0:
        return "pass"
    if exit_code == 124:
        return "timeout"
    if _CAP_ERROR_PATTERN.search(stderr):
        return "capability"
    return "env"


# ---------------------------------------------------------------------------
# Unit tests — classify_failure
# ---------------------------------------------------------------------------


class TestClassifyFailure:
    def test_exit_zero_is_pass(self) -> None:
        assert classify_failure("", 0) == "pass"

    def test_eperm_stderr_is_capability(self) -> None:
        assert classify_failure("failed: Operation not permitted", 1) == "capability"

    def test_eperm_acronym_is_capability(self) -> None:
        assert classify_failure("capset: EPERM", 1) == "capability"

    def test_prctl_is_capability(self) -> None:
        assert classify_failure("prctl PR_SET_NO_NEW_PRIVS failed", 1) == "capability"

    def test_permission_denied_is_capability(self) -> None:
        assert classify_failure("/usr/bin/claude: permission denied", 1) == "capability"

    def test_capset_is_capability(self) -> None:
        assert classify_failure("capset failed: Operation not permitted", 1) == "capability"

    def test_auth_error_is_env(self) -> None:
        # API auth failures are unrelated to capabilities
        assert classify_failure("Error: Invalid API key", 1) == "env"

    def test_missing_binary_is_env(self) -> None:
        assert classify_failure("executable file not found in $PATH", 127) == "env"

    def test_timeout_sentinel(self) -> None:
        assert classify_failure("", 124) == "timeout"

    def test_empty_stderr_nonzero_is_env(self) -> None:
        assert classify_failure("", 1) == "env"

    def test_case_insensitive_permission_denied(self) -> None:
        assert classify_failure("Permission Denied", 1) == "capability"


# ---------------------------------------------------------------------------
# Integration test — requires Docker + achaean-claude:latest image
# ---------------------------------------------------------------------------


def _docker_available() -> bool:
    return shutil.which("docker") is not None and subprocess.call(
        ["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ) == 0


def _image_available(image: str) -> bool:
    return subprocess.call(
        ["docker", "image", "inspect", image],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ) == 0


_INTEGRATION_REASON = (
    "integration test requires RUN_INTEGRATION=1 env var, "
    "a reachable Docker daemon, and achaean-claude:latest to be built"
)

_IMAGE = "achaean-claude:latest"


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1"
    or not _docker_available()
    or not _image_available(_IMAGE),
    reason=_INTEGRATION_REASON,
)
def test_claude_version_passes_under_cap_drop_all() -> None:
    """achaean-claude:latest should start correctly under cap_drop=ALL."""
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--entrypoint=",
            _IMAGE,
            "claude",
            "--version",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    failure_class = classify_failure(result.stderr, result.returncode)
    assert result.returncode == 0, (
        f"claude --version exited {result.returncode} under cap_drop=ALL\n"
        f"failure_class={failure_class}\n"
        f"stdout={result.stdout!r}\n"
        f"stderr={result.stderr!r}\n"
        "If failure_class='capability', identify the required cap via capabilities(7) "
        "and add cap_add to nomad/mesh.nomad.hcl with a justification comment."
    )
    assert failure_class == "pass"
