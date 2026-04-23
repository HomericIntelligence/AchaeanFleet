#!/usr/bin/env bats

load helpers/common

SCRIPT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../../../../scripts" && pwd)/build-all.sh"

setup() {
    setup_mocks
    clean_state
}

@test "CONTAINER_CMD defaults to docker when unset" {
    unset CONTAINER_CMD
    run bash "$SCRIPT"
    [ "$status" -eq 0 ]
    [[ "$output" == *"docker build"* ]]
}

@test "explicit CONTAINER_CMD=podman is honored" {
    export CONTAINER_CMD=podman
    run bash "$SCRIPT"
    [ "$status" -eq 0 ]
    [[ "$output" == *"podman build"* ]]
}

@test "script exits non-zero when a build fails" {
    export DOCKER_MOCK_EXIT=1
    run bash "$SCRIPT"
    [ "$status" -eq 1 ]
}
