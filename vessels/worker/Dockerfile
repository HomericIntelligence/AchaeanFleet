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
RUN apt-get update && apt-get install -y --no-install-recommends \
    jq \
    yq \
    make \
    && rm -rf /var/lib/apt/lists/* || true

# Install yq if not available via apt — pinned version with SHA256 verification (no unverified download)
ARG YQ_VERSION=4.52.5
ARG YQ_SHA256=75d893a0d5940d1019cb7cdc60001d9e876623852c31cfc6267047bc31149fa9
RUN which yq || ( \
    curl -fsSL \
        "https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}/yq_linux_amd64" \
        -o /tmp/yq && \
    echo "${YQ_SHA256}  /tmp/yq" | sha256sum --check && \
    install -m 755 /tmp/yq /usr/local/bin/yq && \
    rm /tmp/yq )

USER agent

ENV AGENT_PROGRAM=none
ENV AGENT_HEADLESS_FLAG=""
