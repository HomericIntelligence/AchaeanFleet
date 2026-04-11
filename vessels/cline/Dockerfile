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
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}

USER root

# Install Cline CLI
ENV CLINE_VERSION=2.14.0
RUN npm install -g cline@${CLINE_VERSION}  # pinned for reproducibility — see #57

# Verify installation
RUN cline --version

USER agent

ENV AGENT_PROGRAM=cline
ENV AGENT_HEADLESS_FLAG=-y
