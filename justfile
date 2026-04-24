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

# Check pinned tool versions against latest available releases
check-versions:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "=== Checking pinned tool versions ==="
    exit_code=0

    # Goose (GitHub releases API)
    echo ""
    echo "Checking GOOSE_VERSION..."
    goose_pinned="1.31.1"
    goose_latest=$(curl -s https://api.github.com/repos/block/goose/releases/latest \
        | grep -oP '"tag_name":\s*"v\K[^"]+' | head -1 || echo "unknown")
    if [ "$goose_latest" = "unknown" ]; then
        echo "  GOOSE: pinned=$goose_pinned latest=unknown [ERROR: API call failed]"
        exit_code=1
    elif [ "$goose_pinned" = "$goose_latest" ]; then
        echo "  GOOSE: pinned=$goose_pinned latest=$goose_latest [UP-TO-DATE]"
    else
        echo "  GOOSE: pinned=$goose_pinned latest=$goose_latest [OUTDATED]"
        exit_code=1
    fi

    # OpenCode (GitHub releases API)
    echo ""
    echo "Checking OPENCODE_VERSION..."
    opencode_pinned="v1.4.3"
    opencode_latest=$(curl -s https://api.github.com/repos/sst/opencode/releases/latest \
        | grep -oP '"tag_name":\s*"\K[^"]+' | head -1 || echo "unknown")
    if [ "$opencode_latest" = "unknown" ]; then
        echo "  OPENCODE: pinned=$opencode_pinned latest=unknown [ERROR: API call failed]"
        exit_code=1
    elif [ "$opencode_pinned" = "$opencode_latest" ]; then
        echo "  OPENCODE: pinned=$opencode_pinned latest=$opencode_latest [UP-TO-DATE]"
    else
        echo "  OPENCODE: pinned=$opencode_pinned latest=$opencode_latest [OUTDATED]"
        exit_code=1
    fi

    # YQ (GitHub releases API)
    echo ""
    echo "Checking YQ_VERSION..."
    yq_pinned="v4.53.2"
    yq_latest=$(curl -s https://api.github.com/repos/mikefarah/yq/releases/latest \
        | grep -oP '"tag_name":\s*"\K[^"]+' | head -1 || echo "unknown")
    if [ "$yq_latest" = "unknown" ]; then
        echo "  YQ: pinned=$yq_pinned latest=unknown [ERROR: API call failed]"
        exit_code=1
    elif [ "$yq_pinned" = "$yq_latest" ]; then
        echo "  YQ: pinned=$yq_pinned latest=$yq_latest [UP-TO-DATE]"
    else
        echo "  YQ: pinned=$yq_pinned latest=$yq_latest [OUTDATED]"
        exit_code=1
    fi

    echo ""
    if [ $exit_code -eq 0 ]; then
        echo "=== All versions up-to-date ==="
    else
        echo "=== Some versions are outdated or API calls failed ==="
    fi
    exit $exit_code

