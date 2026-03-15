# AchaeanFleet Vessel: Claude Code
#
# Installs @anthropic-ai/claude-code on top of the Node base image.
# Compatible with ai-maestro's agent-server.js.

ARG BASE_IMAGE=achaean-base-node:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-claude"
LABEL org.opencontainers.image.description="Claude Code agent vessel"

USER root

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Verify installation
RUN claude --version || true

USER agent

ENV AGENT_PROGRAM=claude-code
ENV AGENT_HEADLESS_FLAG=-p

# Runtime: agent-server.js starts claude with -p flag in tmux
