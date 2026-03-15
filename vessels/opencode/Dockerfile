# AchaeanFleet Vessel: OpenCode
#
# Installs OpenCode Go binary on top of the minimal Debian base image.

ARG BASE_IMAGE=achaean-base-minimal:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-opencode"
LABEL org.opencontainers.image.description="OpenCode AI coding agent vessel"

USER root

# Install OpenCode via official install script or direct binary download
RUN curl -fsSL https://opencode.ai/install | bash || \
    ( \
        OPENCODE_VERSION=$(curl -s https://api.github.com/repos/sst/opencode/releases/latest | grep '"tag_name"' | sed 's/.*"tag_name": "\(.*\)".*/\1/') && \
        curl -fsSL "https://github.com/sst/opencode/releases/download/${OPENCODE_VERSION}/opencode_linux_amd64.tar.gz" \
            -o /tmp/opencode.tar.gz && \
        tar -xzf /tmp/opencode.tar.gz -C /usr/local/bin && \
        chmod +x /usr/local/bin/opencode && \
        rm -f /tmp/opencode.tar.gz \
    )

# Verify installation
RUN opencode --version || true

USER agent

ENV AGENT_PROGRAM=opencode
ENV AGENT_HEADLESS_FLAG=-p
