# AchaeanFleet Vessel: Goose (Block)
#
# Installs Goose CLI binary on top of the minimal Debian base image.
# Goose is a Rust binary distributed via GitHub releases.

ARG BASE_IMAGE=achaean-base-minimal:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-goose"
LABEL org.opencontainers.image.description="Goose (Block) AI agent vessel"

ARG GIT_SHA=unknown
LABEL git-sha=${GIT_SHA}

USER root

# Ensure pipefail for piped RUN commands
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG TARGETARCH=amd64
ARG GOOSE_VERSION=1.31.1
ENV GOOSE_VERSION=1.31.1
ARG GOOSE_AMD64_SHA256=61c072e843428310abc9751abb4bab097ce2721e519539fb22f0a4a29c8d02da
ARG GOOSE_ARM64_SHA256=1903a5ab266e6c59ae98636e45e80e9e63dd96fd5cd03787fe617252b5bda161

RUN case "${TARGETARCH}" in \
      amd64) GOOSE_TARBALL="goose-x86_64-unknown-linux-gnu.tar.gz"; GOOSE_SHA256="${GOOSE_AMD64_SHA256}" ;; \
      arm64) GOOSE_TARBALL="goose-aarch64-unknown-linux-gnu.tar.gz"; GOOSE_SHA256="${GOOSE_ARM64_SHA256}" ;; \
      *) echo "Unsupported arch: ${TARGETARCH}" && exit 1 ;; \
    esac && \
    curl -fsSL "https://github.com/block/goose/releases/download/v${GOOSE_VERSION}/${GOOSE_TARBALL}" \
        -o /tmp/goose.tar.gz && \
    echo "${GOOSE_SHA256}  /tmp/goose.tar.gz" | sha256sum --check && \
    tar -xzf /tmp/goose.tar.gz -C /usr/local/bin ./goose && \
    chmod +x /usr/local/bin/goose && \
    rm /tmp/goose.tar.gz

# Verify installation (native arch only — cross-arch QEMU emulation cannot execute arm64 binaries)
ARG BUILDARCH
RUN if [ -z "${BUILDARCH}" ] || [ "${TARGETARCH}" = "${BUILDARCH}" ]; then goose --version; else echo "Skipping goose --version: cross-arch build (${BUILDARCH} -> ${TARGETARCH})"; fi

USER agent

ENV AGENT_PROGRAM=goose
ENV AGENT_HEADLESS_FLAG="--mode cli"

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:23030/health 2>/dev/null || exit 1
