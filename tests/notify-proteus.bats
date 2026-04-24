#!/usr/bin/env bats
# Smoke tests for scripts/notify-proteus.sh
# Asserts: default GITHUB_ORG is "homeric-intelligence" (regression guard for #4)
# Asserts: GITHUB_ORG env var override propagates correctly to the dispatched URL

SCRIPT="$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/scripts/notify-proteus.sh"

setup_mock_curl() {
    local http_code="${1:-204}"
    export CURL_ARGS_FILE
    CURL_ARGS_FILE="$(mktemp)"
    export MOCK_BIN
    MOCK_BIN="$(mktemp -d)"
    export MOCK_HTTP_CODE="$http_code"
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
    [[ -n "${MOCK_BIN:-}"       && -d "$MOCK_BIN"       ]] && rm -rf "$MOCK_BIN"
    return 0
}

@test "missing GITHUB_TOKEN exits 0 with skip message" {
    run env -i PATH="$PATH" GITHUB_TOKEN="" bash "$SCRIPT"
    [ "$status" -eq 0 ]
    [[ "$output" == *"GITHUB_TOKEN not set"* ]]
}

@test "default org is HomericIntelligence" {
    setup_mock_curl 204
    run env GITHUB_TOKEN=test-token bash "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -q "HomericIntelligence" "$CURL_ARGS_FILE"
}

@test "GITHUB_ORG override replaces default org in URL" {
    setup_mock_curl 204
    run env GITHUB_TOKEN=test-token GITHUB_ORG=myorg bash "$SCRIPT"
    [ "$status" -eq 0 ]
    grep -q "myorg" "$CURL_ARGS_FILE"
    ! grep -q "homeric-intelligence" "$CURL_ARGS_FILE"
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
    [[ "$output" == *"failed"* ]]
}
