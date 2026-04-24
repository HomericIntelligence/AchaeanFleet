#!/usr/bin/env bash
# scripts/load-secrets.sh — Load secrets from SOPS, age, or environment
#
# Loads ANTHROPIC_API_KEY and OPENAI_API_KEY from encrypted files (SOPS/age)
# or from environment variables, writing them to compose/secrets/ with 600 mode.
#
# Usage:
#   bash scripts/load-secrets.sh              # Use env method (default)
#   bash scripts/load-secrets.sh --tool sops  # Decrypt with SOPS
#   bash scripts/load-secrets.sh --tool age   # Decrypt with age
#   bash scripts/load-secrets.sh teardown     # Remove secret files
#
# Environment variables (for --tool env):
#   ANTHROPIC_API_KEY
#   OPENAI_API_KEY
#
# For --tool age, expects:
#   ~/.age/key.txt (age private key)
#   compose/secrets/anthropic_api_key.enc
#   compose/secrets/openai_api_key.enc (optional)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SECRETS_DIR="${REPO_ROOT}/compose/secrets"

# Parse arguments
TOOL="${1:-env}"

# =============================================================================
# Helper functions
# =============================================================================

warn() {
    echo "⚠️  $*" >&2
}

die() {
    echo "❌ Error: $*" >&2
    exit 1
}

info() {
    echo "ℹ️  $*"
}

# =============================================================================
# Main logic
# =============================================================================

mkdir -p "${SECRETS_DIR}"

case "${TOOL}" in
    teardown)
        # Remove secret files
        info "Removing secret files..."
        rm -f "${SECRETS_DIR}/anthropic_api_key"
        rm -f "${SECRETS_DIR}/openai_api_key"
        info "Secrets cleaned up. Remember to securely erase backup copies if they exist."
        ;;

    env)
        # Load from environment variables
        if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
            die "ANTHROPIC_API_KEY not set in environment"
        fi

        info "Loading secrets from environment..."

        # Write ANTHROPIC_API_KEY
        echo -n "${ANTHROPIC_API_KEY}" > "${SECRETS_DIR}/anthropic_api_key"
        chmod 600 "${SECRETS_DIR}/anthropic_api_key"
        info "Wrote compose/secrets/anthropic_api_key"

        # Write OPENAI_API_KEY if set
        if [[ -n "${OPENAI_API_KEY:-}" ]]; then
            echo -n "${OPENAI_API_KEY}" > "${SECRETS_DIR}/openai_api_key"
            chmod 600 "${SECRETS_DIR}/openai_api_key"
            info "Wrote compose/secrets/openai_api_key"
        fi

        warn "Remember to run 'bash scripts/load-secrets.sh teardown' before shutdown to wipe secrets"
        ;;

    sops)
        # Decrypt with SOPS
        if ! command -v sops &> /dev/null; then
            die "sops not found in PATH. Install it from https://github.com/getsops/sops"
        fi

        info "Decrypting with SOPS..."

        # Decrypt ANTHROPIC_API_KEY
        if [[ -f "${SECRETS_DIR}/anthropic_api_key.enc" ]]; then
            sops -d "${SECRETS_DIR}/anthropic_api_key.enc" > "${SECRETS_DIR}/anthropic_api_key"
            chmod 600 "${SECRETS_DIR}/anthropic_api_key"
            info "Wrote compose/secrets/anthropic_api_key"
        else
            die "compose/secrets/anthropic_api_key.enc not found"
        fi

        # Decrypt OPENAI_API_KEY if encrypted file exists
        if [[ -f "${SECRETS_DIR}/openai_api_key.enc" ]]; then
            sops -d "${SECRETS_DIR}/openai_api_key.enc" > "${SECRETS_DIR}/openai_api_key"
            chmod 600 "${SECRETS_DIR}/openai_api_key"
            info "Wrote compose/secrets/openai_api_key"
        fi

        warn "Remember to run 'bash scripts/load-secrets.sh teardown' before shutdown to wipe secrets"
        ;;

    age)
        # Decrypt with age
        if ! command -v age &> /dev/null; then
            die "age not found in PATH. Install it from https://github.com/FiloSottile/age"
        fi

        AGE_KEY="${HOME}/.age/key.txt"
        if [[ ! -f "${AGE_KEY}" ]]; then
            die "age key not found at ${AGE_KEY}"
        fi

        info "Decrypting with age..."

        # Decrypt ANTHROPIC_API_KEY
        if [[ -f "${SECRETS_DIR}/anthropic_api_key.enc" ]]; then
            age -d -i "${AGE_KEY}" "${SECRETS_DIR}/anthropic_api_key.enc" > "${SECRETS_DIR}/anthropic_api_key"
            chmod 600 "${SECRETS_DIR}/anthropic_api_key"
            info "Wrote compose/secrets/anthropic_api_key"
        else
            die "compose/secrets/anthropic_api_key.enc not found"
        fi

        # Decrypt OPENAI_API_KEY if encrypted file exists
        if [[ -f "${SECRETS_DIR}/openai_api_key.enc" ]]; then
            age -d -i "${AGE_KEY}" "${SECRETS_DIR}/openai_api_key.enc" > "${SECRETS_DIR}/openai_api_key"
            chmod 600 "${SECRETS_DIR}/openai_api_key"
            info "Wrote compose/secrets/openai_api_key"
        fi

        warn "Remember to run 'bash scripts/load-secrets.sh teardown' before shutdown to wipe secrets"
        ;;

    *)
        die "Unknown tool: ${TOOL}. Use 'env', 'sops', 'age', or 'teardown'"
        ;;
esac

info "Done."
