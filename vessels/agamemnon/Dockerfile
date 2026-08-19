# AchaeanFleet Vessel: Agamemnon — HMAS orchestration server
#
# Ported from HomericIntelligence/Agamemnon (Dockerfile). Source is cloned at a
# pinned upstream commit and built with the uv-tool-managed
# CMake/Ninja/Conan toolchain (Odysseus ADR-018).

ARG UPSTREAM_SHA=bb17afd828a8
ARG UPSTREAM_REPO=https://github.com/HomericIntelligence/Agamemnon

# uv binary source — named stage (podman/buildah-safe COPY source).
FROM ghcr.io/astral-sh/uv:0.12.2@sha256:069a51314a7bb6031777a9273205fe1b0b19e914ef418207d1338b268df641dd AS uv

# -- Builder -------------------------------------------------------------------
FROM ubuntu:26.04@sha256:678c6550cc43645e08669028bc177f50be4e7c5b8cca677067b1914d4afc7a03 AS builder

ARG UPSTREAM_SHA
ARG UPSTREAM_REPO
# The system compiler (g++) and OpenSSL dev headers come from apt; the
# CMake/Ninja/Conan toolchain is installed as uv tools below.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    make \
    g++ \
    git \
    ca-certificates \
    libssl-dev \
    python3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /usr/local/bin/uv

# Install the build toolchain as uv tools whose entry points land on
# /usr/local/bin, then detect a default conan profile.
ENV UV_TOOL_BIN_DIR=/usr/local/bin
RUN --mount=type=cache,target=/root/.cache/uv \
    uv tool install cmake \
    && uv tool install ninja \
    && uv tool install conan \
    && conan profile detect

WORKDIR /src
RUN git clone --filter=blob:none ${UPSTREAM_REPO} /src \
    && git checkout -q ${UPSTREAM_SHA}

RUN conan install . \
    --output-folder=build \
    --profile=conan/profiles/default \
    --build=missing

RUN cmake -B build -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE=build/conan_toolchain.cmake \
    -DCMAKE_BUILD_TYPE=Release \
    -DAgamemnon_BUILD_TESTING=OFF \
    -DAgamemnon_ENABLE_CLANG_TIDY=OFF \
    -DAgamemnon_ENABLE_CPPCHECK=OFF \
    -DAgamemnon_WARNINGS_AS_ERRORS=OFF \
    && cmake --build build --target Agamemnon_server Agamemnon_healthcheck

# -- Runtime -------------------------------------------------------------------
FROM debian:13-slim@sha256:3a39a0592364683e6bab97937b72cad5a8fa6dcbbee90edb3bb48c7f8e94f258

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /src/build/Agamemnon_server /usr/local/bin/Agamemnon_server
COPY --from=builder /src/build/Agamemnon_healthcheck /usr/local/bin/Agamemnon_healthcheck

EXPOSE 8080

ENV NATS_URL=nats://localhost:4222
ENV PORT=8080
ENV SERVER_THREAD_COUNT=8
ENV SERVER_READ_TIMEOUT_SEC=10
ENV SERVER_WRITE_TIMEOUT_SEC=10
ENV SERVER_REQUEST_SIZE_LIMIT_MB=4
ENV NATS_STREAM_MAX_BYTES_MB=50
ENV NATS_STREAM_MAX_AGE_SEC=3600

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["/usr/local/bin/Agamemnon_healthcheck"]

RUN useradd -r -s /usr/sbin/nologin agamemnon
USER agamemnon

ENTRYPOINT ["/usr/local/bin/Agamemnon_server"]
