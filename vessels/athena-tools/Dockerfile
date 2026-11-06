# Independent ARM64 tool image; pins are mirrored in versions.yml.
FROM python:3.14.10-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b AS tools

ARG GIT_VERSION=1:2.39.5-0+deb12u3
ARG DEBIAN_SNAPSHOT=20261105T000000Z
ARG PIP_VERSION=26.3
ARG CODEX_VERSION=0.153.4
ARG CODEX_ARM64_SHA256=439c0dd0d6923f607b4e5cd1e3079c12f0b86f6e5007f07e377d6ad25e2d7bb9
ARG JUST_VERSION=1.51.0
ARG JUST_ARM64_SHA256=ed7ec466b77709198fd4afed253dba0270203ba5eb1c006bee2b0139090284f5
ARG UV_VERSION=0.12.10
ARG UV_ARM64_SHA256=9ff6b9d4665edcdd3a88dcc73cd1eb641754deb927f14e8c62ebfde6bf4f5f5e
# Athena revision 40c0d98 (2026-11-04, Athena #389) is the newest upstream
# uv.lock. Its dependency resolution is what the Trivy gate asked for: filelock
# 3.30.1 -> 4.2.4 (CVE-2026-112940) and virtualenv 21.14.5 -> 21.14.13
# (CVE-2026-113718/-113722/-113723/-113725). Upstream raised requires-python to
# >=3.14.10,<3.15 in the same commit range, so the interpreter floor moves with
# it and the base image moves from python:3.14.8 to 3.14.10. That base also
# carries apt 2.6.2 (CVE-2026-109518) and libssl3 3.0.22-1~deb12u2
# (CVE-2026-84782), both of which the 3.14.8 base predated.
#
# The Debian snapshot advances to 20261105T000000Z for libexpat1 and libbrotli1:
# they are absent from the new base image and arrive as dependencies of the git
# install below, so their versions are whatever the snapshot's main +
# bookworm-security suites offer. The security uploads the gate wants
# (libexpat1 2.5.0-1+deb12u5, libbrotli1 1.0.9-2+deb12u1) are published; the
# Trivy scan of the built image is the check that the snapshot carries them.
#
# eb8ff6c (2026-10-13, Athena #346) added the validator seam this image's
# workspace preparation depends on: scripts/validate_skills.py honours
# ATHENA_VALIDATE_IGNORED_PATHS, which workspace.just sets to .fleet-runtime.
# 40c0d98 still exposes it, and the justfile still offers `validate` and
# `uv-pins`, which is what the smoke job runs.
ARG ATHENA_REVISION=40c0d98df8ea1ff54360f1d1966d67b5e214c0c5
ARG ATHENA_LOCK_SHA256=27230f4781f617149a03a7f5de39ff8535e3dd7350bf033cfe1fd8ec002c24e7
ARG ATHENA_PROJECT_SHA256=ff8b147f1f9719627d4b6b0ce26c5324bbd3cde6748ecb0fdeafbdc883d19195
ARG ATHENA_PYTHON_SHA256=4f4c88910b6d485ae689143880e5e81b595a48a51ecb391b2f14feaec106d180

# Install git from the pinned Debian snapshot.
#
# Signature verification stays on. Only the Valid-Until replay clock is disabled,
# and only for these two source lines, using the per-source option
# sources.list(5) documents for repositories that are "not updated any more by
# design".
#
# Valid-Until is inherited from the live security archive's release cadence, not
# from the snapshot, so a snapshot's InRelease goes stale about six days after its
# timestamp even though the archived bytes never change. That makes the clock a
# pure nuisance here: it cannot detect tampering, which is what the Debian archive
# signature covers, and it cannot tell you the pinned content is wrong, because the
# content is immutable. What it really signals is "you may be pinning an old
# snapshot", and that risk is gated by the Trivy scan of the built image, which is
# a required check. Enforcing the clock instead meant the build failed every few
# days with `E: Release file ... is expired` and apt-get exit 100.
#
# The review obligation is kept, on a timescale a human or a monthly bump can
# actually meet: tests/test_athena_tools.py fails once DEBIAN_SNAPSHOT is older
# than 30 days.
RUN test "$(dpkg --print-architecture)" = arm64 \
    && rm /etc/apt/sources.list.d/debian.sources \
    && printf 'deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/%s/ bookworm main\ndeb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/%s/ bookworm-security main\n' \
        "$DEBIAN_SNAPSHOT" "$DEBIAN_SNAPSHOT" > /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends "git=${GIT_VERSION}" \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/local/bin/python3 /usr/bin/python3 \
    && ln -s /usr/local/bin/python /usr/bin/python

# The base image's pip vendors msgpack 1.1.2 at pip/_vendor/vendor.txt, which
# trivy reports as CVE-2026-114613 / GHSA-6v7p-g79w-8964 even though the
# site-packages table is clean. pip 26.3 vendors msgpack 1.2.4, above both fixed
# versions; it is the same upward re-pin bases/Dockerfile.python uses.
RUN python -m pip install --no-cache-dir --upgrade "pip==${PIP_VERSION}"

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