# Rotate checksum for a tool when updating to a new version
# Usage: just rotate-checksum goose 1.32.0
# Supports: goose, opencode, yq
rotate-checksum TOOL VERSION:
    #!/usr/bin/env bash
    set -euo pipefail

    tool="{{TOOL}}"
    version="{{VERSION}}"

    case "$tool" in
        goose)
            echo "=== Rotating checksum for goose v${version} ==="

            # Find and remove old checksum files
            old_files=$(find scripts/checksums -name "goose-*-linux-x86_64.sha256" -o -name "goose-*-linux-aarch64.sha256" 2>/dev/null || true)

            # Download and compute checksums for both architectures
            echo "Computing SHA256 for amd64..."
            amd64_sha=$(curl -fsSL "https://github.com/block/goose/releases/download/v${version}/goose-x86_64-unknown-linux-gnu.tar.gz" | sha256sum | awk '{print $1}')
            echo "  AMD64: $amd64_sha"

            echo "Computing SHA256 for arm64..."
            arm64_sha=$(curl -fsSL "https://github.com/block/goose/releases/download/v${version}/goose-aarch64-unknown-linux-gnu.tar.gz" | sha256sum | awk '{print $1}')
            echo "  ARM64: $arm64_sha"

            # Write new checksum files (version-in-filename format for reference)
            echo "$amd64_sha" > "scripts/checksums/goose-${version}-linux-x86_64.sha256"
            echo "$arm64_sha" > "scripts/checksums/goose-${version}-linux-aarch64.sha256"
            echo "Wrote: scripts/checksums/goose-${version}-linux-x86_64.sha256"
            echo "Wrote: scripts/checksums/goose-${version}-linux-aarch64.sha256"

            # Update the Dockerfile ARG
            sed -i "s/ARG GOOSE_VERSION=.*/ARG GOOSE_VERSION=${version}/" vessels/goose/Dockerfile
            sed -i "s/ARG GOOSE_AMD64_SHA256=.*/ARG GOOSE_AMD64_SHA256=${amd64_sha}/" vessels/goose/Dockerfile
            sed -i "s/ARG GOOSE_ARM64_SHA256=.*/ARG GOOSE_ARM64_SHA256=${arm64_sha}/" vessels/goose/Dockerfile
            echo "Updated: vessels/goose/Dockerfile"

            # Remove old checksum files
            if [ -n "$old_files" ]; then
                echo "$old_files" | xargs rm -f
                echo "Removed old checksum files"
            fi

            echo ""
            echo "=== Checksum rotation complete for goose ==="
            echo "Next steps:"
            echo "  1. Review changes: git diff vessels/goose/Dockerfile scripts/checksums/"
            echo "  2. Test the build: just build-vessel goose"
            echo "  3. Commit: git commit -m 'chore(goose): bump to v${version}'"
            ;;

        opencode)
            echo "=== Rotating checksum for opencode ${version} ==="

            # Find and remove old checksum files
            old_files=$(find scripts/checksums -name "opencode-*-linux-x64.sha256" 2>/dev/null || true)

            # Download and compute checksum
            echo "Computing SHA256 for opencode..."
            sha=$(curl -fsSL "https://github.com/sst/opencode/releases/download/${version}/opencode_linux_amd64.tar.gz" | sha256sum | awk '{print $1}')
            echo "  SHA256: $sha"

            # Write new checksum file (version-in-filename format for reference)
            echo "$sha" > "scripts/checksums/opencode-${version}-linux-x64.sha256"
            echo "Wrote: scripts/checksums/opencode-${version}-linux-x64.sha256"

            # Update the Dockerfile ENV
            sed -i "s/ENV OPENCODE_VERSION=.*/ENV OPENCODE_VERSION=${version}/" vessels/opencode/Dockerfile
            echo "Updated: vessels/opencode/Dockerfile"

            # Remove old checksum files
            if [ -n "$old_files" ]; then
                echo "$old_files" | xargs rm -f
                echo "Removed old checksum files"
            fi

            echo ""
            echo "=== Checksum rotation complete for opencode ==="
            echo "Next steps:"
            echo "  1. Review changes: git diff vessels/opencode/Dockerfile scripts/checksums/"
            echo "  2. Test the build: just build-vessel opencode"
            echo "  3. Commit: git commit -m 'chore(opencode): bump to ${version}'"
            ;;

        yq)
            echo "=== Rotating checksum for yq ${version} ==="

            # Find and remove old checksum files
            old_files=$(find scripts/checksums -name "yq-*-linux-x64.sha256" 2>/dev/null || true)

            # Download and compute checksum
            echo "Computing SHA256 for yq..."
            sha=$(curl -fsSL "https://github.com/mikefarah/yq/releases/download/${version}/yq_linux_amd64" | sha256sum | awk '{print $1}')
            echo "  SHA256: $sha"

            # Write new checksum file (version-in-filename format for reference)
            echo "$sha" > "scripts/checksums/yq-${version}-linux-x64.sha256"
            echo "Wrote: scripts/checksums/yq-${version}-linux-x64.sha256"

            # Update the Dockerfile ARG
            sed -i "s/ARG YQ_VERSION=.*/ARG YQ_VERSION=${version}/" vessels/worker/Dockerfile
            echo "Updated: vessels/worker/Dockerfile"

            # Remove old checksum files
            if [ -n "$old_files" ]; then
                echo "$old_files" | xargs rm -f
                echo "Removed old checksum files"
            fi

            echo ""
            echo "=== Checksum rotation complete for yq ==="
            echo "Next steps:"
            echo "  1. Review changes: git diff vessels/worker/Dockerfile scripts/checksums/"
            echo "  2. Test the build: just build-vessel worker"
            echo "  3. Commit: git commit -m 'chore(yq): bump to ${version}'"
            ;;

        *)
            echo "ERROR: Unknown tool: $tool"
            echo "Supported tools: goose, opencode, yq"
            exit 1
            ;;
    esac

