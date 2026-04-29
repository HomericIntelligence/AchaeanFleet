# AchaeanFleet Vessel: Aider
#
# Installs aider-chat on top of the Python base image.
# Supports Python 3.9-3.12; this image uses 3.12.

ARG BASE_IMAGE=achaean-base-python:latest
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

# Copy requirements.txt for reproducible dependency management
COPY vessels/aider/requirements.txt /tmp/requirements.txt

# Install aider-chat (version pinned for reproducibility — issue #2)
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Verify installation
RUN aider --version

USER agent

ENV AGENT_PROGRAM=aider
ENV AGENT_HEADLESS_FLAG="--yes --message"

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:23020/health 2>/dev/null || exit 1
