# AchaeanFleet Vessel: Codebuff
#
# Installs codebuff on top of the Node base image.

ARG BASE_IMAGE=achaean-base-node:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-codebuff"
LABEL org.opencontainers.image.description="Codebuff AI coding agent vessel"

USER root

# Install Codebuff CLI
RUN npm install -g codebuff

# Verify installation
RUN codebuff --version || true

USER agent

ENV AGENT_PROGRAM=codebuff
# Codebuff headless mode is configured via SDK; no dedicated flag
ENV AGENT_HEADLESS_FLAG=""
