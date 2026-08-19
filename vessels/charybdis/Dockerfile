# AchaeanFleet Vessel: Charybdis — test/validation framework CLI
#
# Ported from HomericIntelligence/Charybdis (Dockerfile). Source is cloned at a
# pinned upstream commit; tests run inside the builder (ctest) as part of the
# image build so a broken upstream never ships in the fleet image.

ARG UPSTREAM_SHA=1fe0457a6f74
ARG UPSTREAM_REPO=https://github.com/HomericIntelligence/Charybdis

# uv binary source — named stage (podman/buildah-safe COPY source).
FROM ghcr.io/astral-sh/uv:0.11.21@sha256:ff07b86af50d4d9391d9daf4ff89ce427bc544f9aae87057e69a1cc0aa369946 AS uv

# -- Builder -------------------------------------------------------------------
FROM ubuntu:24.04@sha256:c4a8d5503dfb2a3eb8ab5f807da5bc69a85730fb49b5cfca2330194ebcc41c7b AS builder

ARG UPSTREAM_SHA
ARG UPSTREAM_REPO
# System toolchain from apt: gcc-14/g++-14, make, git, CA certs, ASan/UBSan
# runtimes. CMake/Ninja/Conan come from uv (ADR-018).
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    make \
    gcc-14 \
    g++-14 \
    git \
    ca-certificates \
    libasan8 \
    libubsan1 \
    && update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-14 100 \
    && update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-14 100 \
    && update-alternatives --install /usr/bin/cc cc /usr/bin/gcc-14 100 \
    && update-alternatives --install /usr/bin/c++ c++ /usr/bin/g++-14 100 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/

ARG USER_ID=10001
ARG GROUP_ID=10001
ARG USER_NAME=builder

RUN groupadd -g ${GROUP_ID} ${USER_NAME} \
    && useradd -m -u ${USER_ID} -g ${GROUP_ID} ${USER_NAME} \
    && chmod 755 /home/${USER_NAME} \
    && mkdir -p /src /install && chown ${USER_ID}:${GROUP_ID} /src /install

ENV UV_PROJECT_ENVIRONMENT=/opt/charybdis-venv \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PATH="/opt/charybdis-venv/bin:$PATH"

WORKDIR /src
RUN git clone --filter=blob:none ${UPSTREAM_REPO} /src \
    && git checkout -q ${UPSTREAM_SHA}

# Sync the locked build toolchain into the shared venv, then chown so the
# non-root builder user can use it (UV_PYTHON_INSTALL_DIR keeps the managed
# CPython out of root's private home — see upstream Dockerfile comments).
RUN uv sync --locked --no-install-project \
    && chown -R ${USER_ID}:${GROUP_ID} /opt/charybdis-venv /opt/uv-python

USER ${USER_NAME}

RUN conan install . \
    --output-folder=build \
    --profile:all=conan/profiles/default \
    --build=missing

RUN cmake -B build -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE=build/conan_toolchain.cmake \
    -DCMAKE_BUILD_TYPE=Release \
    -DCharybdis_BUILD_TESTING=ON \
    -DCharybdis_ENABLE_CLANG_TIDY=OFF \
    -DCharybdis_ENABLE_CPPCHECK=OFF \
    && cmake --build build

# Run tests as part of the build to validate.
RUN ctest --test-dir build --output-on-failure

RUN cmake --install build --prefix /install

# -- Runtime -------------------------------------------------------------------
FROM ubuntu:24.04@sha256:c4a8d5503dfb2a3eb8ab5f807da5bc69a85730fb49b5cfca2330194ebcc41c7b AS runtime

LABEL org.opencontainers.image.title="achaean-charybdis"
LABEL org.opencontainers.image.description="Charybdis test/validation framework CLI — control-plane vessel"

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -r -s /bin/false charybdis

COPY --from=builder /install/bin/Charybdis /usr/local/bin/charybdis

USER charybdis

# CLI test-runner vessel: liveness == PID 1 of the container is running.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["sh", "-c", "kill -0 1 || exit 1"]

ENTRYPOINT ["/usr/local/bin/charybdis"]
