MOCKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../mocks" && pwd)"

setup_mocks() {
    export PATH="${MOCKS_DIR}:${PATH}"
    export BUILD_DATE=""
    export VCS_REF=""
}

clean_state() {
    unset CONTAINER_CMD
    unset DOCKER_MOCK_EXIT
    unset TAG
}
