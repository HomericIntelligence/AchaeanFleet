# AchaeanFleet Vessel: Claude Code
#
# Installs @anthropic-ai/claude-code on top of the Node base image.
# Compatible with the HomericIntelligence agent mesh.

# Global ARG must be declared before the first FROM so it can be referenced
# by later FROM stages (Docker scopes ARGs declared between FROMs to that stage
# only).
ARG BASE_IMAGE=achaean-base-node:latest

# Builder stage — builds the GitHub CLI from source (issue #779).
#
# The apt-repo gh package vendors golang.org/x/mod v0.37.0, which carries
# HIGH CVE-2026-56864 and CVE-2026-56865 (fixed in x/mod v0.40.0). No released
# gh package ships the patched module yet, so we rebuild cli/cli at a pinned
# release tag with `go get golang.org/x/mod@<patched>` and assert the patched
# module is embedded in the binary at build time.
FROM golang:1.26.7-trixie@sha256:b389f1219965d8ba67776b81d17308ab25fa763be3855e5fe63ebcb10e15f3a1 AS gh-builder

ARG GH_VERSION=v2.96.0
ARG X_MOD_VERSION=v0.40.0

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

WORKDIR /src/cli

RUN git clone --depth 1 --branch "${GH_VERSION}" https://github.com/cli/cli.git . \
    && go get golang.org/x/mod@${X_MOD_VERSION} \
    && CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/gh ./cmd/gh \
    && actual="$(go version -m /out/gh | awk '$1 == "dep" && $2 == "golang.org/x/mod" {print $3}')" \
    && echo "Verifying golang.org/x/mod in built gh: ${actual:-MISSING} (need >= ${X_MOD_VERSION})" \
    && [ "$(printf '%s\n' "${actual}" "${X_MOD_VERSION}" | sort -V | head -n1)" = "${X_MOD_VERSION}" ]

FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="achaean-claude"
LABEL org.opencontainers.image.description="Claude Code agent vessel"

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.created=${BUILD_DATE}
LABEL org.opencontainers.image.revision=${VCS_REF}
LABEL org.opencontainers.image.version=${VERSION}
LABEL git-sha=${GIT_SHA}

USER root

# Ensure pipefail for piped RUN commands
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install Claude Code CLI (version pinned for reproducibility — issue #2)
RUN npm install -g @anthropic-ai/claude-code@2.1.233

# Install GitHub CLI from the source-built stage (issue #779).
# Built at /usr/bin/gh — the path referenced by prior Trivy scan rationale.
COPY --from=gh-builder /out/gh /usr/bin/gh
RUN chmod 0755 /usr/bin/gh

# Verify installation
RUN claude --version
RUN gh --version

USER agent

ENV AGENT_PROGRAM=claude
ENV AGENT_HEADLESS_FLAG=-p

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:23001/health 2>/dev/null || exit 1

# Runtime: Agamemnon agent sidecar starts claude with -p flag in tmux
