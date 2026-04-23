# AchaeanFleet Vessel: Goose (Block)
#
# Installs Goose CLI binary on top of the minimal Debian base image.
# Goose is a Rust binary distributed via GitHub releases.

ARG BASE_IMAGE=achaean-base-minimal:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-goose"
LABEL org.opencontainers.image.description="Goose (Block) AI agent vessel"

USER root

ARG GOOSE_VERSION=1.30.0
ARG GOOSE_SHA256_AMD64=0aeb220b744208b2fe5eca86eefdd31a4e0a6a35bdd0651ebd29959fc02f9eaf
ARG GOOSE_SHA256_ARM64=edb2618dbd27bb1cf9f4a07be914d1313a91a6726a9e04cb05e3455a30d556d6
# TARGETARCH is injected by docker buildx (amd64 | arm64); pass explicitly for plain docker build
ARG TARGETARCH

ENV GOOSE_VERSION=${GOOSE_VERSION}

RUN set -eux; \
    case "${TARGETARCH}" in \
      amd64) ARCH="x86_64";   SHA256="${GOOSE_SHA256_AMD64}" ;; \
      arm64) ARCH="aarch64";  SHA256="${GOOSE_SHA256_ARM64}"  ;; \
      *)     echo "Unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL \
        "https://github.com/block/goose/releases/download/v${GOOSE_VERSION}/goose-${ARCH}-unknown-linux-gnu.tar.gz" \
        -o /tmp/goose.tar.gz; \
    echo "${SHA256}  /tmp/goose.tar.gz" | sha256sum --check; \
    tar -xzf /tmp/goose.tar.gz -C /usr/local/bin ./goose; \
    chmod +x /usr/local/bin/goose; \
    rm /tmp/goose.tar.gz

# Verify installation
RUN goose --version || true

USER agent

ENV AGENT_PROGRAM=goose
ENV AGENT_HEADLESS_FLAG="--mode cli"
