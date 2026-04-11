# AchaeanFleet Vessel: Goose (Block)
#
# Installs Goose CLI binary on top of the minimal Debian base image.
# Goose is a Rust binary distributed via install script.

ARG BASE_IMAGE=achaean-base-minimal:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-goose"
LABEL org.opencontainers.image.description="Goose (Block) AI agent vessel"

USER root

# Install Goose (pinned release; verify SHA256 before extraction)
# renovate: datasource=github-releases depName=block/goose
ARG GOOSE_VERSION=1.30.0
COPY scripts/checksums/goose-1.30.0-linux-x86_64.sha256 /tmp/goose.sha256
RUN curl -fsSL \
        "https://github.com/block/goose/releases/download/v${GOOSE_VERSION}/goose-x86_64-unknown-linux-gnu.tar.gz" \
        -o /tmp/goose.tar.gz && \
    echo "$(cat /tmp/goose.sha256)  /tmp/goose.tar.gz" | sha256sum --check && \
    tar -xzf /tmp/goose.tar.gz -C /usr/local/bin ./goose && \
    chmod +x /usr/local/bin/goose && \
    rm -f /tmp/goose.tar.gz /tmp/goose.sha256

# Verify installation
RUN goose --version || true

USER agent

ENV AGENT_PROGRAM=goose
ENV AGENT_HEADLESS_FLAG="--mode cli"
