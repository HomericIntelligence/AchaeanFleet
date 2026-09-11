# Build only through the fleet-image recipe, which validates all digest inputs.
ARG NODE_BASE_IMAGE
ARG RUNTIME_BASE_IMAGE
FROM ${NODE_BASE_IMAGE} AS codex
WORKDIR /opt/codex
COPY vessels/fleet/package.json vessels/fleet/package-lock.json ./
RUN npm ci --ignore-scripts --omit=dev
ARG TARGETARCH
# The pinned npm platform package contains standalone musl binaries.
RUN case "${TARGETARCH}" in \
      amd64) package=x64; triple=x86_64-unknown-linux-musl ;; \
      arm64) package=arm64; triple=aarch64-unknown-linux-musl ;; \
      *) exit 1 ;; \
    esac \
    && mkdir /opt/codex-bin \
    && cp -a "node_modules/@openai/codex-linux-${package}/vendor/${triple}/." /opt/codex-bin/ \
    && ln -s bin/codex /opt/codex-bin/codex \
    && ln -s bin/codex-code-mode-host /opt/codex-bin/codex-code-mode-host \
    && test -x /opt/codex-bin/codex-resources/bwrap \
    && test "$(/opt/codex-bin/codex --version)" = "codex-cli 0.153.4"

# RUNTIME_BASE_IMAGE is a digest-pinned python:3.13-slim-bookworm image.
FROM ${RUNTIME_BASE_IMAGE} AS toolchain
# This intermediate package-install stage needs root; runtime ends as UID 1000.
# hadolint ignore=DL3002
USER root
ARG TARGETARCH
# A fixed Debian snapshot resolves the same OS package inputs on each build.
RUN python3 -c 'import sys; assert sys.version_info[:2] == (3, 13)' \
    && . /etc/os-release && test "${VERSION_CODENAME}" = bookworm \
    && rm -f /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources \
    && printf '%s\n' \
       'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20260909T000000Z/ bookworm main' \
       'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/20260909T000000Z/ bookworm-security main' \
       > /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends git build-essential pkg-config ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY hephaestus/fleet_image.py /opt/fleet-image.py
COPY vessels/fleet/tool-artifacts.json /opt/fleet-tool-artifacts.json
RUN python3 /opt/fleet-image.py install-tools --platform "linux/${TARGETARCH}" \
       --artifacts /opt/fleet-tool-artifacts.json --destination /usr/local/bin \
    && test "$(just --version)" = 'just 1.51.0' \
    && test "$(pixi --version)" = 'pixi 0.70.2' \
    && groupadd --gid 1000 agent \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash agent \
    && mkdir -p /workspace /var/lib/fleet \
    && chown 1000:1000 /workspace /var/lib/fleet

# Named, offline build context; never resolve an unpublished package from PyPI/Git.
FROM toolchain AS runtime
# The validated, hash-locked wheel bundle is a named BuildKit build context.
# hadolint ignore=DL3022
COPY --from=hephaestus_bundle / /opt/fleet-bundle/
RUN python3 -c 'import sys; assert sys.version_info[:2] == (3, 13)' \
    && python3 -m venv /opt/fleet \
    && /opt/fleet/bin/python -m pip install --no-cache-dir --no-index --require-hashes \
       --only-binary=:all: --find-links=/opt/fleet-bundle -r /opt/fleet-bundle/requirements.txt \
    && /opt/fleet/bin/python -m pip check \
    && /opt/fleet/bin/hephaestus-fleet-worker --help >/dev/null \
    && rm -f /opt/fleet-bundle/*.whl
ARG HEPHAESTUS_REVISION
LABEL org.opencontainers.image.source="https://github.com/HomericIntelligence/AchaeanFleet"
LABEL ai.homeric.hephaestus.revision=${HEPHAESTUS_REVISION}
ENV PATH="/opt/fleet/bin:${PATH}"
ENV HOME=/home/agent
WORKDIR /workspace
USER 1000:1000

# Tool jobs use this target. It contains no Codex program or authentication home.
FROM runtime AS build-tools
LABEL org.opencontainers.image.title="achaean-fleet-build-tools"
ENTRYPOINT ["just"]

FROM runtime AS worker
LABEL org.opencontainers.image.title="achaean-fleet-worker"
LABEL ai.homeric.codex.version="0.153.4"
COPY --from=codex /opt/codex-bin/ /opt/codex-bin/
COPY --chmod=0555 vessels/fleet/entrypoint.sh /opt/fleet-entrypoint.sh
ENV PATH="/opt/codex-bin:${PATH}"
ENV CODEX_HOME=/var/lib/fleet/codex
# Supervision provides private writable mounts and all worker identity arguments.
ENTRYPOINT ["/opt/fleet-entrypoint.sh"]
