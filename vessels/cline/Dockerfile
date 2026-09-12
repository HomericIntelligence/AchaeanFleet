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

# Keep the existing CLI while fixing ink-picture's vulnerable Sharp closure.
# The lock includes both Linux architectures and npm verifies each integrity.
COPY vessels/cline/package.json vessels/cline/package-lock.json /opt/achaean-cline/
RUN npm ci --omit=dev --prefix /opt/achaean-cline \
    && ln -s /opt/achaean-cline/node_modules/.bin/cline /usr/local/bin/cline

# Verify the installed native image library, including the patched libheif.
COPY vessels/cline/verify-runtime.cjs /opt/achaean-cline/verify-runtime.cjs
RUN cline --version \
    && node /opt/achaean-cline/verify-runtime.cjs

USER agent

ENV AGENT_PROGRAM=cline
ENV AGENT_HEADLESS_FLAG=-y

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:23040/health 2>/dev/null || exit 1
