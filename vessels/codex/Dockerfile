# AchaeanFleet Vessel: OpenAI Codex
#
# Installs @openai/codex on top of the Node base image.

ARG BASE_IMAGE=achaean-base-node:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-codex"
LABEL org.opencontainers.image.description="OpenAI Codex agent vessel"

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}

USER root

# Install OpenAI Codex CLI (version pinned for reproducibility — issue #2)
RUN npm install -g @openai/codex@0.120.0

# Verify installation
RUN codex --version

USER agent

ENV AGENT_PROGRAM=codex
ENV AGENT_HEADLESS_FLAG=--yes

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:23010/health 2>/dev/null || exit 1
