# AchaeanFleet Vessel: Claude Code
#
# Installs @anthropic-ai/claude-code on top of the Node base image.
# Compatible with the HomericIntelligence agent mesh.

ARG BASE_IMAGE=achaean-base-node:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-claude"
LABEL org.opencontainers.image.description="Claude Code agent vessel"

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}
LABEL git-sha=${GIT_SHA}

USER root

# Install Claude Code CLI (version pinned for reproducibility — issue #2)
RUN npm install -g @anthropic-ai/claude-code@2.1.101

# Install GitHub CLI (needed for issue/PR operations)
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
      | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && apt-get update && apt-get install -y gh && rm -rf /var/lib/apt/lists/*

# Verify installation
RUN claude --version
RUN gh --version

USER agent

ENV AGENT_PROGRAM=claude-code
ENV AGENT_HEADLESS_FLAG=-p

# Runtime: Agamemnon agent sidecar starts claude with -p flag in tmux
