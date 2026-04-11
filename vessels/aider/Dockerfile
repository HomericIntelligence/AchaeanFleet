# AchaeanFleet Vessel: Aider
#
# Installs aider-chat on top of the Python base image.
# Supports Python 3.9-3.12; this image uses 3.12.

ARG BASE_IMAGE=achaean-base-python:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-aider"
LABEL org.opencontainers.image.description="Aider AI coding assistant vessel"

USER root

# Install aider-chat
ENV AIDER_VERSION=0.82.3
RUN pip install --no-cache-dir "aider-chat==${AIDER_VERSION}"  # pinned for reproducibility — see #57

# Verify installation
RUN aider --version || true

USER agent

ENV AGENT_PROGRAM=aider
ENV AGENT_HEADLESS_FLAG="--yes --message"
