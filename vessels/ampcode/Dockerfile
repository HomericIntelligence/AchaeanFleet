# AchaeanFleet Vessel: AmpCode (Sourcegraph Amp)
#
# Installs @sourcegraph/amp on top of the Node base image.

ARG BASE_IMAGE=achaean-base-node:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-ampcode"
LABEL org.opencontainers.image.description="AmpCode (Sourcegraph Amp) agent vessel"

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}
LABEL git-sha=${GIT_SHA}

USER root

# Install AmpCode CLI (version pinned for reproducibility — issue #2)
RUN npm install -g @sourcegraph/amp@0.0.1775866026-gd3abf3

# Verify installation
RUN amp --version

USER agent

ENV AGENT_PROGRAM=amp
ENV AGENT_HEADLESS_FLAG=-x

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:23070/health 2>/dev/null || exit 1
