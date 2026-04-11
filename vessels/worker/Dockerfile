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

# Install additional tools useful for shell workers (yq may not be in apt on all distros)
RUN apt-get update && apt-get install -y \
    jq \
    make \
    && rm -rf /var/lib/apt/lists/*

# Install yq via direct binary download if not already available
RUN which yq \
    || ( \
        curl -fsSL "https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64" \
            -o /usr/local/bin/yq \
        && chmod +x /usr/local/bin/yq \
    )

# Verify yq is present
RUN yq --version

USER agent

ENV AGENT_PROGRAM=none
ENV AGENT_HEADLESS_FLAG=""
