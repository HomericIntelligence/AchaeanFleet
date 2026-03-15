# AchaeanFleet justfile — build helper for all images
# Usage: just <recipe>
# Requires: just, docker

# Default: show help
default:
    @just --list

# =============================================================================
# Variables
# =============================================================================

registry := env_var_or_default("REGISTRY", "ghcr.io/homericintelligence")

bases := "achaean-base-node achaean-base-python achaean-base-minimal"

vessels := "claude codex aider goose cline opencode codebuff ampcode worker"

# =============================================================================
# Build
# =============================================================================

# Build all 3 base images
build-bases:
    @echo "=== Building base images ==="
    docker build -f bases/Dockerfile.node    -t achaean-base-node:latest    .
    docker build -f bases/Dockerfile.python  -t achaean-base-python:latest  .
    docker build -f bases/Dockerfile.minimal -t achaean-base-minimal:latest .
    @echo "=== Bases built ==="

# Build a single vessel image (builds its base first)
# Usage: just build-vessel claude
build-vessel NAME:
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{NAME}}" in
        claude|codex|cline|codebuff|ampcode) base="achaean-base-node" ;;
        aider)                               base="achaean-base-python" ;;
        goose|opencode|worker)               base="achaean-base-minimal" ;;
        *) echo "Unknown vessel: {{NAME}}"; exit 1 ;;
    esac
    echo "Building base: ${base}"
    docker build -f "bases/Dockerfile.${base#achaean-base-}" -t "${base}:latest" .
    echo "Building vessel: achaean-{{NAME}}"
    docker build -f "vessels/{{NAME}}/Dockerfile" \
        --build-arg BASE_IMAGE="${base}:latest" \
        -t "achaean-{{NAME}}:latest" .
    echo "Done: achaean-{{NAME}}:latest"

# Build all images (bases then vessels) via shell script
build-all:
    @echo "=== Building all AchaeanFleet images ==="
    bash scripts/build-all.sh
    @echo "=== All images built ==="

# =============================================================================
# Test
# =============================================================================

# Smoke-test all vessel images (requires dagger)
test:
    @echo "=== Running image smoke tests ==="
    npx ts-node dagger/pipeline.ts test

# =============================================================================
# Push
# =============================================================================

# Push all images to registry
push:
    @echo "=== Pushing images to {{registry}} ==="
    npx ts-node dagger/pipeline.ts push --registry {{registry}}

# =============================================================================
# Compose
# =============================================================================

# Start Claude-only compose (Phase 3)
compose-up:
    docker compose -f compose/docker-compose.claude-only.yml up -d

# Stop Claude-only compose
compose-down:
    docker compose -f compose/docker-compose.claude-only.yml down

# Start full mesh compose (Phase 4)
mesh-up:
    docker compose -f compose/docker-compose.mesh.yml up -d

# Stop full mesh compose
mesh-down:
    docker compose -f compose/docker-compose.mesh.yml down

# =============================================================================
# Cleanup
# =============================================================================

# Remove all achaean-* images from local Docker
clean:
    @echo "=== Removing achaean-* images ==="
    docker images --format '{{{{.Repository}}}}:{{{{.Tag}}}}' \
        | grep '^achaean-' \
        | xargs -r docker rmi || true
    @echo "=== Cleaned ==="
