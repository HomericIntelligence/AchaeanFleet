# Independent ARM64 tool image; pins are mirrored in versions.yml.
FROM python:3.14.8-slim-bookworm@sha256:48b13b003dda20b16f9442b8475aa05fe21bf6579a8c881db92ffb4d8fd20f83 AS tools

ARG GIT_VERSION=1:2.39.5-0+deb12u3
ARG DEBIAN_SNAPSHOT=20261012T000000Z
ARG CODEX_VERSION=0.153.4
ARG CODEX_ARM64_SHA256=439c0dd0d6923f607b4e5cd1e3079c12f0b86f6e5007f07e377d6ad25e2d7bb9
ARG JUST_VERSION=1.51.0
ARG JUST_ARM64_SHA256=ed7ec466b77709198fd4afed253dba0270203ba5eb1c006bee2b0139090284f5
ARG UV_VERSION=0.12.10
ARG UV_ARM64_SHA256=9ff6b9d4665edcdd3a88dcc73cd1eb641754deb927f14e8c62ebfde6bf4f5f5e
# Athena revision 3ba7375 (2026-09-28) locked virtualenv 21.6.1, which fails
# CVE-2026-102925 / CVE-2026-102930 / CVE-2026-102937 (fixed in 21.7.13).
# a010a02 (2026-10-09) is the newest upstream uv.lock and resolves virtualenv
# 21.14.5. Upstream raised requires-python to >=3.14.8,<3.15 at the same time,
# so the interpreter floor moves with it and the base image moves from 3.13.15
# to 3.14.8. The old base also carried 7 fixable HIGH findings; the new one has
# none under the gate's --ignore-unfixed / severity HIGH,CRITICAL settings.
ARG ATHENA_REVISION=a010a0239ba44e0a8e17d55bfff777cc42b6dea1
ARG ATHENA_LOCK_SHA256=44af437c6c9a05f9a24d2fc062ce6e39996975193fda355d0ad082a343b65c40
ARG ATHENA_PROJECT_SHA256=cf9bd202b019ed41223330dfc66cdea05ab7794bcd118764c5fb813d244dd1b8
ARG ATHENA_PYTHON_SHA256=5abd4dc1efa09469b88916c8e4e027a8c266a9b6d06f43ac9da3e30cd00b4ab5

# Keep ordinary apt signature and expiry verification enabled. An expired
# snapshot must be updated and reviewed, never accepted through a bypass.
#
# 20260920T000000Z was retired on 2026-09-27: the bookworm-security InRelease
# carries a Valid-Until roughly seven days past the snapshot timestamp, so apt
# refused it with "Release file ... is expired" and the build exited 100. The
# pin moves to 20261012T000000Z (Valid-Until 2026-10-18). git 1:2.39.5-0+deb12u3
# is still the version bookworm main offers, so GIT_VERSION is unchanged.
#
# This pin lapses roughly every seven days and has no automated bump, so the
# build will fail again within the week unless the snapshot is advanced.
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
