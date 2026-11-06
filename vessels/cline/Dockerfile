# AchaeanFleet Vessel: Cline
#
# Installs cline on top of the Node base image.

ARG BASE_IMAGE=achaean-base-node:latest
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-cline"
LABEL org.opencontainers.image.description="Cline AI coding agent vessel"

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}
LABEL git-sha=${GIT_SHA}

USER root

# Install Cline CLI (version pinned for reproducibility — issue #2).
#
# Installed into /opt/cline rather than globally so the package.json `overrides`
# block applies: ink-picture (the TUI image renderer) declares sharp ^0.34.3, and
# sharp 0.34.5 carries GHSA-f88m-g3jw-g9cj, GHSA-rgj7-g3m4-5g8c and
# GHSA-wq5f-xc86-pv6w, all fixed in sharp 0.35.x. npm is still the install path;
# only the transitive sharp resolution is pinned.
WORKDIR /opt/cline
RUN printf '%s\n' \
      '{"name":"cline-vessel","private":true,"dependencies":{"cline":"2.18.0"},"overrides":{"sharp":"0.35.5"}}' \
      > package.json && \
    npm install --omit=dev --no-audit --no-fund && \
    ln -sf /opt/cline/node_modules/.bin/cline /usr/local/bin/cline

# Verify installation
RUN cline --version

WORKDIR /

USER agent

ENV AGENT_PROGRAM=cline
ENV AGENT_HEADLESS_FLAG=-y

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:23040/health 2>/dev/null || exit 1
