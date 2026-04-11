# AchaeanFleet Vessel: AmpCode (Sourcegraph Amp)
#
# Installs @sourcegraph/amp on top of the Node base image.

ARG BASE_IMAGE=achaean-base-node:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-ampcode"
LABEL org.opencontainers.image.description="AmpCode (Sourcegraph Amp) agent vessel"

USER root

# Install AmpCode CLI
RUN npm install -g @sourcegraph/amp

# Verify installation
RUN amp --version

USER agent

ENV AGENT_PROGRAM=amp
ENV AGENT_HEADLESS_FLAG=-x
