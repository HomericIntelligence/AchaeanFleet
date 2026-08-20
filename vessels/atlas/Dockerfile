# AchaeanFleet Vessel: Atlas — unified ecosystem status dashboard
#
# Ported from HomericIntelligence/Argus (dashboard/Dockerfile), where the
# atlas module lives at the repo root of dashboard/. Source is cloned at a
# pinned upstream commit; the builder stage also compiles a tiny static
# healthcheck binary (healthcheck.go) because distroless ships no shell.

ARG UPSTREAM_SHA=59727bb5c86a
ARG UPSTREAM_REPO=https://github.com/HomericIntelligence/Argus

ARG GO_VERSION=1.25-alpine

# -- Builder -------------------------------------------------------------------
FROM golang:${GO_VERSION} AS builder

ARG UPSTREAM_SHA
ARG UPSTREAM_REPO
ARG VERSION=dev

# Healthcheck binary must be copied into the build before the source tree is
# fetched so it compiles in the same stage.
RUN apk add --no-cache git

WORKDIR /healthcheck-src
COPY vessels/atlas/healthcheck.go .

WORKDIR /src
RUN git clone -q ${UPSTREAM_REPO} /src \
    && git -C /src checkout -q ${UPSTREAM_SHA}

# The atlas module lives in the dashboard/ subdirectory of the Argus repo.
WORKDIR /src/dashboard

# The pinned Argus commit predates the x/crypto SSH fixes. Upgrade the
# indirect module before compiling so the final static binary carries the
# patched implementation instead of inheriting v0.50.0.
RUN go mod edit -require=golang.org/x/crypto@v0.52.0 \
    && go mod tidy

RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go mod download

RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux \
    go build \
        -trimpath \
        -ldflags="-s -w -X github.com/HomericIntelligence/atlas/internal/version.Version=${VERSION}" \
        -o /out/atlas \
        ./cmd/argus-dashboard

RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux \
    go build \
        -trimpath \
        -ldflags="-s -w" \
        -o /out/healthcheck \
        /healthcheck-src/healthcheck.go

# -- Runtime: distroless (no shell, no package manager) ------------------------
FROM gcr.io/distroless/static-debian12:nonroot

LABEL org.opencontainers.image.title="achaean-atlas"
LABEL org.opencontainers.image.description="Atlas — unified status dashboard for the HomericIntelligence ecosystem"

# distroless/static defaults to nonroot (UID 65532); make it explicit.
USER 65532:65532

COPY --from=builder /out/atlas /atlas
COPY --from=builder --chown=65532:65532 /src/dashboard/web/static /web/static
COPY --from=builder /out/healthcheck /healthcheck

EXPOSE 3002

# Static healthcheck binary (no shell in distroless) probes /livez.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["/healthcheck"]

ENTRYPOINT ["/atlas"]
