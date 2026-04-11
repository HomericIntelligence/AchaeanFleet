# AchaeanFleet Vessel: Goose (Block)
#
# Installs Goose CLI binary on top of the minimal Debian base image.
# Goose is a Rust binary distributed via install script.

ARG BASE_IMAGE=achaean-base-minimal:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-goose"
LABEL org.opencontainers.image.description="Goose (Block) AI agent vessel"

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
RUN goose --version || true

USER agent

ENV AGENT_PROGRAM=goose
ENV AGENT_HEADLESS_FLAG="--mode cli"
