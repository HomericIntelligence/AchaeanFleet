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

# Load Anthropic API key from secret file if present
if [ -f /run/secrets/anthropic_api_key ]; then
    ANTHROPIC_API_KEY="$(cat /run/secrets/anthropic_api_key)"
    export ANTHROPIC_API_KEY
fi

# Load OpenAI API key from secret file if present
if [ -f /run/secrets/openai_api_key ]; then
    OPENAI_API_KEY="$(cat /run/secrets/openai_api_key)"
    export OPENAI_API_KEY
fi

# Hand off to the container's CMD (or any arguments passed to docker run)
exec "$@"
