# AchaeanFleet Vessel: Shell Worker
#
# A minimal shell worker with no AI tool installed.
# Used for CI tasks, scripting, and utility workloads.
# Based on the minimal Debian base image.

ARG BASE_IMAGE=achaean-base-minimal:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-worker"
LABEL org.opencontainers.image.description="Shell worker vessel — no AI tool, scripting and utility workloads"

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
ARG YQ_VERSION=v4.53.2
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}

USER root

# Install required tools — failures here are fatal
RUN apt-get update && apt-get install -y jq make && rm -rf /var/lib/apt/lists/*

# Install yq if not available via apt
RUN which yq || ( \
    curl -fsSL "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_amd64" \
        -o /usr/local/bin/yq && \
    chmod +x /usr/local/bin/yq )

COPY vessels/worker/healthcheck-server.js /app/healthcheck-server.js
RUN chown agent:agent /app/healthcheck-server.js

USER agent

ENV AGENT_PROGRAM=none
ENV AGENT_HEADLESS_FLAG=""

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:23001/health 2>/dev/null || exit 1

CMD ["node", "/app/healthcheck-server.js"]
