#!/usr/bin/env bash
# scripts/build-all.sh — Build all AchaeanFleet images in order
#
# Builds 3 bases first, then 9 vessels in dependency order.
# Called by: just build-all
#
# Usage:
#   bash scripts/build-all.sh
#   TAG=v1.2.3 bash scripts/build-all.sh   # Override image tag

set -euo pipefail

TAG="${TAG:-latest}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

# Counters
built=0
failed=0

build_image() {
    local tag="$1"
    local dockerfile="$2"
    shift 2
    local extra_args=("$@")

    echo ""
    echo "--- Building ${tag} from ${dockerfile} ---"
    if docker build -f "${dockerfile}" -t "${tag}" "${extra_args[@]}" .; then
        echo "    OK: ${tag}"
        built=$((built + 1))
    else
        echo "    FAILED: ${tag}" >&2
        failed=$((failed + 1))
        return 1
    fi
}

# =============================================================================
# Step 1: Base images (must be built before vessels)
# =============================================================================
echo "=== Building base images ==="

build_image "achaean-base-node:${TAG}"    "bases/Dockerfile.node"
build_image "achaean-base-python:${TAG}"  "bases/Dockerfile.python"
build_image "achaean-base-minimal:${TAG}" "bases/Dockerfile.minimal"

# =============================================================================
# Step 2: Vessel images (each FROM a base via ARG BASE_IMAGE)
# =============================================================================
echo ""
echo "=== Building vessel images ==="

# Node-based vessels
build_image "achaean-claude:${TAG}"   "vessels/claude/Dockerfile"   --build-arg "BASE_IMAGE=achaean-base-node:${TAG}"
build_image "achaean-codex:${TAG}"    "vessels/codex/Dockerfile"    --build-arg "BASE_IMAGE=achaean-base-node:${TAG}"
build_image "achaean-cline:${TAG}"    "vessels/cline/Dockerfile"    --build-arg "BASE_IMAGE=achaean-base-node:${TAG}"
build_image "achaean-codebuff:${TAG}" "vessels/codebuff/Dockerfile" --build-arg "BASE_IMAGE=achaean-base-node:${TAG}"
build_image "achaean-ampcode:${TAG}"  "vessels/ampcode/Dockerfile"  --build-arg "BASE_IMAGE=achaean-base-node:${TAG}"

# Python-based vessels
build_image "achaean-aider:${TAG}" "vessels/aider/Dockerfile" --build-arg "BASE_IMAGE=achaean-base-python:${TAG}"

# Minimal-based vessels
build_image "achaean-goose:${TAG}"    "vessels/goose/Dockerfile"    --build-arg "BASE_IMAGE=achaean-base-minimal:${TAG}"
build_image "achaean-opencode:${TAG}" "vessels/opencode/Dockerfile" --build-arg "BASE_IMAGE=achaean-base-minimal:${TAG}"
build_image "achaean-worker:${TAG}"   "vessels/worker/Dockerfile"   --build-arg "BASE_IMAGE=achaean-base-minimal:${TAG}"

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "=== Build summary: ${built} built, ${failed} failed ==="

if [[ $failed -gt 0 ]]; then
    exit 1
fi
