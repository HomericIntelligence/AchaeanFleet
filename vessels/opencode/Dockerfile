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

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG TARGETARCH=amd64
# Pinned OpenCode version for reproducibility (issue #2). Update ENV to bump.
ENV OPENCODE_VERSION=v1.4.3

# Install OpenCode binary at pinned version
# opencode uses x64/arm64 naming (not amd64/arm64)
RUN case "${TARGETARCH}" in \
      amd64) OPENCODE_ARCH="x64" ;; \
      arm64) OPENCODE_ARCH="arm64" ;; \
      *) echo "Unsupported arch: ${TARGETARCH}" && exit 1 ;; \
    esac && \
    curl -fsSL "https://github.com/sst/opencode/releases/download/${OPENCODE_VERSION}/opencode-linux-${OPENCODE_ARCH}.tar.gz" \
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
