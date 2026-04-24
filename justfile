# AchaeanFleet justfile — build helper for all images
# Usage: just <recipe>
# Requires: just, podman (preferred) or docker

# Default: show help
default:
    @just --list

# =============================================================================
# Variables
# =============================================================================

# Override: REGISTRY=ghcr.io/org (default: ghcr.io/homericintelligence) — registry prefix for push
registry := env_var_or_default("REGISTRY", "ghcr.io/homericintelligence")

# Override: TAG=v1.2.3 (default: latest) — image tag applied to all built images
tag := env_var_or_default("TAG", "latest")

bases := "achaean-base-node achaean-base-python achaean-base-minimal"

vessels := "claude codex aider goose cline opencode codebuff ampcode worker"

# Auto-detect container runtime: prefer podman, fall back to docker
container_cmd := `which podman 2>/dev/null && echo podman || echo docker`

# Auto-detect compose command
compose_cmd := `which podman-compose 2>/dev/null && echo podman-compose || echo "docker compose"`

# =============================================================================
# Bootstrap
# =============================================================================

# One-command environment setup for new developers
bootstrap:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "=== AchaeanFleet bootstrap ==="
    echo ""

    # --- Minimum version checks (#158) ---
    check_version() {
        local tool="$1" actual_ver="$2" min_major="$3" min_minor="$4"
        local actual_major actual_minor
        actual_major="$(echo "$actual_ver" | cut -d. -f1)"
        actual_minor="$(echo "$actual_ver" | cut -d. -f2)"
        if [ "$actual_major" -lt "$min_major" ] || \
           { [ "$actual_major" -eq "$min_major" ] && [ "$actual_minor" -lt "$min_minor" ]; }; then
            echo "  WARNING: $tool $actual_ver is below minimum $min_major.$min_minor — upgrade recommended"
        else
            echo "  OK: $tool $actual_ver (>= $min_major.$min_minor)"
        fi
    }

    echo "→ Checking tool versions..."

    # node >= 18
    if command -v node &>/dev/null; then
        node_ver="$(node --version | sed 's/^v//')"
        check_version "node" "$node_ver" 18 0
    else
        echo "  WARNING: node not found — required for Dagger pipeline"
    fi

    # npm >= 8
    if command -v npm &>/dev/null; then
        npm_ver="$(npm --version)"
        check_version "npm" "$npm_ver" 8 0
    else
        echo "  WARNING: npm not found — required for Dagger pipeline"
    fi

    # docker or podman must be present
    if command -v podman &>/dev/null; then
        podman_ver="$(podman version --format '{{`{{.Client.Version}}`}}' 2>/dev/null || podman --version | awk '{print $3}')"
        echo "  OK: podman $podman_ver"
    elif command -v docker &>/dev/null; then
        docker_ver="$(docker version --format '{{`{{.Client.Version}}`}}' 2>/dev/null || docker --version | awk '{print $3}' | tr -d ',')"
        echo "  OK: docker $docker_ver"
    else
        echo "  WARNING: neither docker nor podman found — required to build images"
    fi

    echo ""

    # --- Set up .env (#157) ---
    echo "→ Setting up compose/.env..."
    if [ ! -f compose/.env ]; then
        cp compose/.env.example compose/.env
        echo "  Created compose/.env from .env.example — edit your API keys before running"
    else
        echo "  compose/.env already exists — skipping copy"
    fi

    # Warn if any API key looks like a placeholder
    placeholder_keys=()
    if grep -qE '^ANTHROPIC_API_KEY=($|your_key_here|<.*>|PLACEHOLDER|changeme)' compose/.env 2>/dev/null; then
        placeholder_keys+=("ANTHROPIC_API_KEY")
    fi
    if grep -qE '^OPENAI_API_KEY=($|your_key_here|<.*>|PLACEHOLDER|changeme)' compose/.env 2>/dev/null; then
        placeholder_keys+=("OPENAI_API_KEY")
    fi
    if [ ${#placeholder_keys[@]} -gt 0 ]; then
        echo ""
        echo "  WARNING: the following keys in compose/.env still have placeholder values:"
        for k in "${placeholder_keys[@]}"; do
            echo "    - $k"
        done
        echo "  Edit compose/.env and set real values before running 'just compose-up'."
    fi

    echo ""

    # --- Install Dagger npm dependencies ---
    echo "→ Installing Dagger npm dependencies..."
    cd dagger && npm install
    cd ..

    echo ""

    # --- Show active container runtime ---
    just runtime

    echo ""
    echo "=== Ready. Edit compose/.env then run: just build-all ==="

# =============================================================================
# Build
# =============================================================================

# Show which container runtime is active
runtime:
    @echo "Container runtime: {{container_cmd}}"
    @{{container_cmd}} version 2>&1 | grep -i "^Version:" | head -1 || true

# Build all 3 base images
build-bases:
    #!/usr/bin/env bash
    set -euo pipefail
    container_cmd="$(which podman 2>/dev/null || echo docker)"
    build_date="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    vcs_ref="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
    version="latest"
    echo "=== Building base images (${container_cmd}) ==="
    ${container_cmd} build -f bases/Dockerfile.node    -t achaean-base-node:latest    \
        --build-arg BUILD_DATE="${build_date}" --build-arg VCS_REF="${vcs_ref}" --build-arg VERSION="${version}" .
    ${container_cmd} build -f bases/Dockerfile.python  -t achaean-base-python:latest  \
        --build-arg BUILD_DATE="${build_date}" --build-arg VCS_REF="${vcs_ref}" --build-arg VERSION="${version}" .
    ${container_cmd} build -f bases/Dockerfile.minimal -t achaean-base-minimal:latest \
        --build-arg BUILD_DATE="${build_date}" --build-arg VCS_REF="${vcs_ref}" --build-arg VERSION="${version}" .
    echo "=== Bases built ==="

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
    build_date="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    vcs_ref="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
    ${container_cmd} build -f "vessels/{{NAME}}/Dockerfile" \
        --build-arg BASE_IMAGE="${base}:latest" \
        --build-arg BUILD_DATE="${build_date}" \
        --build-arg VCS_REF="${vcs_ref}" \
        --build-arg VERSION="latest" \
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

# Print OCI labels (build metadata) for a named image
# Usage: just image-info claude
image-info NAME:
    #!/usr/bin/env bash
    set -euo pipefail
    container_cmd="$(which podman 2>/dev/null || echo docker)"
    image="achaean-{{NAME}}:latest"
    echo "=== OCI labels for ${image} ==="
    ${container_cmd} inspect "${image}" \
        | jq -r '.[0].Config.Labels | to_entries[] | "\(.key) = \(.value)"' \
        | grep -E '^org\.opencontainers\.' \
        || echo "(no OCI labels found — image may not be built yet)"

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

# Run all tests: BATS shell tests + dagger image smoke tests
test: test-shell
    @echo "=== Running image smoke tests ==="
    npx ts-node dagger/pipeline.ts test

# Validate all compose YAML files parse without errors (no images needed)
test-compose:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "=== Validating compose files ==="
    for f in compose/docker-compose.claude-only.yml compose/docker-compose.mesh.yml compose/docker-compose.smoke.yml; do
        echo "  Checking $f ..."
        {{compose_cmd}} -f "$f" config --quiet || { echo "FAIL: $f"; exit 1; }
        echo "  OK: $f"
    done
    echo "=== All compose files valid ==="

# Build worker vessel, start it, probe /health on port 23080, then tear down
test-smoke:
    #!/usr/bin/env bash
    set -euo pipefail
    container_cmd="$(which podman 2>/dev/null || echo docker)"
    compose_cmd="$(which podman-compose 2>/dev/null || echo 'docker compose')"
    echo "=== Smoke test: building worker vessel ==="
    ${container_cmd} build -f bases/Dockerfile.minimal -t achaean-base-minimal:latest .
    ${container_cmd} build -f vessels/worker/Dockerfile \
        --build-arg BASE_IMAGE=achaean-base-minimal:latest \
        -t achaean-worker:latest .
    echo "=== Starting smoke container ==="
    ${compose_cmd} -f compose/docker-compose.smoke.yml up -d
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
    ${compose_cmd} -f compose/docker-compose.smoke.yml down --volumes --remove-orphans || true
    [ $ok -eq 1 ] || { echo "FAIL: /health did not respond within 60s"; exit 1; }
    echo "=== Smoke test passed ==="

# Run BATS shell tests only (no container runtime required)
test-shell:
    @echo "=== Running BATS shell tests ==="
    bats -r tests/shell/

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

# Check if TLS certs exist; if not, generate them
certs-check:
    @test -d tls/certs && test -f tls/certs/ca.crt || (echo "TLS certs not found — running generate-certs.sh…" && bash tls/generate-certs.sh)

# Check TLS certificate expiry; warn if any cert expires within 30 days
check-cert-expiry:
    #!/usr/bin/env bash
    set -euo pipefail
    certs=($(find tls/ -name "*.crt" 2>/dev/null || true))
    if [ ${#certs[@]} -eq 0 ]; then
        echo "No TLS certs found in tls/ directory."
        exit 0
    fi
    exit_code=0
    for cert in "${certs[@]}"; do
        if ! openssl x509 -checkend 2592000 -noout -in "$cert" 2>/dev/null; then
            expiry=$(openssl x509 -noout -enddate -in "$cert" 2>/dev/null | cut -d= -f2)
            echo "WARNING: Certificate $cert expires within 30 days on $expiry"
            exit_code=1
        fi
    done
    exit $exit_code

# Start full mesh compose (Phase 4)
mesh-up: (certs-check)
    {{compose_cmd}} -f compose/docker-compose.mesh.yml up -d

# Stop full mesh compose
mesh-down:
    {{compose_cmd}} -f compose/docker-compose.mesh.yml down

# =============================================================================
# Lint
# =============================================================================

# Install pre-commit hooks into .git/hooks (run once after cloning)
lint-install:
    pre-commit install

# Run all linters across all files
lint:
    pre-commit run --all-files

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

# Prune dangling images, stopped containers, and build cache
clean-dangling:
    #!/usr/bin/env bash
    set -euo pipefail
    container_cmd="$(which podman 2>/dev/null || echo docker)"
    echo "=== Pruning dangling images (${container_cmd}) ==="
    ${container_cmd} image prune -f
    echo "=== Pruning stopped containers ==="
    ${container_cmd} container prune -f
    echo "=== Pruning build cache ==="
    ${container_cmd} builder prune -f 2>/dev/null || true
    echo "=== Pruning volumes ==="
    {{container_cmd}} volume prune -f || true
    @echo "=== Disk cleanup complete — check above for reclaimed space ==="

# Full cleanup: remove achaean-* images + dangling layers + build cache
clean-all:
    @echo "=== Full cleanup ==="
    just clean
    just clean-dangling
    @echo "=== All cleaned ==="
