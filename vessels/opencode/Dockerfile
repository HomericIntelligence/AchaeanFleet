# AchaeanFleet Vessel: OpenCode
#
# Installs OpenCode Go binary on top of the minimal Debian base image.

ARG BASE_IMAGE=achaean-base-minimal:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-opencode"
LABEL org.opencontainers.image.description="OpenCode AI coding agent vessel"

USER root

# Install OpenCode (pinned release; verify SHA256 before extraction)
# renovate: datasource=github-releases depName=sst/opencode
ARG OPENCODE_VERSION=1.4.3
COPY scripts/checksums/opencode-1.4.3-linux-x64.sha256 /tmp/opencode.sha256
RUN curl -fsSL \
        "https://github.com/sst/opencode/releases/download/v${OPENCODE_VERSION}/opencode-linux-x64.tar.gz" \
        -o /tmp/opencode.tar.gz && \
    echo "$(cat /tmp/opencode.sha256)  /tmp/opencode.tar.gz" | sha256sum --check && \
    tar -xzf /tmp/opencode.tar.gz -C /usr/local/bin opencode && \
    chmod +x /usr/local/bin/opencode && \
    rm -f /tmp/opencode.tar.gz /tmp/opencode.sha256

# Verify installation
RUN opencode --version || true

USER agent

ENV AGENT_PROGRAM=opencode
ENV AGENT_HEADLESS_FLAG=-p
