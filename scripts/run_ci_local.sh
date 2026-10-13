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
# Image: requires the locally built 'achaeanfleet-ci:local' image.
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
    # Do not put the function call in a conditional: Bash would disable
    # errexit inside it and a later successful command could hide failure.
    "$@"
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
        "${IMAGE}" bash -euo pipefail -c "${stale_guard:+${stale_guard}; }$cmd"
}

run_pixi() {
    run_in_container "pixi install --locked --environment dev --quiet && pixi run --environment dev $1"
}

# ============================================================================
# Subset definitions
# ============================================================================

run_lint() {
    run_pixi "pre-commit run --all-files --show-diff-on-failure"
}

run_markdownlint() {
    run_in_container "markdownlint-cli2 '**/*.md' '#node_modules' '#.pixi' '#.git'"
}

run_pixi-check() {
    # pixi lockfile consistency
    run_in_container "pixi install --locked"
}

run_unit-tests() {
    run_pixi "python -m pytest tests/ -v"
    run_pixi "bats -r tests"
}

run_integration-tests() {
    # Caddy supplies the networks referenced by these stacks, as in hosted CI.
    run_in_container 'for stack in claude-only mesh; do
        docker-compose -f compose/docker-compose.caddy.yml -f "compose/docker-compose.${stack}.yml" config --quiet
    done
    docker-compose -f compose/docker-compose.smoke.yml config --quiet'
}

run_schema-validation() {
    run_pixi "python -m pytest tests/test_nomad_specs.py tests/test_nomad_mesh_spec.py tests/test_nomad_vault_integration.py tests/test_pod_specs.py -v"
    # Only job specs are accepted by nomad validate; vault-policy.hcl is a policy.
    run_in_container 'for job in nomad/*.nomad.hcl; do nomad validate "$job"; done'
}

run_security-secrets-scan() {
    run_in_container "gitleaks detect --no-banner --redact --source ."
}

run_security-dependency-scan() {
    run_in_container "trivy fs --scanners vuln --severity HIGH,CRITICAL --exit-code 1 ."
}

run_deps-version-sync() {
    run_pixi "python -m pytest tests/test_dockerfile_pins.py tests/test_dockerfile_version_pins.py tests/test_dockerfile_sha256_pins.py -v"
}

run_forbid-suppressions() {
    run_pixi "pre-commit run forbid-or-true --all-files"
    run_pixi "pre-commit run forbid-continue-on-error --all-files"
    run_pixi "pre-commit run forbid-advisory-warnings --all-files"
}

run_justfile-check() {
    # justfile syntax check
    run_in_container "just --evaluate > /dev/null"
}

run_symlink-check() {
    run_in_container "bash scripts/check-symlinks.sh"
}

# ============================================================================
# Dispatch
# ============================================================================

detect_engine
select_image

case "${SUBSET}" in
    all)
        for subset in lint markdownlint pixi-check unit-tests integration-tests \
            schema-validation security-secrets-scan security-dependency-scan \
            deps-version-sync forbid-suppressions justfile-check symlink-check; do
            run_step "$subset" "run_${subset}"
        done
        ;;
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
