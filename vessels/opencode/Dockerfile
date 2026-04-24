# AchaeanFleet Vessel: OpenCode
#
# Installs OpenCode Go binary on top of the minimal Debian base image.

ARG BASE_IMAGE=achaean-base-minimal:latest

FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-opencode"
LABEL org.opencontainers.image.description="OpenCode AI coding agent vessel"

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}
LABEL git-sha=${GIT_SHA}

USER root

# Pinned OpenCode version for reproducibility (issue #2). Update ENV to bump.
ENV OPENCODE_VERSION=v1.4.3

# Install OpenCode binary at pinned version
RUN curl -fsSL "https://github.com/sst/opencode/releases/download/${OPENCODE_VERSION}/opencode_linux_amd64.tar.gz" \
        -o /tmp/opencode.tar.gz && \
    tar -xzf /tmp/opencode.tar.gz -C /usr/local/bin && \
    chmod +x /usr/local/bin/opencode && \
    rm -f /tmp/opencode.tar.gz

# Verify installation
RUN opencode --version

USER agent

ENV AGENT_PROGRAM=opencode
ENV AGENT_HEADLESS_FLAG=-p

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:23050/health 2>/dev/null || exit 1
