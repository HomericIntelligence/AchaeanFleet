# AchaeanFleet Vessel: Nestor — research/ideation server
#
# Ported from HomericIntelligence/Nestor (Dockerfile). Source is cloned at a
# pinned upstream commit; the C++ server is built with the uv-managed
# CMake/Ninja/Conan toolchain (Odysseus ADR-018).
#
# ENTRYPOINT is set to the server binary so the vessel satisfies the fleet
# entrypoint/healthcheck contract; the container serves the /v1/health probe.

ARG UPSTREAM_SHA=6445688c1c27
ARG UPSTREAM_REPO=https://github.com/HomericIntelligence/Nestor

# uv binary source — named stage so `COPY --from=uv` resolves under both
# podman/buildah and docker (see Nestor Dockerfile for the buildah rationale).
FROM ghcr.io/astral-sh/uv:0.12.2@sha256:069a51314a7bb6031777a9273205fe1b0b19e914ef418207d1338b268df641dd AS uv

# -- Builder -------------------------------------------------------------------
FROM ubuntu@sha256:678c6550cc43645e08669028bc177f50be4e7c5b8cca677067b1914d4afc7a03 AS builder
ARG UPSTREAM_SHA
ARG UPSTREAM_REPO
# ubuntu:24.04 — pinned for reproducible builds (Nestor #60)

# apt provides only the compiler + OpenSSL headers + git/ca-certificates. The
# CMake/Ninja/Conan build toolchain is uv-managed as locked PyPI wheels.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    make \
    g++ \
    git \
    ca-certificates \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# uv binary (manages cmake/ninja/conan/gcovr/pre-commit as locked wheels).
COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /src
RUN git clone -q ${UPSTREAM_REPO} /src \
    && git -C /src checkout -q ${UPSTREAM_SHA}

# Sync the locked build toolchain first so it caches independently of sources.
RUN uv sync --locked \
    && uv run conan profile detect --force

# Conan deps, then CMake configuration (FetchContent nats.c cached separately).
RUN uv run conan install . \
    --output-folder=build \
    --profile:all=conan/profiles/nestor-release \
    --build=missing

RUN uv run cmake -B build -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE=build/conan_toolchain.cmake \
    -DCMAKE_BUILD_TYPE=Release \
    -DNestor_BUILD_TESTING=OFF \
    -DNestor_ENABLE_CLANG_TIDY=OFF \
    -DNestor_ENABLE_CPPCHECK=OFF \
    && uv run cmake --build build --target Nestor_server

# -- Runtime -------------------------------------------------------------------
FROM ubuntu@sha256:678c6550cc43645e08669028bc177f50be4e7c5b8cca677067b1914d4afc7a03

LABEL org.opencontainers.image.title="achaean-nestor"
LABEL org.opencontainers.image.description="Nestor research/ideation server — control-plane vessel"

# hadolint ignore=DL3008
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libssl3 \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /src/build/Nestor_server /usr/local/bin/Nestor_server

EXPOSE 8081

ENV NESTOR_PORT=8081
ENV NATS_URL=nats://localhost:4222

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["sh", "-c", "wget -qO- http://localhost:${NESTOR_PORT}/v1/health || exit 1"]

RUN useradd -r -s /usr/sbin/nologin -u 999 nestor
USER 999

ENTRYPOINT ["/usr/local/bin/Nestor_server"]
