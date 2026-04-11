# AchaeanFleet Vessel: OpenAI Codex
#
# Installs @openai/codex on top of the Node base image.

ARG BASE_IMAGE=achaean-base-node:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-codex"
LABEL org.opencontainers.image.description="OpenAI Codex agent vessel"

USER root

# Install OpenAI Codex CLI
ENV CODEX_VERSION=0.120.0
RUN npm install -g @openai/codex@${CODEX_VERSION}  # pinned for reproducibility — see #57

# Verify installation
RUN codex --version || true

USER agent

ENV AGENT_PROGRAM=codex
ENV AGENT_HEADLESS_FLAG=--yes
