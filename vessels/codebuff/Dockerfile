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
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}

USER root

# Install Codebuff CLI
ENV CODEBUFF_VERSION=1.0.638
RUN npm install -g codebuff@${CODEBUFF_VERSION}  # pinned for reproducibility — see #57

# Verify installation
RUN codebuff --version

USER agent

ENV AGENT_PROGRAM=codebuff
# Codebuff headless mode is configured via SDK; no dedicated flag
ENV AGENT_HEADLESS_FLAG=""
