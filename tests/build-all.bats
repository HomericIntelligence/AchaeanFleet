#!/usr/bin/env bats
# Smoke tests for scripts/build-all.sh
# Asserts: CONTAINER_CMD env var controls which container runtime is invoked
# Asserts: default CONTAINER_CMD is "docker"
# Asserts: CONTAINER_CMD=podman uses podman instead

SCRIPT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/scripts/build-all.sh"

setup() {
    export CALL_LOG
    CALL_LOG="$(mktemp)"
    export MOCK_BIN
    MOCK_BIN="$(mktemp -d)"

    # Create mock docker binary that logs calls and exits 0
    cat > "$MOCK_BIN/docker" <<'EOF'
#!/usr/bin/env bash
echo "$0 $@" >> "$CALL_LOG"
exit 0
EOF
    chmod +x "$MOCK_BIN/docker"

    # Create mock podman binary that logs calls and exits 0
    cat > "$MOCK_BIN/podman" <<'EOF'
#!/usr/bin/env bash
echo "$0 $@" >> "$CALL_LOG"
exit 0
EOF
    chmod +x "$MOCK_BIN/podman"

    # Prepend mock bin dir to PATH so our mocks are found first
    export PATH="$MOCK_BIN:$PATH"
}

teardown() {
    [[ -n "${CALL_LOG:-}" && -f "$CALL_LOG" ]] && rm -f "$CALL_LOG"
    [[ -n "${MOCK_BIN:-}"  && -d "$MOCK_BIN"  ]] && rm -rf "$MOCK_BIN"
    return 0
}

@test "default CONTAINER_CMD uses docker" {
    run bash "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -q "docker build" "$CALL_LOG"
}

@test "CONTAINER_CMD=podman uses podman instead" {
    run env CONTAINER_CMD=podman bash "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -q "podman build" "$CALL_LOG"
}
