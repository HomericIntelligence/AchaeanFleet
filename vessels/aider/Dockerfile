# AchaeanFleet Vessel: Aider
#
# aider-chat releases up to 0.86.x require Python ">=3.10,<3.13", but the
# achaean-base-python image runs Python 3.14. To keep the shared base while
# satisfying aider's interpreter constraint, we copy a self-contained
# Python 3.12 from the official python:3.12-slim image into /opt/python3.12
# and install aider-chat into a venv built with that interpreter.
#
# This avoids forking a separate base image just for aider and keeps the rest
# of the agent setup (user, tmux, oh-my-zsh, entrypoint) inherited from the
# shared base.

# Global ARG must be declared before the first FROM so it can be referenced
# by later FROM stages (Docker scopes ARGs declared between FROMs to that stage
# only).
ARG BASE_IMAGE=achaean-base-python:latest

# Source stage — provides a complete Python 3.12 install we can copy whole.
# NOTE: must be python:3.12-slim (NOT the 3.14 base digest) — aider-chat
# requires >=3.10,<3.13 and the RUN below invokes /opt/python3.12/bin/python3.12.
FROM python:3.12-slim@sha256:876416ecde9aca2bcc90e1fb0c7a9500bbf749f5788b70f82d4c5a5c2357f8b4 AS python312-source

# Upgrade pip in the SOURCE stage (before COPY): `pip install --upgrade pip`
# in-place self-replacement races on python 3.12 (OSError: [Errno 39]
# Directory not empty on site-packages/pip/_internal/commands), so use
# --ignore-installed (no silent-failure idiom) and purge the stale 25.0.1
# dist-info so the scan reports a single clean pip.
RUN python3 -m pip install --no-cache-dir --upgrade --ignore-installed "pip==26.0.1" \
    && rm -rf /usr/local/lib/python3.12/site-packages/pip-25.0.1.dist-info

FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-aider"
LABEL org.opencontainers.image.description="Aider AI coding assistant vessel"

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}
LABEL git-sha=${GIT_SHA}

USER root

# Bring Python 3.12 in as a self-contained install at /opt/python3.12 so the
# venv we build below has a real interpreter to point at, independent of the
# base image's Python 3.14.
COPY --from=python312-source /usr/local /opt/python3.12

# Copy requirements files for reproducible dependency management.
# The security-overrides file is consumed by a second `pip install --upgrade`
# pass below because aider-chat hard-pins older CVE-affected versions of
# GitPython/Pillow/urllib3; a single resolver pass cannot satisfy both
# aider's pins and the upgrade constraints (ResolutionImpossible).
COPY vessels/aider/requirements.txt /tmp/requirements.txt
COPY vessels/aider/requirements-security-overrides.txt /tmp/requirements-security-overrides.txt

# Create an isolated venv with Python 3.12 and install aider-chat into it,
# then force-upgrade the CVE-affected transitive deps in a second pass.
# We expose `aider` on PATH via a symlink so existing AGENT_PROGRAM=aider
# wiring continues to work without changes elsewhere.
RUN /opt/python3.12/bin/python3.12 -m venv --upgrade-deps /opt/aider-venv \
    && /opt/aider-venv/bin/pip install --no-cache-dir --upgrade "pip==26.0.1" \
    && /opt/aider-venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt \
    && /opt/aider-venv/bin/pip install --no-cache-dir --upgrade -r /tmp/requirements-security-overrides.txt \
    && ln -sf /opt/aider-venv/bin/aider /usr/local/bin/aider \
    && rm /tmp/requirements.txt /tmp/requirements-security-overrides.txt

# filelock 3.20.3 -> 4.2.1   CVE-2026-112940 (arbitrary file overwrite)
#
# Two upstream constraints keep filelock on the 3.x line: aider-chat 0.86.2
# requires filelock==3.20.3 and litellm 1.108.1 requires filelock<4.0. No
# released version of either lifts them, so the upgrade pass above can only
# reach 3.32.7, which is still affected. --no-deps installs 4.2.1 anyway.
#
# That is the same tradeoff this image already makes for aider's other exact
# pins (aiohttp==3.13.3, anyio==4.12.1, certifi==2026.1.4, fsspec==2026.2.0 are
# all overridden by the file above). It is safe for filelock specifically
# because nothing in the aider wheel imports it — the equality pin is vestigial
# metadata — and filelock 4.2.1 still exports the FileLock / SoftFileLock /
# Timeout API that litellm's proxy-client CLI and huggingface-hub call, which
# the smoke check below exercises.
RUN /opt/aider-venv/bin/pip install --no-cache-dir --no-deps --upgrade "filelock==4.2.1" \
    && /opt/aider-venv/bin/python -c "import filelock, os, tempfile; \
assert filelock.__version__ == '4.2.1', filelock.__version__; \
directory = tempfile.mkdtemp(); path = os.path.join(directory, 'cache.lock'); \
lock = filelock.FileLock(path); lock.acquire(); assert os.path.exists(path); lock.release(); \
assert hasattr(filelock, 'SoftFileLock') and hasattr(filelock, 'Timeout')"

# Verify installation
RUN aider --version

USER agent

ENV AGENT_PROGRAM=aider
ENV AGENT_HEADLESS_FLAG="--yes --message"

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:23020/health 2>/dev/null || exit 1
