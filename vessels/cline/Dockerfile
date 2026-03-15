# AchaeanFleet Vessel: Cline
#
# Installs cline on top of the Node base image.

ARG BASE_IMAGE=achaean-base-node:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-cline"
LABEL org.opencontainers.image.description="Cline AI coding agent vessel"

USER root

# Install Cline CLI
RUN npm install -g cline

# Verify installation
RUN cline --version || true

USER agent

ENV AGENT_PROGRAM=cline
ENV AGENT_HEADLESS_FLAG=-y
