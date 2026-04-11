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
RUN pip install --no-cache-dir aider-chat

# Verify installation
RUN aider --version

USER agent

ENV AGENT_PROGRAM=aider
ENV AGENT_HEADLESS_FLAG="--yes --message"
