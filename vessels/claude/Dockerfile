# AchaeanFleet Vessel: Claude Code
#
# Installs @anthropic-ai/claude-code on top of the Node base image.
# Compatible with the HomericIntelligence agent mesh.

ARG BASE_IMAGE=achaean-base-node:latest
FROM ${BASE_IMAGE} AS github-cli

USER root
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Upstream gh 2.100.0 still embeds x/mod 0.39.0. Build its pinned source with
# the 0.40.0 security fix; keep the compiler and module cache out of the vessel.
# Update and validation procedure: docs/runbooks/github-cli-rebuild.md.
ARG GO_VERSION=1.26.8
ARG GO_AMD64_SHA256=d0f743b33e8d8945e6b1f432edd15785c70507121d6e2a723b21285eddf8b57b
ARG GO_ARM64_SHA256=211ffced9dcb9633a55eac6364816ec0ddd951389a740e88fa8b3337971bdda0
ARG GH_SOURCE_REVISION=45437bc7eeeb3359bbfddd1742f79de7652fd3e2
ARG GH_SOURCE_SHA256=e16749bc0d99dc0633a3d5ebadf48ffff1c24beb1ce83e8f6a71bb64ce477e9a
RUN architecture="$(dpkg --print-architecture)" \
    && case "$architecture" in \
      amd64) checksum="$GO_AMD64_SHA256" ;; \
      arm64) checksum="$GO_ARM64_SHA256" ;; \
      *) echo "Unsupported GitHub CLI build architecture: $architecture" >&2; exit 1 ;; \
    esac \
    && curl -fsSL --retry 3 "https://go.dev/dl/go${GO_VERSION}.linux-${architecture}.tar.gz" -o /tmp/go.tar.gz \
    && echo "${checksum}  /tmp/go.tar.gz" | sha256sum --check \
    && tar -xzf /tmp/go.tar.gz -C /opt \
    && curl -fsSL --retry 3 "https://codeload.github.com/cli/cli/tar.gz/${GH_SOURCE_REVISION}" -o /tmp/gh.tar.gz \
    && echo "${GH_SOURCE_SHA256}  /tmp/gh.tar.gz" | sha256sum --check \
    && mkdir /opt/gh-source /out \
    && tar -xzf /tmp/gh.tar.gz -C /opt/gh-source --strip-components=1

WORKDIR /opt/gh-source
ENV PATH="/opt/go/bin:$PATH" GOTOOLCHAIN=local CGO_ENABLED=0 GOMAXPROCS=2
RUN go mod edit -require=golang.org/x/mod@v0.40.0 \
    && printf '%s\n' \
      'golang.org/x/mod v0.40.0 h1:hUv+3cXcdRHz08UmSiOob7sadHig73uo5bkXxQ/tvUs=' \
      'golang.org/x/mod v0.40.0/go.mod h1:0/weTWkPWGBikyTWAX3dkjVztMmBA5hM0DH6BElSupE=' >> go.sum \
    && go build -mod=readonly -trimpath -buildvcs=false -p 2 \
      -ldflags='-s -w -X github.com/cli/cli/v2/internal/build.Version=2.100.0-fleet.1' \
      -o /out/gh ./cmd/gh \
    && go version -m /out/gh | tee /out/gh.buildinfo \
    && awk '$1 == "dep" && $2 == "golang.org/x/mod" { found++; if ($3 != "v0.40.0") exit 1 } END { if (found != 1) exit 1 }' /out/gh.buildinfo \
    && /out/gh --version

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

# Install only the rebuilt CLI and its actual module inventory.
COPY --from=github-cli /out/gh /usr/bin/gh
COPY --from=github-cli /out/gh.buildinfo /usr/share/doc/gh/fleet.buildinfo

# Verify installation
RUN claude --version
RUN gh --version

USER agent

ENV AGENT_PROGRAM=claude
ENV AGENT_HEADLESS_FLAG=-p

HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:23001/health 2>/dev/null || exit 1

# Runtime: Agamemnon agent sidecar starts claude with -p flag in tmux
