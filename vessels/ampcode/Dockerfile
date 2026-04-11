# AchaeanFleet Vessel: AmpCode (Sourcegraph Amp)
#
# Installs @sourcegraph/amp on top of the Node base image.

ARG BASE_IMAGE=achaean-base-node:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-ampcode"
LABEL org.opencontainers.image.description="AmpCode (Sourcegraph Amp) agent vessel"

USER root

# Install AmpCode CLI (version pinned for reproducibility — issue #2)
RUN npm install -g @sourcegraph/amp@0.0.1775866026-gd3abf3

# Verify installation
RUN amp --version || true

USER agent

ENV AGENT_PROGRAM=amp
ENV AGENT_HEADLESS_FLAG=-x
