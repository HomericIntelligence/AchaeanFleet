"""Regression tests asserting all npm/pip installs in Dockerfiles are version-pinned.

Every `npm install -g` and `pip install` command must specify an exact version so
builds are reproducible.  See issue #57.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Repository root — two levels up from this file (tests/test_dockerfile_pins.py)
REPO_ROOT = Path(__file__).parent.parent

# Patterns that match an *unpinned* package token
NPM_INSTALL_LINE = re.compile(r"RUN\s+npm\s+install\s+-g\s+(.+)")
PIP_INSTALL_LINE = re.compile(r"RUN\s+pip\s+install\s+(.+)")

# A pinned npm package looks like:  name@version  or  @scope/name@version
NPM_PINNED = re.compile(r"^(@[\w-]+/)?[\w.-]+@[\w.\-+]+$")

# A pinned pip package looks like:  "pkg==1.2.3"  (quotes optional)
PIP_PINNED = re.compile(r'^"?[\w.\-]+==[.\w]+[^"]*"?$')


def collect_dockerfiles() -> list[Path]:
    """Return all Dockerfile paths under bases/ and vessels/."""
    paths: list[Path] = []
    paths.extend((REPO_ROOT / "bases").glob("Dockerfile.*"))
    paths.extend((REPO_ROOT / "vessels").rglob("Dockerfile"))
    return sorted(paths)


def _strip_comment(token: str) -> str:
    """Remove inline Dockerfile comment from a token."""
    return token.split("#")[0].strip()


def _expand_env(token: str, env_vars: dict[str, str]) -> str:
    """Expand simple ${VAR} references from preceding ENV declarations."""
    for var, val in env_vars.items():
        token = token.replace(f"${{{var}}}", val)
    return token


def check_dockerfile(path: Path) -> list[str]:
    """Return a list of violation strings for unpinned installs in *path*."""
    violations: list[str] = []
    env_vars: dict[str, str] = {}

    for lineno, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()

        # Track ENV declarations so we can expand ${VAR} in install commands
        if line.startswith("ENV "):
            parts = line[4:].strip().split("=", 1)
            if len(parts) == 2:
                env_vars[parts[0].strip()] = parts[1].strip()

        # Check: npm install -g <pkg>
        m = NPM_INSTALL_LINE.search(line)
        if m:
            pkg_raw = _strip_comment(m.group(1)).strip()
            pkg = _expand_env(pkg_raw, env_vars)
            if not NPM_PINNED.match(pkg):
                violations.append(
                    f"{path.relative_to(REPO_ROOT)}:{lineno}: "
                    f"unpinned npm package '{pkg_raw}' "
                    f"(expanded: '{pkg}') — add @version"
                )

        # Check: pip install … pkg (skip bare --upgrade pip lines)
        m = PIP_INSTALL_LINE.search(line)
        if m:
            args = _strip_comment(m.group(1)).strip()
            # Ignore pure pip self-upgrade: pip install --upgrade pip
            if re.fullmatch(r"--upgrade\s+pip", args):
                continue
            # Ignore requirements file installs: pip install -r <file>
            if re.search(r"-r\s+\S+", args):
                continue
            # Skip requirements-file installs: -r <file> pins are in the file itself
            if re.search(r"\s-r\s", f" {args}"):
                continue
            # Strip flags like --no-cache-dir
            tokens = [t for t in args.split() if not t.startswith("-")]
            for pkg_raw in tokens:
                pkg = _expand_env(pkg_raw, env_vars)
                if not PIP_PINNED.match(pkg):
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}:{lineno}: "
                        f"unpinned pip package '{pkg_raw}' "
                        f"(expanded: '{pkg}') — add ==version"
                    )

    return violations


DOCKERFILES = collect_dockerfiles()


@pytest.mark.parametrize("dockerfile", DOCKERFILES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_all_installs_are_pinned(dockerfile: Path) -> None:
    """Assert every npm/pip install in the Dockerfile specifies an exact version."""
    violations = check_dockerfile(dockerfile)
    assert not violations, (
        "Found unpinned package install(s) — add exact versions (see issue #57):\n"
        + "\n".join(f"  {v}" for v in violations)
    )
