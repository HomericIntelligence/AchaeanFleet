# AchaeanFleet Vessel: Goose (Block)
#
# Installs Goose CLI binary on top of the minimal Debian base image.
# Uses a multi-stage build: the builder stage downloads and extracts the
# Goose binary; only the binary is copied into the runtime image.

ARG BASE_IMAGE=achaean-base-minimal:latest

# Builder stage: download and extract the Goose binary
FROM debian:bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download Goose binary directly (skip install script to avoid shell surprises)
RUN curl -fsSL https://github.com/block/goose/releases/latest/download/goose-linux-x86_64.tar.gz \
        -o /tmp/goose.tar.gz && \
    tar -xzf /tmp/goose.tar.gz -C /tmp && \
    chmod +x /tmp/goose && \
    /tmp/goose --version

# Runtime stage: copy only the binary
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-goose"
LABEL org.opencontainers.image.description="Goose (Block) AI agent vessel"

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}

USER root

# Install Goose — pinned version with SHA256 verification (no curl-pipe-bash)
ARG GOOSE_VERSION=1.30.0
ARG GOOSE_SHA256=0aeb220b744208b2fe5eca86eefdd31a4e0a6a35bdd0651ebd29959fc02f9eaf
RUN curl -fsSL \
        "https://github.com/block/goose/releases/download/v${GOOSE_VERSION}/goose-x86_64-unknown-linux-gnu.tar.gz" \
        -o /tmp/goose.tar.gz && \
    echo "${GOOSE_SHA256}  /tmp/goose.tar.gz" | sha256sum --check && \
    tar -xzf /tmp/goose.tar.gz -C /usr/local/bin ./goose && \
    chmod +x /usr/local/bin/goose && \
    rm /tmp/goose.tar.gz

# Verify installation
RUN goose --version

USER agent

ENV AGENT_PROGRAM=goose
ENV AGENT_HEADLESS_FLAG="--mode cli"
