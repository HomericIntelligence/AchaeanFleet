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

USER root

COPY --from=builder /tmp/goose /usr/local/bin/goose

# Verify installation
RUN goose --version || true

USER agent

ENV AGENT_PROGRAM=goose
ENV AGENT_HEADLESS_FLAG="--mode cli"
