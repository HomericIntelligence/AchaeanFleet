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

# Install OpenAI Codex CLI
ENV CODEX_VERSION=0.120.0
RUN npm install -g @openai/codex@${CODEX_VERSION}  # pinned for reproducibility — see #57

# Verify installation
RUN codex --version

USER agent

ENV AGENT_PROGRAM=codex
ENV AGENT_HEADLESS_FLAG=--yes
