#!/usr/bin/env bash
# Prepare verified public inputs, then optionally build the standalone ARM64 image.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
recipe="$root/vessels/athena-tools"
mode="${1:?usage: inputs|build DIRECTORY}"
context="${2:?an explicit build context directory is required}"
case "$mode" in inputs|build) ;; *) echo "unknown mode: $mode" >&2; exit 2 ;; esac
mkdir -p "$context/inputs"
context="$(cd "$context" && pwd)"

pin() {
    local value
    value="$(sed -n "s/^ARG $1=//p" "$recipe/Dockerfile")"
    test -n "$value"
    printf '%s' "$value"
}

sha256() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d ' ' -f 1
    else
        shasum -a 256 "$1" | cut -d ' ' -f 1
    fi
}

fetch() {
    local name="$1" expected="$2" url="$3" target
    target="$context/inputs/$name"
    if [ -e "$target" ]; then
        test "$(sha256 "$target")" = "$expected"
    else
        curl --fail --location --proto '=https' --tlsv1.2 \
            --connect-timeout 20 --max-time 180 --output "$target.partial" "$url"
        test "$(sha256 "$target.partial")" = "$expected"
        mv "$target.partial" "$target"
    fi
}

fetch codex-arm64.tgz "$(pin CODEX_ARM64_SHA256)" \
    "https://registry.npmjs.org/@openai/codex/-/codex-$(pin CODEX_VERSION)-linux-arm64.tgz"
fetch just-arm64.tar.gz "$(pin JUST_ARM64_SHA256)" \
    "https://github.com/casey/just/releases/download/$(pin JUST_VERSION)/just-$(pin JUST_VERSION)-aarch64-unknown-linux-musl.tar.gz"
fetch uv-arm64.tar.gz "$(pin UV_ARM64_SHA256)" \
    "https://github.com/astral-sh/uv/releases/download/$(pin UV_VERSION)/uv-aarch64-unknown-linux-gnu.tar.gz"
upstream="https://raw.githubusercontent.com/HomericIntelligence/Athena/$(pin ATHENA_REVISION)"
fetch uv.lock "$(pin ATHENA_LOCK_SHA256)" "$upstream/uv.lock"
fetch pyproject.toml "$(pin ATHENA_PROJECT_SHA256)" "$upstream/pyproject.toml"
fetch .python-version "$(pin ATHENA_PYTHON_SHA256)" "$upstream/.python-version"
cp "$recipe/Dockerfile" "$recipe/Dockerfile.dockerignore" \
    "$recipe/prepare_workspace.py" "$recipe/workspace.just" "$context/"

if [ "$mode" = build ]; then
    engine="${CONTAINER_CMD:-podman}"
    # The Linux operator also owns the VM, disk admission and process cleanup.
    timeout --signal=TERM --kill-after=30s 1800s "$engine" build \
        --memory 2g --memory-swap 2g --cpu-period 100000 --cpu-quota 200000 \
        --ulimit nproc=512:512 --platform linux/arm64 \
        -f "$context/Dockerfile" -t achaean-athena-tools:local "$context"
fi
