# AchaeanFleet justfile — build helper for all images
# Usage: just <recipe>
# Requires: just, podman (preferred) or docker

# Default: show help
default:
    @just --list

# =============================================================================
# Variables
# =============================================================================

registry := env_var_or_default("REGISTRY", "ghcr.io/homericintelligence")

bases := "achaean-base-node achaean-base-python achaean-base-minimal"

vessels := "claude codex aider goose cline opencode codebuff ampcode worker"

# Auto-detect container runtime: prefer podman, fall back to docker
container_cmd := `which podman 2>/dev/null && echo podman || echo docker`

# Auto-detect compose command
compose_cmd := `which podman-compose 2>/dev/null && echo podman-compose || echo "docker compose"`

# =============================================================================
# Build
# =============================================================================

# Show which container runtime is active
runtime:
    @echo "Container runtime: {{container_cmd}}"
    @{{container_cmd}} version 2>&1 | grep -i "^Version:" | head -1 || true

# Build all 3 base images
build-bases:
    @echo "=== Building base images ({{container_cmd}}) ==="
    {{container_cmd}} build -f bases/Dockerfile.node    -t achaean-base-node:latest    .
    {{container_cmd}} build -f bases/Dockerfile.python  -t achaean-base-python:latest  .
    {{container_cmd}} build -f bases/Dockerfile.minimal -t achaean-base-minimal:latest .
    @echo "=== Bases built ==="

# Build a single vessel image (builds its base first)
# Usage: just build-vessel claude
build-vessel NAME:
    #!/usr/bin/env bash
    set -euo pipefail
    container_cmd="$(which podman 2>/dev/null || echo docker)"
    case "{{NAME}}" in
        claude|codex|cline|codebuff|ampcode) base="achaean-base-node" ;;
        aider)                               base="achaean-base-python" ;;
        goose|opencode|worker)               base="achaean-base-minimal" ;;
        *) echo "Unknown vessel: {{NAME}}"; exit 1 ;;
    esac
    echo "Container runtime: ${container_cmd}"
    echo "Building base: ${base}"
    ${container_cmd} build -f "bases/Dockerfile.${base#achaean-base-}" -t "${base}:latest" .
    echo "Building vessel: achaean-{{NAME}}"
    ${container_cmd} build -f "vessels/{{NAME}}/Dockerfile" \
        --build-arg BASE_IMAGE="${base}:latest" \
        -t "achaean-{{NAME}}:latest" .
    echo "Done: achaean-{{NAME}}:latest"

# Build all images (bases then vessels) via shell script
build-all:
    @echo "=== Building all AchaeanFleet images ({{container_cmd}}) ==="
    CONTAINER_CMD={{container_cmd}} bash scripts/build-all.sh
    @echo "=== All images built ==="

# Verify all 9 vessel images exist locally (podman or docker)
verify:
    #!/usr/bin/env bash
    set -euo pipefail
    container_cmd="$(which podman 2>/dev/null || echo docker)"
    echo "Verifying images with: ${container_cmd}"
    failed=0
    for vessel in claude codex aider goose cline opencode codebuff ampcode worker; do
        if ${container_cmd} image exists "achaean-${vessel}:latest" 2>/dev/null || \
           ${container_cmd} inspect "achaean-${vessel}:latest" &>/dev/null; then
            echo "  ✓ achaean-${vessel}:latest"
        else
            echo "  ✗ achaean-${vessel}:latest — NOT FOUND"
            failed=$((failed + 1))
        fi
    done
    [ $failed -eq 0 ] && echo "All images verified." || { echo "${failed} image(s) missing. Run: just build-all"; exit 1; }

# =============================================================================
# Pods (Podman)
# =============================================================================

# Start a named pod from pods/ YAML spec (Podman only)
# Usage: just pod-up claude
pod-up NAME:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! which podman &>/dev/null; then echo "podman required for pod commands"; exit 1; fi
    podman play kube pods/{{NAME}}-pod.yaml
    echo "Pod achaean-{{NAME}}-pod started"

# Stop and remove a pod
# Usage: just pod-down claude
pod-down NAME:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! which podman &>/dev/null; then echo "podman required for pod commands"; exit 1; fi
    podman play kube pods/{{NAME}}-pod.yaml --down
    echo "Pod achaean-{{NAME}}-pod stopped"

# List running pods
pod-list:
    @podman pod list 2>/dev/null || echo "podman not available"

# =============================================================================
# Test
# =============================================================================

# Smoke-test all vessel images (requires dagger)
test:
    @echo "=== Running image smoke tests ==="
    npx ts-node dagger/pipeline.ts test

# Validate all compose YAML files parse without errors (no images needed)
test-compose:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "=== Validating compose files ==="
    for f in compose/docker-compose.claude-only.yml compose/docker-compose.mesh.yml compose/docker-compose.smoke.yml; do
        echo "  Checking $f ..."
        docker compose -f "$f" config --quiet || { echo "FAIL: $f"; exit 1; }
        echo "  OK: $f"
    done
    echo "=== All compose files valid ==="

# Build worker vessel, start it, probe /health on port 23080, then tear down
test-smoke:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "=== Smoke test: building worker vessel ==="
    docker build -f bases/Dockerfile.minimal -t achaean-base-minimal:latest .
    docker build -f vessels/worker/Dockerfile \
        --build-arg BASE_IMAGE=achaean-base-minimal:latest \
        -t achaean-worker:latest .
    echo "=== Starting smoke container ==="
    docker compose -f compose/docker-compose.smoke.yml up -d
    echo "=== Waiting for /health on port 23080 (up to 60s) ==="
    ok=0
    for i in $(seq 1 30); do
        if wget -qO- http://localhost:23080/health 2>/dev/null | grep -q '"status"'; then
            echo "  Health OK after $((i * 2))s"
            ok=1
            break
        fi
        sleep 2
    done
    docker compose -f compose/docker-compose.smoke.yml down --volumes --remove-orphans || true
    [ $ok -eq 1 ] || { echo "FAIL: /health did not respond within 60s"; exit 1; }
    echo "=== Smoke test passed ==="

# =============================================================================
# Push
# =============================================================================

# Push all images to registry
push:
    @echo "=== Pushing images to {{registry}} ==="
    npx ts-node dagger/pipeline.ts push --registry {{registry}}

# Push and notify ProjectProteus to trigger Myrmidons apply
push-and-notify:
    just push
    bash scripts/notify-proteus.sh

# =============================================================================
# Compose
# =============================================================================

# Start Claude-only compose (Phase 3)
compose-up:
    {{compose_cmd}} -f compose/docker-compose.claude-only.yml up -d

# Stop Claude-only compose
compose-down:
    {{compose_cmd}} -f compose/docker-compose.claude-only.yml down

# Start full mesh compose (Phase 4)
mesh-up:
    {{compose_cmd}} -f compose/docker-compose.mesh.yml up -d

# Stop full mesh compose
mesh-down:
    {{compose_cmd}} -f compose/docker-compose.mesh.yml down

# =============================================================================
# Cleanup
# =============================================================================

# Remove all achaean-* images from local store
clean:
    #!/usr/bin/env bash
    set -euo pipefail
    container_cmd="$(which podman 2>/dev/null || echo docker)"
    echo "=== Removing achaean-* images (${container_cmd}) ==="
    ${container_cmd} images --format '{{{{.Repository}}}}:{{{{.Tag}}}}' \
        | grep '^achaean-' \
        | xargs -r ${container_cmd} rmi || true
    echo "=== Cleaned ==="
