#!/usr/bin/env bats
# Tests for scripts/notify-proteus.sh
#
# Dispatch chain under test:
#   AchaeanFleet → ProjectProteus (image-pushed)
#                → Myrmidons (agamemnon-apply) via Proteus cross-repo-dispatch.yml

SCRIPT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/scripts/notify-proteus.sh"

# ── helpers ──────────────────────────────────────────────────────────────────

# Installs a mock `curl` on PATH that records its arguments to CURL_ARGS_FILE
# and returns a configurable HTTP status code (default 204).
setup_mock_curl() {
    local http_code="${1:-204}"
    export CURL_ARGS_FILE="$(mktemp)"
    export MOCK_HTTP_CODE="$http_code"

    export MOCK_BIN="$(mktemp -d)"
    cat > "$MOCK_BIN/curl" <<EOF
#!/usr/bin/env bash
echo "\$@" > "$CURL_ARGS_FILE"
echo "$http_code"
EOF
    chmod +x "$MOCK_BIN/curl"
    export PATH="$MOCK_BIN:$PATH"
}

teardown() {
    [[ -n "${CURL_ARGS_FILE:-}" && -f "$CURL_ARGS_FILE" ]] && rm -f "$CURL_ARGS_FILE"
    [[ -n "${MOCK_BIN:-}" && -d "$MOCK_BIN" ]]             && rm -rf "$MOCK_BIN"
    return 0
}

# ── tests ─────────────────────────────────────────────────────────────────────

@test "missing GITHUB_TOKEN exits 0 with skip message" {
    run env -i PATH="$PATH" GITHUB_TOKEN="" bash "$SCRIPT"
    [ "$status" -eq 0 ]
    [[ "$output" == *"GITHUB_TOKEN not set"* ]]
}

@test "unset GITHUB_TOKEN also exits 0 with skip message" {
    run bash -c "unset GITHUB_TOKEN; bash '$SCRIPT'"
    [ "$status" -eq 0 ]
    [[ "$output" == *"GITHUB_TOKEN not set"* ]]
}

@test "dispatches to ProjectProteus by default" {
    setup_mock_curl 204
    run env GITHUB_TOKEN=test-token bash "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -q "ProjectProteus" "$CURL_ARGS_FILE"
}

@test "NOTIFY_REPO override is respected" {
    setup_mock_curl 204
    run env GITHUB_TOKEN=test-token NOTIFY_REPO=SomeOtherRepo bash "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -q "SomeOtherRepo" "$CURL_ARGS_FILE"
}

@test "does NOT dispatch to Myrmidons by default" {
    setup_mock_curl 204
    run env GITHUB_TOKEN=test-token bash "$SCRIPT"
    [ "$status" -eq 0 ]
    ! grep -q "Myrmidons" "$CURL_ARGS_FILE"
}

@test "client_payload contains host field" {
    setup_mock_curl 204
    run env GITHUB_TOKEN=test-token bash "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -q '"host"' "$CURL_ARGS_FILE"
}

@test "AGAMEMNON_HOST default is hermes" {
    setup_mock_curl 204
    run env GITHUB_TOKEN=test-token bash "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -q '"host": "hermes"' "$CURL_ARGS_FILE"
}

@test "AGAMEMNON_HOST override is passed in payload" {
    setup_mock_curl 204
    run env GITHUB_TOKEN=test-token AGAMEMNON_HOST=custom-host bash "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -q '"host": "custom-host"' "$CURL_ARGS_FILE"
}

@test "client_payload contains image_tag field" {
    setup_mock_curl 204
    run env GITHUB_TOKEN=test-token IMAGE_TAG=sha-abc123 bash "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -q '"image_tag": "sha-abc123"' "$CURL_ARGS_FILE"
}

@test "IMAGE_TAG defaults to latest when not set" {
    setup_mock_curl 204
    run env GITHUB_TOKEN=test-token bash "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -q '"image_tag": "latest"' "$CURL_ARGS_FILE"
}

@test "client_payload contains source field set to AchaeanFleet" {
    setup_mock_curl 204
    run env GITHUB_TOKEN=test-token bash "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -q '"source": "AchaeanFleet"' "$CURL_ARGS_FILE"
}

@test "event_type is image-pushed" {
    setup_mock_curl 204
    run env GITHUB_TOKEN=test-token bash "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -q '"event_type": "image-pushed"' "$CURL_ARGS_FILE"
}

@test "HTTP 204 response exits 0" {
    setup_mock_curl 204
    run env GITHUB_TOKEN=test-token bash "$SCRIPT"
    [ "$status" -eq 0 ]
    [[ "$output" == *"successfully"* ]]
}

@test "non-204 response exits 1" {
    setup_mock_curl 422
    run env GITHUB_TOKEN=test-token bash "$SCRIPT"
    [ "$status" -eq 1 ]
    [[ "$output" == *"Dispatch failed"* ]]
}

@test "HTTP 404 response exits 1" {
    setup_mock_curl 404
    run env GITHUB_TOKEN=test-token bash "$SCRIPT"
    [ "$status" -eq 1 ]
}

@test "uses homericintelligence org by default" {
    setup_mock_curl 204
    run env GITHUB_TOKEN=test-token bash "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -q "homericintelligence" "$CURL_ARGS_FILE"
}

@test "GITHUB_ORG override is respected" {
    setup_mock_curl 204
    run env GITHUB_TOKEN=test-token GITHUB_ORG=myorg bash "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -q "myorg" "$CURL_ARGS_FILE"
}
