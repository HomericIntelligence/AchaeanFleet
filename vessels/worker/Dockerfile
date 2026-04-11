# AchaeanFleet Vessel: Shell Worker
#
# A minimal shell worker with no AI tool installed.
# Used for CI tasks, scripting, and utility workloads.
# Based on the minimal Debian base image.

ARG BASE_IMAGE=achaean-base-minimal:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-worker"
LABEL org.opencontainers.image.description="Shell worker vessel — no AI tool, scripting and utility workloads"

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}

USER root

# Install required tools — failures here are fatal
RUN apt-get update && apt-get install -y jq make && rm -rf /var/lib/apt/lists/*

# Pinned yq version for reproducibility (issue #2). Update ENV to bump.
ENV YQ_VERSION=v4.52.5

# Install yq if not available via apt
RUN which yq || ( \
    curl -fsSL "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_amd64" \
        -o /usr/local/bin/yq && \
    chmod +x /usr/local/bin/yq )

USER agent

ENV AGENT_PROGRAM=none
ENV AGENT_HEADLESS_FLAG=""
