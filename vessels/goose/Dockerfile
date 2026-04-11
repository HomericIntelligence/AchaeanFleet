# AchaeanFleet Vessel: Goose (Block)
#
# Installs Goose CLI binary on top of the minimal Debian base image.
# Goose is a Rust binary distributed via install script.

ARG BASE_IMAGE=achaean-base-minimal:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-goose"
LABEL org.opencontainers.image.description="Goose (Block) AI agent vessel"

USER root

# Pinned Goose version for reproducibility (issue #2). Update ENV to bump.
ENV GOOSE_VERSION=v1.30.0

# Install Goose binary at pinned version
RUN curl -fsSL "https://github.com/block/goose/releases/download/${GOOSE_VERSION}/goose-linux-x86_64.tar.gz" \
        -o /tmp/goose.tar.gz && \
    tar -xzf /tmp/goose.tar.gz -C /usr/local/bin && \
    chmod +x /usr/local/bin/goose && \
    rm -f /tmp/goose.tar.gz

# Verify installation
RUN goose --version || true

USER agent

ENV AGENT_PROGRAM=goose
ENV AGENT_HEADLESS_FLAG="--mode cli"
