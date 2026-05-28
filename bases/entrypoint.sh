#!/bin/sh
# AchaeanFleet base entrypoint — credential chain loader
#
# Reads API key secrets from /run/secrets/ (Docker secrets mount) and exports
# them into the environment before exec'ing the container's CMD.
#
# Credential chain (first match wins):
#   1. /run/secrets/anthropic_api_key  → ANTHROPIC_API_KEY
#   2. /run/secrets/openai_api_key     → OPENAI_API_KEY
#   3. Existing env vars pass through unchanged (fallback for plain env mode)
#
# Security note: Docker secrets keep keys out of `docker inspect` output and
# `docker compose config`. The key will still appear in the child process
# environment after exec — true process-env isolation requires the agent tool
# itself to read the secrets file directly.

set -e

# ENTRYPOINT_SECRETS_DIR allows tests to inject a different secrets directory.
# In production, this is unset and defaults to /run/secrets.
SECRETS_DIR_DEFAULT="${ENTRYPOINT_SECRETS_DIR:-/run/secrets}"

# Load Anthropic API key from secret file if present
if [ -f "$SECRETS_DIR_DEFAULT/anthropic_api_key" ]; then
    ANTHROPIC_API_KEY="$(cat "$SECRETS_DIR_DEFAULT/anthropic_api_key")"
    export ANTHROPIC_API_KEY
fi

# Load OpenAI API key from secret file if present
if [ -f "$SECRETS_DIR_DEFAULT/openai_api_key" ]; then
    OPENAI_API_KEY="$(cat "$SECRETS_DIR_DEFAULT/openai_api_key")"
    export OPENAI_API_KEY
fi

# If the command is bash but bash is not available, fall back to sh
if [ "$1" = "bash" ] && ! command -v bash >/dev/null 2>&1; then
    shift
    exec sh "$@"
fi

# Hand off to the container's CMD (or any arguments passed to docker run)
exec "$@"
