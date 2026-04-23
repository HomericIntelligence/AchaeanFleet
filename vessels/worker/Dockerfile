# AchaeanFleet Vessel: Shell Worker
#
# A minimal shell worker with no AI tool installed.
# Used for CI tasks, scripting, and utility workloads.
# Based on the minimal Debian base image.

ARG BASE_IMAGE=achaean-base-minimal:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-worker"
LABEL org.opencontainers.image.description="Shell worker vessel — no AI tool, scripting and utility workloads"

USER root

# Install additional tools useful for shell workers
RUN apt-get update && apt-get install -y \
    jq \
    yq \
    make \
    && rm -rf /var/lib/apt/lists/*

# Install yq if not available via apt
RUN which yq || \
    curl -fsSL "https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64" \
        -o /usr/local/bin/yq && \
    chmod +x /usr/local/bin/yq

USER agent

ENV AGENT_PROGRAM=none
ENV AGENT_HEADLESS_FLAG=""
