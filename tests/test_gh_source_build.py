"""Static analysis tests for the source-built GitHub CLI in achaean-claude.

Issue #779: the apt gh package vendors golang.org/x/mod v0.37.0 with HIGH
CVE-2026-56864 / CVE-2026-56865 (fixed in v0.40.0). The vessel must build gh
from source at a pinned release tag with the patched module and assert the
patched module is embedded via a build-time guard. The temporary .trivyignore
entries for those CVEs must never reappear once the rebuilt image scans clean.

These tests require no Docker daemon — they parse Dockerfile text only.
Run with: pytest tests/test_gh_source_build.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent

CLAUDE_DOCKERFILE = REPO_ROOT / "vessels" / "claude" / "Dockerfile"
TRIVYIGNORE = REPO_ROOT / ".trivyignore"

# The patched golang.org/x/mod version that clears both CVEs.
X_MOD_VERSION = "v0.40.0"


@pytest.fixture()
def claude_dockerfile_text() -> str:
    """Return the text of the achaean-claude vessel Dockerfile."""
    return CLAUDE_DOCKERFILE.read_text()


# ---------------------------------------------------------------------------
# Builder stage
# ---------------------------------------------------------------------------


def test_gh_builder_stage_exists(claude_dockerfile_text: str) -> None:
    """The Dockerfile must define an 'gh-builder' stage."""
    assert re.search(
        r"^FROM \S+ AS gh-builder$", claude_dockerfile_text, re.MULTILINE
    ), "vessels/claude/Dockerfile: missing 'FROM ... AS gh-builder' stage"


def test_gh_builder_image_is_digest_pinned(claude_dockerfile_text: str) -> None:
    """The golang builder image FROM must be pinned by digest, not a moving tag."""
    from_match = re.search(r"^FROM (\S+) AS gh-builder", claude_dockerfile_text, re.MULTILINE)
    assert from_match is not None
    image_ref = from_match.group(1)
    assert "@sha256:" in image_ref, (
        f"gh-builder image '{image_ref}' is not digest-pinned; "
        "pin like golang:<tag>@sha256:<digest>"
    )


def test_gh_version_arg_is_pinned(claude_dockerfile_text: str) -> None:
    """ARG GH_VERSION must pin an exact cli/cli release tag."""
    match = re.search(r"^ARG GH_VERSION=(\S+)$", claude_dockerfile_text, re.MULTILINE)
    assert match is not None, "missing 'ARG GH_VERSION=<tag>' declaration"
    assert re.fullmatch(r"v\d+\.\d+\.\d+", match.group(1)), (
        f"GH_VERSION '{match.group(1)}' is not an exact release tag (vX.Y.Z)"
    )


def test_x_mod_version_arg_pins_patched_module(claude_dockerfile_text: str) -> None:
    """ARG X_MOD_VERSION must pin golang.org/x/mod at or above the patched version."""
    match = re.search(r"^ARG X_MOD_VERSION=(\S+)$", claude_dockerfile_text, re.MULTILINE)
    assert match is not None, "missing 'ARG X_MOD_VERSION=<tag>' declaration"
    pinned = match.group(1)

    def _semver(version: str) -> tuple[int, int, int]:
        return tuple(int(part) for part in version.lstrip("v").split("."))  # type: ignore[return-value]

    assert _semver(pinned) >= _semver(X_MOD_VERSION), (
        f"X_MOD_VERSION {pinned} does not include the fix for "
        f"CVE-2026-56864/CVE-2026-56865 (needs >={X_MOD_VERSION})"
    )


# ---------------------------------------------------------------------------
# Build-time guard: patched module must be provably embedded in the binary
# ---------------------------------------------------------------------------


def test_build_guard_verifies_embedded_x_mod(claude_dockerfile_text: str) -> None:
    """The builder RUN must inspect the binary's build info for golang.org/x/mod."""
    assert "go version -m" in claude_dockerfile_text, (
        "builder must run 'go version -m' on the built binary to prove the "
        "vendored golang.org/x/mod version"
    )
    assert "golang.org/x/mod" in claude_dockerfile_text


def test_no_apt_github_cli_install_remains(claude_dockerfile_text: str) -> None:
    """The apt githubcli repo install must not return."""
    assert "githubcli-archive-keyring.gpg" not in claude_dockerfile_text, (
        "apt-based gh install reintroduced — keep the source build (issue #779)"
    )
    assert not re.search(
        r"apt-get install[^\n]*\bgh\b", claude_dockerfile_text
    ), "apt-get install of gh found — use COPY --from=gh-builder instead"


def test_binary_copied_to_usr_bin_gh(claude_dockerfile_text: str) -> None:
    """The built binary must be installed at /usr/bin/gh (the scanned path)."""
    assert "COPY --from=gh-builder /out/gh /usr/bin/gh" in claude_dockerfile_text


# ---------------------------------------------------------------------------
# Allowlist regression guard: suppression must never replace the root fix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cve", ["CVE-2026-56864", "CVE-2026-56865"])
def test_trivyignore_has_no_gh_x_mod_entries(cve: str) -> None:
    """CVE-2026-56864/56865 allowlist entries must stay removed from .trivyignore.

    These were temporary suppressions (expiring 2026-10-12) for golang.org/x/mod
    vendored in gh. The root-cause fix is the source rebuild; the issue
    explicitly forbids closing by dismissing findings.
    """
    if not TRIVYIGNORE.exists():
        pytest.skip(".trivyignore does not exist")
    lines = TRIVYIGNORE.read_text().splitlines()
    offenders = [
        line for line in lines if line.strip() == cve
    ]
    assert not offenders, (
        f".trivyignore contains a bare '{cve}' entry; the gh x/mod CVEs are "
        f"fixed by the source rebuild (issue #779) — do not suppress them"
    )
