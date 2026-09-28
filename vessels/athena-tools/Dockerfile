# Independent ARM64 tool image; pins are mirrored in versions.yml.
FROM python:3.13.15-slim-bookworm@sha256:ae8c3b6bb3d02ffffa2bee0bed8c7c99b9478bd042ff4d79a5bbd6eb10398864 AS tools

ARG GIT_VERSION=1:2.39.5-0+deb12u3
ARG DEBIAN_SNAPSHOT=20260920T000000Z
ARG CODEX_VERSION=0.153.4
ARG CODEX_ARM64_SHA256=439c0dd0d6923f607b4e5cd1e3079c12f0b86f6e5007f07e377d6ad25e2d7bb9
ARG JUST_VERSION=1.51.0
ARG JUST_ARM64_SHA256=ed7ec466b77709198fd4afed253dba0270203ba5eb1c006bee2b0139090284f5
ARG UV_VERSION=0.12.10
ARG UV_ARM64_SHA256=9ff6b9d4665edcdd3a88dcc73cd1eb641754deb927f14e8c62ebfde6bf4f5f5e
ARG ATHENA_REVISION=3ba737517e2234729bcc7eb45b6ec0e3531efdf0
ARG ATHENA_LOCK_SHA256=c42df8b53694e9a434da9c75bf6e83cf7518260aba0dfd10bd403f902668d78b
ARG ATHENA_PROJECT_SHA256=304611c94811981ea79df8f31ddb06547307dcf13112167c2842d0caeaf3f0d0
ARG ATHENA_PYTHON_SHA256=861b3dd8083d28f336ef70f6755bc399538ddad627b1d095820ca34cb953cf14

# Keep ordinary apt signature and expiry verification enabled. An expired
# snapshot must be updated and reviewed, never accepted through a bypass.
RUN test "$(dpkg --print-architecture)" = arm64 \
    && rm /etc/apt/sources.list.d/debian.sources \
    && printf 'deb https://snapshot.debian.org/archive/debian/%s/ bookworm main\ndeb https://snapshot.debian.org/archive/debian-security/%s/ bookworm-security main\n' \
        "$DEBIAN_SNAPSHOT" "$DEBIAN_SNAPSHOT" > /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends "git=${GIT_VERSION}" \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/local/bin/python3 /usr/bin/python3 \
    && ln -s /usr/local/bin/python /usr/bin/python

COPY inputs/ /tmp/inputs/
RUN cd /tmp/inputs \
    && printf '%s  codex-arm64.tgz\n%s  just-arm64.tar.gz\n%s  uv-arm64.tar.gz\n%s  uv.lock\n%s  pyproject.toml\n%s  .python-version\n' \
        "$CODEX_ARM64_SHA256" "$JUST_ARM64_SHA256" "$UV_ARM64_SHA256" \
        "$ATHENA_LOCK_SHA256" "$ATHENA_PROJECT_SHA256" "$ATHENA_PYTHON_SHA256" | sha256sum -c - \
    && mkdir /opt/codex /opt/athena /opt/athena/dependencies /tmp/uv \
    && tar -xzf codex-arm64.tgz -C /opt/codex --strip-components=3 package/vendor/aarch64-unknown-linux-musl \
    && ln -s /opt/codex/bin /opt/codex-bin \
    && tar -xzf just-arm64.tar.gz -C /usr/bin just \
    && tar -xzf uv-arm64.tar.gz -C /tmp/uv --strip-components=1 \
    && install -m 0755 /tmp/uv/uv /usr/bin/uv \
    && cp uv.lock pyproject.toml .python-version /opt/athena/dependencies/ \
    && rm -rf /tmp/inputs /tmp/uv

COPY prepare_workspace.py workspace.just /opt/athena/
WORKDIR /opt/athena/dependencies
RUN UV_PYTHON_DOWNLOADS=never UV_PYTHON=/usr/bin/python3 \
    UV_CACHE_DIR=/opt/athena/cache UV_PROJECT_ENVIRONMENT=/tmp/athena-build-venv \
    UV_CONCURRENT_BUILDS=1 UV_CONCURRENT_INSTALLS=1 RAYON_NUM_THREADS=1 \
    uv sync --locked --no-build \
    && rm -rf /tmp/athena-build-venv
RUN PYTHONDONTWRITEBYTECODE=1 python3 - "$ATHENA_REVISION" <<'PY'
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, "/opt/athena")
from prepare_workspace import DEPENDENCY_FILES, cache_sha256, file_sha256
binding = {
    "upstream_revision": sys.argv[1],
    "dependency_files": {name: file_sha256(Path(name)) for name in DEPENDENCY_FILES},
    "cache_sha256": cache_sha256(Path("/opt/athena/cache")),
    "platform": "linux/arm64",
    "python": subprocess.check_output(["/usr/bin/python3", "--version"], text=True).strip(),
    "uv": subprocess.check_output(["/usr/bin/uv", "--version"], text=True).strip(),
    "git_package": subprocess.check_output(["dpkg-query", "-W", "-f=${Version}", "git"], text=True),
}
Path("/opt/athena/inputs.json").write_text(json.dumps(binding, sort_keys=True, indent=2) + "\n")
PY

FROM tools AS runtime
ARG IMAGE_VERSION=development
LABEL org.opencontainers.image.title="Athena offline tools" \
    org.opencontainers.image.source="https://github.com/HomericIntelligence/AchaeanFleet" \
    org.opencontainers.image.description="Contained tools and offline Athena dependencies; external worker owns orchestration and authentication" \
    org.opencontainers.image.version="${IMAGE_VERSION}"
RUN groupadd --gid 1000 agent \
    && useradd --uid 1000 --gid 1000 --create-home agent \
    && mkdir /workspace && chown 1000:1000 /workspace
ENV AGENT_PROGRAM=/opt/codex-bin/codex
USER 1000:1000
WORKDIR /workspace
# Hephaestus overrides this with the pinned exec-server entrypoint.
ENTRYPOINT ["/usr/bin/env"]
HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD ["/usr/bin/test", "-x", "/opt/codex-bin/codex"]
