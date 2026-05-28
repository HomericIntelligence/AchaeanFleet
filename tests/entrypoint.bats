#!/usr/bin/env bats
# Tests for bases/entrypoint.sh credential chain loader
#
# These tests invoke the actual entrypoint script to verify its behavior.
# A test-only override env var (ENTRYPOINT_SECRETS_DIR) allows hermetic testing
# without relying on /run/secrets (which exists only in containers).

ENTRYPOINT="$BATS_TEST_DIRNAME/../bases/entrypoint.sh"

setup() {
    # Create a temp directory for test secrets files so tests are isolated
    # from any real credentials on the host.
    SECRETS_DIR="$(mktemp -d)"
    # Unset any real keys that might be set in the test runner's environment.
    unset ANTHROPIC_API_KEY
    unset OPENAI_API_KEY
}

teardown() {
    [ -d "$SECRETS_DIR" ] && rm -rf "$SECRETS_DIR"
    return 0
}

@test "entrypoint.sh exists and is executable" {
    [ -x "$ENTRYPOINT" ]
}

@test "loads ANTHROPIC_API_KEY from secret file" {
    echo -n "sk-ant-test-123" > "$SECRETS_DIR/anthropic_api_key"
    run env -i HOME="$HOME" PATH="$PATH" ENTRYPOINT_SECRETS_DIR="$SECRETS_DIR" "$ENTRYPOINT" sh -c 'echo "$ANTHROPIC_API_KEY"'
    [ "$status" -eq 0 ]
    [ "$output" = "sk-ant-test-123" ]
}

@test "loads OPENAI_API_KEY from secret file" {
    echo -n "sk-openai-test-456" > "$SECRETS_DIR/openai_api_key"
    run env -i HOME="$HOME" PATH="$PATH" ENTRYPOINT_SECRETS_DIR="$SECRETS_DIR" "$ENTRYPOINT" sh -c 'echo "$OPENAI_API_KEY"'
    [ "$status" -eq 0 ]
    [ "$output" = "sk-openai-test-456" ]
}

@test "passes through existing ANTHROPIC_API_KEY env var when no secret file" {
    # No secret file created — env var should pass through unchanged
    run env -i HOME="$HOME" PATH="$PATH" ENTRYPOINT_SECRETS_DIR="$SECRETS_DIR" ANTHROPIC_API_KEY="sk-from-env" "$ENTRYPOINT" sh -c 'echo "$ANTHROPIC_API_KEY"'
    [ "$status" -eq 0 ]
    [ "$output" = "sk-from-env" ]
}

@test "secret file takes precedence over env var" {
    # When both secret file and env var exist, secret file should win
    echo -n "sk-from-secret" > "$SECRETS_DIR/anthropic_api_key"
    run env -i HOME="$HOME" PATH="$PATH" ENTRYPOINT_SECRETS_DIR="$SECRETS_DIR" ANTHROPIC_API_KEY="sk-from-env" "$ENTRYPOINT" sh -c 'echo "$ANTHROPIC_API_KEY"'
    [ "$status" -eq 0 ]
    [ "$output" = "sk-from-secret" ]
}

@test "leaves ANTHROPIC_API_KEY unset when neither file nor env var present" {
    # No secret file and no env var — key should remain unset
    run env -i HOME="$HOME" PATH="$PATH" ENTRYPOINT_SECRETS_DIR="$SECRETS_DIR" "$ENTRYPOINT" sh -c 'if [ -z "$ANTHROPIC_API_KEY" ]; then echo "UNSET"; else echo "$ANTHROPIC_API_KEY"; fi'
    [ "$status" -eq 0 ]
    [ "$output" = "UNSET" ]
}

@test "execs CMD arguments and propagates exit code" {
    # Verify that entrypoint execs the child command and passes through its exit code
    run env -i HOME="$HOME" PATH="$PATH" ENTRYPOINT_SECRETS_DIR="$SECRETS_DIR" "$ENTRYPOINT" sh -c 'echo "hello"; exit 7'
    [ "$status" -eq 7 ]
    [ "$output" = "hello" ]
}

@test "bash→sh fallback when bash is not on PATH" {
    # When bash is not available, entrypoint should fall back to sh
    # Create a minimal fake PATH with only sh
    FAKE_PATH="$(mktemp -d)"
    ln -s /bin/sh "$FAKE_PATH/sh"
    run env -i HOME="$HOME" PATH="$FAKE_PATH" ENTRYPOINT_SECRETS_DIR="$SECRETS_DIR" "$ENTRYPOINT" bash -c 'echo "via-sh"; exit 0'
    EXIT_CODE="$status"
    rm -rf "$FAKE_PATH"
    [ "$EXIT_CODE" -eq 0 ]
    [ "$output" = "via-sh" ]
}
