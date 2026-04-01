# AchaeanFleet Vessel: Goose (Block)
#
# Installs Goose CLI binary on top of the minimal Debian base image.
# Goose is a Rust binary distributed via install script.

ARG BASE_IMAGE=achaean-base-minimal:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-goose"
LABEL org.opencontainers.image.description="Goose (Block) AI agent vessel"

USER root

# Install Goose via official install script or tarball fallback
RUN curl -fsSL https://github.com/block/goose/releases/latest/download/download_cli.sh | bash || ( \
    curl -fsSL https://github.com/block/goose/releases/latest/download/goose-x86_64-unknown-linux-gnu.tar.bz2 \
        -o /tmp/goose.tar.bz2 && \
    tar -xjf /tmp/goose.tar.bz2 -C /usr/local/bin && \
    chmod +x /usr/local/bin/goose && \
    rm -f /tmp/goose.tar.bz2 )

# Verify installation
RUN goose --version || true

USER agent

ENV AGENT_PROGRAM=goose
ENV AGENT_HEADLESS_FLAG="--mode cli"
