# AchaeanFleet Vessel: Cline
#
# Installs cline on top of the Node base image.

ARG BASE_IMAGE=achaean-base-node:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-cline"
LABEL org.opencontainers.image.description="Cline AI coding agent vessel"

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}
LABEL git-sha=${GIT_SHA}

USER root

# Install Cline CLI (version pinned for reproducibility — issue #2)
RUN npm install -g cline@2.14.0

# Verify installation
RUN cline --version

USER agent

ENV AGENT_PROGRAM=cline
ENV AGENT_HEADLESS_FLAG=-y

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:23040/health 2>/dev/null || exit 1
