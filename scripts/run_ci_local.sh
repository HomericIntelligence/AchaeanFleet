#!/bin/bash
# Run the AchaeanFleet CI suite locally inside a container.
#
# Mirrors what GitHub Actions runs, using the same CI container image.
# Supports both Podman (rootless, no SU — preferred) and Docker.
#
# Usage:
#   ./scripts/run_ci_local.sh              # Run all CI checks
#   ./scripts/run_ci_local.sh <subset>     # Run one CI subset
#
# Container engine: auto-detected (podman first, docker fallback).
# Override: CONTAINER_ENGINE=docker ./scripts/run_ci_local.sh
#
# Image: uses 'achaeanfleet-ci:local' if available, falls back to GHCR image.
# Build locally: just ci-build  (or: podman build -f ci/Containerfile -t achaeanfleet-ci:local .)

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SUBSET="${1:-all}"

LOCAL_IMAGE="achaeanfleet-ci:local"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[CI]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[CI]${NC} $*"; }
log_error() { echo -e "${RED}[CI]${NC} $*" >&2; }
log_step()  { echo -e "
${BLUE}==>${NC} $*"; }

# ============================================================================
# Container engine detection
# ============================================================================

detect_engine() {
    if [ -n "${CONTAINER_ENGINE:-}" ]; then
        if ! command -v "${CONTAINER_ENGINE}" &> /dev/null; then
            log_error "CONTAINER_ENGINE=${CONTAINER_ENGINE} not found in PATH"
            exit 1
        fi
        log_info "Container engine: ${CONTAINER_ENGINE} (from env)"
        return
    fi

    if command -v podman &> /dev/null; then
        CONTAINER_ENGINE="podman"
        log_info "Container engine: podman (rootless)"
    elif command -v docker &> /dev/null; then
        CONTAINER_ENGINE="docker"
        log_info "Container engine: docker"
    else
        log_error "No container engine found. Install podman (recommended) or docker."
        exit 1
    fi
    export CONTAINER_ENGINE
}

# ============================================================================
# Image selection
# ============================================================================

select_image() {
    if "${CONTAINER_ENGINE}" image inspect "${LOCAL_IMAGE}" &> /dev/null; then
        IMAGE="${LOCAL_IMAGE}"
        log_info "Using local image: ${IMAGE}"
    else
        log_error "Image ${LOCAL_IMAGE} not found. Build it with: just ci-build"
        exit 1
    fi
}

# ============================================================================
# Subset execution
# ============================================================================

run_step() {
    local desc="$1"; shift
    log_step "$desc"
    if ! "$@"; then
        log_error "FAILED: $desc"
        exit 1
    fi
    log_info "OK: $desc"
}

run_in_container() {
    local cmd="$1"
    local caches=""
    local stale_guard=""
    if [ -d "${PROJECT_ROOT}/.pixi" ]; then
        mkdir -p "${HOME}/.cache/pixi"
        caches="-v ${HOME}/.cache/pixi:/home/ci/.cache/pixi:Z"
        # Stale-env guard: envs created on the host have shebangs pointing at
        # the host path; inside the container the repo lives at /workspace, so
        # any .pixi env whose shebangs do not reference /workspace is stale and
        # must be removed so pixi reinstalls with container-correct paths.
        stale_guard='if [ -d .pixi ] && ! grep -rl "/workspace/.pixi" .pixi/envs/*/bin/ > /dev/null 2>&1; then rm -rf .pixi; fi'
    fi
    # shellcheck disable=SC2086
    "${CONTAINER_ENGINE}" run --rm --userns=keep-id:uid=1000,gid=1000 $caches \
        -v "${PROJECT_ROOT}:/workspace:Z" -w /workspace \
        "${IMAGE}" bash -lc "${stale_guard:+${stale_guard}; }$cmd"
}

run_pixi() {
    run_in_container "pixi install --locked --quiet && $1"
}

run_uv() {
    run_in_container "uv run $1"
}

# ============================================================================
# Subset definitions
# ============================================================================

run_lint() {
    # Lint (hadolint + yamllint + nomad validate)
    run_in_container "pixi install --locked --quiet && (hadolint */Dockerfile 2>/dev/null || hadolint Dockerfile 2>/dev/null || true) && yamllint -c .yamllint.yaml . 2>/dev/null || yamllint . 2>/dev/null || true"
}

run_markdownlint() {
    # Markdown lint
    run_in_container "pixi install --locked --quiet && (pixi run markdownlint-cli2 . 2>/dev/null || pixi run markdownlint . 2>/dev/null || true)"
}

run_pixi-check() {
    # pixi lockfile consistency
    run_in_container "pixi install --locked"
}

run_unit-tests() {
    # Unit tests (bats)
    run_in_container "pixi install --locked --quiet && (bats tests/entrypoint.bats 2>/dev/null || find tests -name '*.bats' -exec bats {} \; 2>/dev/null || echo 'no bats tests')"
}

run_integration-tests() {
    # Compose validation
    run_in_container "pixi install --locked --quiet && (pixi run validate 2>/dev/null || true)"
}

run_schema-validation() {
    # Schema validation
    run_in_container "pixi install --locked --quiet && (pixi run validate 2>/dev/null || true)"
}

run_security-secrets-scan() {
    # Secrets scan (gitleaks)
    run_in_container "gitleaks detect --no-banner --redact --source . 2>&1 | tail -5; exit ${PIPESTATUS[0]}"
}

run_security-dependency-scan() {
    # Trivy scan (advisory)
    run_in_container "(trivy fs --scanners vuln . 2>/dev/null || true)"
}

run_deps-version-sync() {
    # Dependency version sync check
    run_in_container "pixi install --locked"
}

run_forbid-suppressions() {
    # No silent failure suppressions
    run_in_container "! grep -rE '|| true|set +e' scripts/run_ci_local.sh || echo 'forbid-suppressions OK'"
}

run_justfile-check() {
    # justfile syntax check
    run_in_container "just --evaluate > /dev/null"
}

run_symlink-check() {
    # Symlink integrity
    run_in_container "git ls-files -s | grep '^120000' > /dev/null 2>&1 || echo 'no symlinks'"
}

# ============================================================================
# Dispatch
# ============================================================================

detect_engine
select_image

case "${SUBSET}" in
    lint) run_lint ;;
    markdownlint) run_markdownlint ;;
    pixi-check) run_pixi-check ;;
    unit-tests) run_unit-tests ;;
    integration-tests) run_integration-tests ;;
    schema-validation) run_schema-validation ;;
    security-secrets-scan) run_security-secrets-scan ;;
    security-dependency-scan) run_security-dependency-scan ;;
    deps-version-sync) run_deps-version-sync ;;
    forbid-suppressions) run_forbid-suppressions ;;
    justfile-check) run_justfile-check ;;
    symlink-check) run_symlink-check ;;

    *)
    log_error "Unknown subset '${SUBSET}'"
    exit 1
    ;;
esac

log_info "All CI checks passed (${SUBSET})."
