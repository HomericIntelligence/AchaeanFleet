# AchaeanFleet Vessel: OpenCode
#
# Installs OpenCode Go binary on top of the minimal Debian base image.
# Uses a multi-stage build: the builder stage downloads and extracts the
# OpenCode binary; only the binary is copied into the runtime image.

ARG BASE_IMAGE=achaean-base-minimal:latest

# Builder stage: download and extract the OpenCode binary
FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Resolve latest release tag, then download the binary tarball
RUN OPENCODE_VERSION=$(curl -s https://api.github.com/repos/sst/opencode/releases/latest \
        | grep '"tag_name"' \
        | sed 's/.*"tag_name": "\(.*\)".*/\1/') && \
    curl -fsSL "https://github.com/sst/opencode/releases/download/${OPENCODE_VERSION}/opencode_linux_amd64.tar.gz" \
        -o /tmp/opencode.tar.gz && \
    tar -xzf /tmp/opencode.tar.gz -C /tmp && \
    chmod +x /tmp/opencode && \
    /tmp/opencode --version || true

# Runtime stage: copy only the binary
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-opencode"
LABEL org.opencontainers.image.description="OpenCode AI coding agent vessel"

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}

USER root

# Install OpenCode — pinned version with SHA256 verification (no curl-pipe-bash)
ARG OPENCODE_VERSION=1.4.3
ARG OPENCODE_SHA256=34d503ebb029853293be6fd4d441bbb2dbb03919bfa4525e88b1ca55d68f3e17
RUN curl -fsSL \
        "https://github.com/sst/opencode/releases/download/v${OPENCODE_VERSION}/opencode-linux-x64.tar.gz" \
        -o /tmp/opencode.tar.gz && \
    echo "${OPENCODE_SHA256}  /tmp/opencode.tar.gz" | sha256sum --check && \
    tar -xzf /tmp/opencode.tar.gz -C /usr/local/bin opencode && \
    chmod +x /usr/local/bin/opencode && \
    rm /tmp/opencode.tar.gz

# Verify installation
RUN opencode --version

USER agent

ENV AGENT_PROGRAM=opencode
ENV AGENT_HEADLESS_FLAG=-p
