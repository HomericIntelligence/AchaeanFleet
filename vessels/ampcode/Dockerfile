# AchaeanFleet Vessel: AmpCode (Sourcegraph Amp)
#
# Installs @sourcegraph/amp on top of the Node base image.

ARG BASE_IMAGE=achaean-base-node:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-ampcode"
LABEL org.opencontainers.image.description="AmpCode (Sourcegraph Amp) agent vessel"

USER root

# Install AmpCode CLI
ENV AMP_VERSION=0.0.1775866026-gd3abf3
RUN npm install -g @sourcegraph/amp@${AMP_VERSION}  # pinned for reproducibility — see #57

# Verify installation
RUN amp --version || true

USER agent

ENV AGENT_PROGRAM=amp
ENV AGENT_HEADLESS_FLAG=-x
