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
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}

USER root

# Copy requirements.txt for reproducible dependency management
COPY requirements.txt /tmp/requirements.txt

# Install aider-chat (version pinned for reproducibility — issue #2)
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Verify installation
RUN aider --version

USER agent

ENV AGENT_PROGRAM=aider
ENV AGENT_HEADLESS_FLAG="--yes --message"
