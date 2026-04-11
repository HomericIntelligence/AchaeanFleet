"""
Static analysis tests asserting that every Dockerfile in AchaeanFleet pins
its tool installations to an exact version.

These tests require no Docker daemon — they parse Dockerfile text only.
Run with: pytest tests/ -v

Covered patterns
----------------
* npm install -g <pkg>        → must have @<version> suffix
* pip install <pkg>           → must have ==<version> specifier
* curl .../releases/latest/   → must NOT appear (use pinned ENV var instead)
* Binary curl-installers      → must be preceded by an ENV <TOOL>_VERSION= declaration
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent

# Globs that find all Dockerfiles in the repo
_DOCKERFILE_GLOBS = ["bases/Dockerfile*", "vessels/*/Dockerfile"]


def _find_dockerfiles() -> list[Path]:
    """Return sorted list of all Dockerfile paths."""
    paths: list[Path] = []
    for pattern in _DOCKERFILE_GLOBS:
        paths.extend(REPO_ROOT.glob(pattern))
    return sorted(paths)


def _relative(path: Path) -> str:
    """Return path relative to repo root for readable test IDs."""
    return str(path.relative_to(REPO_ROOT))


# Pre-collect so parametrize decorators work at collection time
ALL_DOCKERFILES = _find_dockerfiles()


# ---------------------------------------------------------------------------
# npm install -g version-pin assertions
# ---------------------------------------------------------------------------

# Matches lines like: RUN npm install -g <pkg>  (with optional flags before the pkg)
_NPM_INSTALL_RE = re.compile(
    r"npm\s+install\s+(?:-g\s+|--global\s+)"  # npm install -g / --global
    r"(?P<packages>[^\\\n]+)",                 # everything until line-end or continuation
)

# A scoped package (@scope/name) must end with @<version> i.e. two '@' chars.
# An unscoped package (name) must end with @<version> i.e. one '@' after the name.
_SCOPED_PKG_VERSION_RE = re.compile(r"^@[^@]+/[^@]+@\S+$")   # @scope/name@version
_PLAIN_PKG_VERSION_RE = re.compile(r"^[^@]\S*@\S+$")          # name@version


def _npm_package_is_pinned(pkg: str) -> bool:
    """Return True if the npm package token contains an explicit version pin."""
    pkg = pkg.strip()
    if not pkg:
        return True  # ignore empty tokens
    if pkg.startswith("@"):
        return bool(_SCOPED_PKG_VERSION_RE.match(pkg))
    return bool(_PLAIN_PKG_VERSION_RE.match(pkg))


@pytest.mark.parametrize("dockerfile", ALL_DOCKERFILES, ids=_relative)
def test_npm_installs_are_pinned(dockerfile: Path) -> None:
    """Every 'npm install -g' line must specify an exact version for each package."""
    text = dockerfile.read_text()
    unpinned: list[str] = []

    for match in _NPM_INSTALL_RE.finditer(text):
        packages_str = match.group("packages")
        # Split on whitespace; drop flags (starting with -)
        tokens = [t for t in packages_str.split() if not t.startswith("-")]
        for token in tokens:
            if not _npm_package_is_pinned(token):
                unpinned.append(token)

    assert not unpinned, (
        f"{_relative(dockerfile)}: unpinned npm packages found: {unpinned}\n"
        "Pin with: npm install -g <pkg>@<exact-version>"
    )


# ---------------------------------------------------------------------------
# pip install version-pin assertions
# ---------------------------------------------------------------------------

# Matches pip install lines that name a package (not flags-only lines).
# We look for any word that looks like a bare package name without ==.
_PIP_INSTALL_RE = re.compile(r"pip\s+install\s+(?P<args>[^\\\n]+)")

# Tokens that are flags or known non-package arguments — skip these
_PIP_FLAG_RE = re.compile(r"^-|^--")

# Upgrade-only invocations that *do* need a version (pip install --upgrade pip)
_PIP_BARE_PACKAGE_RE = re.compile(r"^[A-Za-z0-9][\w\-\.]*$")


def _pip_token_is_pinned(token: str) -> bool:
    """Return True if a pip token is either a flag/option or a pinned specifier."""
    token = token.strip().strip('"').strip("'")
    if not token:
        return True
    if _PIP_FLAG_RE.match(token):
        return True  # it's a flag, not a package
    # If it looks like a bare package name (no version specifier), it's unpinned
    if _PIP_BARE_PACKAGE_RE.match(token):
        return False
    # Has a specifier (==, >=, <=, ~=, !=, [extra], etc.) → pinned or constrained
    return True


@pytest.mark.parametrize("dockerfile", ALL_DOCKERFILES, ids=_relative)
def test_pip_installs_are_pinned(dockerfile: Path) -> None:
    """Every 'pip install' line naming a package must use == exact version pinning."""
    text = dockerfile.read_text()
    unpinned: list[str] = []

    for match in _PIP_INSTALL_RE.finditer(text):
        args_str = match.group("args")
        tokens = args_str.split()
        for token in tokens:
            if not _pip_token_is_pinned(token):
                unpinned.append(token)

    assert not unpinned, (
        f"{_relative(dockerfile)}: unpinned pip packages found: {unpinned}\n"
        'Pin with: pip install "pkg==<exact-version>"'
    )


# ---------------------------------------------------------------------------
# No /releases/latest/ in curl download URLs
# ---------------------------------------------------------------------------

_RELEASES_LATEST_RE = re.compile(r"releases/latest/download/")


@pytest.mark.parametrize("dockerfile", ALL_DOCKERFILES, ids=_relative)
def test_no_latest_release_downloads(dockerfile: Path) -> None:
    """curl download URLs must not use /releases/latest/ — use a pinned ENV version."""
    text = dockerfile.read_text()
    matches = _RELEASES_LATEST_RE.findall(text)
    assert not matches, (
        f"{_relative(dockerfile)}: found {len(matches)} use(s) of "
        "'/releases/latest/download/' — replace with a pinned ENV TOOL_VERSION=x.y.z"
    )


# ---------------------------------------------------------------------------
# Binary curl-installers must be preceded by an ENV <TOOL>_VERSION declaration
# ---------------------------------------------------------------------------

# Known binary tool ENV variables that should gate their curl installer blocks
_EXPECTED_VERSION_ENVS = {
    "vessels/goose/Dockerfile": "GOOSE_VERSION",
    "vessels/opencode/Dockerfile": "OPENCODE_VERSION",
    "vessels/worker/Dockerfile": "YQ_VERSION",
}


@pytest.mark.parametrize(
    "rel_path,env_var",
    list(_EXPECTED_VERSION_ENVS.items()),
    ids=list(_EXPECTED_VERSION_ENVS.keys()),
)
def test_binary_installer_has_version_env(rel_path: str, env_var: str) -> None:
    """Curl-installer vessel Dockerfiles must declare an ENV <TOOL>_VERSION variable."""
    dockerfile = REPO_ROOT / rel_path
    if not dockerfile.exists():
        pytest.skip(f"{rel_path} does not exist")
    text = dockerfile.read_text()
    assert f"ENV {env_var}=" in text, (
        f"{rel_path}: missing 'ENV {env_var}=<version>' declaration.\n"
        "Binary curl-installers must pin their version via an ENV variable."
    )


# ---------------------------------------------------------------------------
# Sanity: every expected Dockerfile actually exists
# ---------------------------------------------------------------------------

_EXPECTED_DOCKERFILES = [
    "bases/Dockerfile.minimal",
    "bases/Dockerfile.node",
    "bases/Dockerfile.python",
    "vessels/claude/Dockerfile",
    "vessels/aider/Dockerfile",
    "vessels/ampcode/Dockerfile",
    "vessels/cline/Dockerfile",
    "vessels/codebuff/Dockerfile",
    "vessels/codex/Dockerfile",
    "vessels/goose/Dockerfile",
    "vessels/opencode/Dockerfile",
    "vessels/worker/Dockerfile",
]


@pytest.mark.parametrize("rel_path", _EXPECTED_DOCKERFILES)
def test_expected_dockerfiles_exist(rel_path: str) -> None:
    """Every expected Dockerfile must be present in the repository."""
    assert (REPO_ROOT / rel_path).exists(), (
        f"Expected Dockerfile not found: {rel_path}"
    )