# =============================================================================
# Workspace
# =============================================================================

# Create all required agent workspace directories in ~/Agents/
# Safe to run multiple times (mkdir -p is idempotent)
init-workspaces:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "=== Creating agent workspace directories ==="
    base_dir="${HOME}/Agents"
    agents=(Aindrea Eris Baird Vegai Pallas Codex-1 Aider-1 Goose-1 Cline-1 Opencode-1 Codebuff-1 Ampcode-1 Worker-1)
    for agent in "${agents[@]}"; do
        mkdir -p "${base_dir}/${agent}"
        echo "  Created: ${base_dir}/${agent}"
    done
    echo "=== All workspace directories initialized ==="

# Validate all *_PROJECT paths exist and are not bare home directories
# Reads from compose/.env if it exists, otherwise uses environment variables
validate-workspaces:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "=== Validating workspace paths ==="

    # Source .env if it exists, otherwise rely on environment
    env_file="compose/.env"
    if [ -f "$env_file" ]; then
        # Load .env into environment, but don't override existing vars
        set +o nounset
        set -a
        source "$env_file"
        set +a
        set -o nounset
    else
        echo "  Note: compose/.env not found; using environment variables"
    fi

    # Track failures
    failed=0

    # Home directory patterns to reject
    home_patterns=("$HOME" "/root" "/home/mvillmow")

    # Helper function to check if a path is a bare home directory
    is_home_dir() {
        local path="$1"
        for pattern in "${home_patterns[@]}"; do
            if [ "$path" = "$pattern" ]; then
                return 0  # true — it is a home dir
            fi
        done
        return 1  # false — it is not a home dir
    }

    # Check WORKSPACE_ROOT
    workspace_root="${WORKSPACE_ROOT:-}"
    if [ -z "$workspace_root" ]; then
        echo "  ERROR: WORKSPACE_ROOT not set"
        failed=$((failed + 1))
    elif ! [ -d "$workspace_root" ]; then
        echo "  ERROR: WORKSPACE_ROOT does not exist: $workspace_root"
        failed=$((failed + 1))
    elif is_home_dir "$workspace_root"; then
        echo "  ERROR: WORKSPACE_ROOT is a bare home directory: $workspace_root"
        failed=$((failed + 1))
    else
        echo "  OK: WORKSPACE_ROOT=$workspace_root"
    fi

    # Check each *_PROJECT path
    project_vars=(VEGAI_PROJECT CODEX_PROJECT AIDER_PROJECT GOOSE_PROJECT CLINE_PROJECT OPENCODE_PROJECT CODEBUFF_PROJECT AMPCODE_PROJECT)
    for var in "${project_vars[@]}"; do
        path="${!var:-}"

        if [ -z "$path" ]; then
            echo "  WARNING: $var not set (will use defaults at runtime)"
            continue
        fi

        if ! [ -d "$path" ]; then
            echo "  ERROR: $var path does not exist: $path"
            failed=$((failed + 1))
        elif is_home_dir "$path"; then
            echo "  ERROR: $var is a bare home directory: $path"
            failed=$((failed + 1))
        else
            echo "  OK: $var=$path"
        fi
    done

    # If no env file and no vars are set, that's OK (not configured yet)
    if [ ! -f "$env_file" ] && [ ${#project_vars[@]} -eq 0 ]; then
        echo "  Note: No configuration detected; skipping validation"
        echo "=== Validation complete ==="
        exit 0
    fi

    echo "=== Validation complete ==="
    if [ $failed -gt 0 ]; then
        echo "FAIL: $failed check(s) failed"
        exit 1
    fi
    exit 0

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
