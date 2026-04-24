# AchaeanFleet Vessel: Codebuff
#
# Installs codebuff on top of the Node base image.

ARG BASE_IMAGE=achaean-base-node:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-codebuff"
LABEL org.opencontainers.image.description="Codebuff AI coding agent vessel"

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}
LABEL git-sha=${GIT_SHA}

USER root

# Install Codebuff CLI (version pinned for reproducibility — issue #2)
RUN npm install -g codebuff@1.0.638

# Verify installation
RUN codebuff --version

USER agent

ENV AGENT_PROGRAM=codebuff
# Codebuff headless mode is configured via SDK; no dedicated flag
ENV AGENT_HEADLESS_FLAG=""

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:23060/health 2>/dev/null || exit 1
