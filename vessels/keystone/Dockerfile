# AchaeanFleet Vessel: Keystone — C++20 HMAS service daemon
#
# Ported from HomericIntelligence/Keystone (Containerfile), production stage
# only — the upstream `test` and `development` stages are intentionally dropped
# so the fleet image ships exactly the daemon, nothing else (optimization).
# Source is cloned at a pinned upstream commit.

ARG UPSTREAM_SHA=ac22a6977c74
ARG UPSTREAM_REPO=https://github.com/HomericIntelligence/Keystone

# uv binary source — named stage (podman/buildah-safe COPY source).
FROM ghcr.io/astral-sh/uv:0.12.2@sha256:069a51314a7bb6031777a9273205fe1b0b19e914ef418207d1338b268df641dd AS uv

# -- Builder -------------------------------------------------------------------
# Base digest pinned 2026-08-16 (noble) — see upstream Containerfile comment.
FROM ubuntu:24.04@sha256:019e8eb29a85e74d64925745884f2ec79aa27e3feab36353d24656f4d6b89467 AS builder

ARG UPSTREAM_SHA
ARG UPSTREAM_REPO
ARG CMAKE_BUILD_TYPE=Release
ARG CMAKE_CXX_FLAGS=""

ENV DEBIAN_FRONTEND=noninteractive

# clang-18 + libc++ dev headers from apt; CMake/Ninja/Conan are uv-managed.
RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    build-essential \
    clang-18 \
    clang++-18 \
    libc++-18-dev \
    libc++abi-18-dev \
    git \
    lcov \
    bc \
    libssl-dev \
    && update-alternatives --install /usr/bin/clang clang /usr/bin/clang-18 100 \
    && update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-18 100 \
    && update-alternatives --install /usr/bin/cc cc /usr/bin/clang-18 100 \
    && update-alternatives --install /usr/bin/c++ c++ /usr/bin/clang++-18 100 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/

# uv-managed toolchain in /opt/venv (outside /workspace so bind mounts at
# runtime never mask it); PATH exposes bare `conan`/`cmake`/`ninja`.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /src
RUN git clone -q ${UPSTREAM_REPO} /src \
    && git -C /src checkout -q ${UPSTREAM_SHA}

RUN uv sync --locked \
    && chmod -R a+rX /opt/venv /opt/uv-python

RUN conan profile detect --force

RUN conan install . --output-folder=build/conan-deps --build=missing \
    -s build_type=Release -s compiler.cppstd=20

RUN cmake -S . -B build/release -G Ninja \
        -DCMAKE_BUILD_TYPE=${CMAKE_BUILD_TYPE} \
        -DCMAKE_CXX_FLAGS="${CMAKE_CXX_FLAGS}" \
        -DCMAKE_TOOLCHAIN_FILE=build/conan-deps/conan_toolchain.cmake \
    && cmake --build build/release

# -- Runtime: production daemon -------------------------------------------------
FROM ubuntu:24.04@sha256:019e8eb29a85e74d64925745884f2ec79aa27e3feab36353d24656f4d6b89467

LABEL org.opencontainers.image.title="achaean-keystone"
LABEL org.opencontainers.image.description="Keystone C++20 HMAS service daemon — control-plane vessel"

RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    libstdc++6 \
    wget \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 1001 hmas || true && \
    useradd -r -u 1001 -g 1001 hmas && \
    mkdir -p /app && \
    chown -R hmas:hmas /app

COPY --from=builder /src/build/release/bin/keystone-server /usr/local/bin/keystone-server

WORKDIR /app
USER hmas

EXPOSE 8080 9090 50051

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:8080/v1/health || exit 1

ENTRYPOINT ["/usr/local/bin/keystone-server"]
