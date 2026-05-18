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
FROM python:3.12-slim@sha256:ec948fa5f90f4f8907e89f4800cfd2d2e91e391a4bce4a6afa77ba265bc3a2fe AS python312-source

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
RUN /opt/python3.12/bin/python3.12 -m venv /opt/aider-venv \
    && /opt/aider-venv/bin/pip install --no-cache-dir --upgrade "pip==26.0.1" \
    && /opt/aider-venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt \
    && /opt/aider-venv/bin/pip install --no-cache-dir --upgrade -r /tmp/requirements-security-overrides.txt \
    && ln -sf /opt/aider-venv/bin/aider /usr/local/bin/aider \
    && rm /tmp/requirements.txt /tmp/requirements-security-overrides.txt

# Verify installation
RUN aider --version

USER agent

ENV AGENT_PROGRAM=aider
ENV AGENT_HEADLESS_FLAG="--yes --message"

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:23020/health 2>/dev/null || exit 1
