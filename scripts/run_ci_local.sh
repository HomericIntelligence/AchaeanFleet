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
# Image: requires the locally built 'achaeanfleet-ci:local' image; never pulls a fallback.
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
    "$@"
    log_info "OK: $desc"
}

run_in_container() {
    local cmd="$1"
    local ci_home="${CI_HOME:-${XDG_CACHE_HOME:-${HOME}/.cache}/achaeanfleet-ci/home}"
    mkdir -p "$ci_home"
    chmod 700 "$ci_home"
    local -a engine_options=()
    if [[ "$(basename "${CONTAINER_ENGINE}")" == podman ]]; then
        engine_options+=("--userns=keep-id:uid=1000,gid=1000" --http-proxy=false)
    fi
    "${CONTAINER_ENGINE}" run --rm "${engine_options[@]}" \
        --label "hi.achaeanfleet.ci=${CI_RUN_ID:-local}" \
        --user=1000:1000 --cpus="${CI_CPUS:-2}" \
        --memory="${CI_MEMORY:-2g}" --memory-swap="${CI_MEMORY:-2g}" \
        --pids-limit=256 --cap-drop=ALL --security-opt=no-new-privileges \
        -e HOME=/home/ci -v "${ci_home}:/home/ci:Z" \
        -v "${PROJECT_ROOT}:/workspace:Z" -w /workspace \
        "${IMAGE}" bash -euo pipefail -c "$cmd"
}

run_pixi() {
    run_in_container "pixi install --locked --environment dev && pixi run --environment dev $1"
}

# ============================================================================
# Subset definitions
# ============================================================================

run_lint() {
    run_pixi "pre-commit run --all-files"
}

run_markdownlint() {
    run_in_container 'markdownlint-cli2 "**/*.md" "#node_modules" "#.pixi" "#.ci-state"'
}

run_pixi-check() {
    run_in_container "pixi install --locked --environment dev"
}

run_unit-tests() {
    run_pixi "python -m pytest tests/ -v && pixi run --environment dev bats -r tests"
}

run_integration-tests() {
    run_in_container 'for overlay in mesh claude-only; do docker-compose -f compose/docker-compose.caddy.yml -f "compose/docker-compose.${overlay}.yml" config --quiet; done; docker-compose -f compose/docker-compose.smoke.yml config --quiet'
}

run_schema-validation() {
    run_pixi "python -m pytest tests/test_nomad_specs.py tests/test_nomad_mesh_spec.py tests/test_pod_specs.py -v"
    run_in_container 'for file in nomad/*.hcl; do if grep -q "^job " "$file"; then nomad job validate "$file"; fi; done'
}

run_security-secrets-scan() {
    run_in_container "gitleaks detect --no-banner --redact --source ."
}

run_security-dependency-scan() {
    run_in_container "trivy fs --scanners vuln --severity HIGH,CRITICAL --exit-code 1 --skip-dirs .ci-state --skip-dirs .pixi ."
}

run_deps-version-sync() {
    run_pixi "python -m pytest tests/test_dockerfile_pins.py tests/test_dockerfile_sha256_pins.py tests/test_dockerfile_version_pins.py -v"
}

run_forbid-suppressions() {
    run_pixi "pre-commit run forbid-or-true --all-files && pixi run --environment dev pre-commit run forbid-continue-on-error --all-files && pixi run --environment dev pre-commit run forbid-advisory-warnings --all-files"
}

run_justfile-check() {
    run_in_container "just --evaluate > /dev/null"
}

run_symlink-check() {
    run_in_container "bash scripts/check-symlinks.sh"
}

run_structure() {
    run_pixi "python scripts/check_ci_structure.py $1"
}

run_all() {
    run_step "Lint" run_lint
    run_step "Markdown" run_markdownlint
    run_step "Locked environment" run_pixi-check
    run_step "Python and shell tests" run_unit-tests
    run_step "Compose integration" run_integration-tests
    run_step "Deployment schemas" run_schema-validation
    run_step "Secrets" run_security-secrets-scan
    run_step "Dependencies" run_security-dependency-scan
    run_step "Version pins" run_deps-version-sync
    run_step "Suppression policy" run_forbid-suppressions
    run_step "Just syntax" run_justfile-check
    run_step "Symlink integrity" run_symlink-check
    for mode in build test package install release; do
        run_step "$mode source gate" run_structure "$mode"
    done
}

# ============================================================================
# Dispatch
# ============================================================================

detect_engine
select_image

case "${SUBSET}" in
    all) run_all ;;
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
    build|test|package|install|release) run_structure "$SUBSET" ;;

    *)
    log_error "Unknown subset '${SUBSET}'"
    exit 1
    ;;
esac

log_info "All CI checks passed (${SUBSET})."
