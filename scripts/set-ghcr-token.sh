#!/bin/bash
# Store one read-only GHCR credential on every repository in an organization.
#
# AchaeanFleet publishes the fleet CI images as private packages because
# organization policy forbids public container packages. A repository can only
# pull them when it owns a classic token with read:packages. This script
# installs that credential once, at organization scope, so every repository
# inherits it without per-repository setup.
#
# Usage:
#   export GHCR_TOKEN=<classic PAT with read:packages>
#   scripts/set-ghcr-token.sh --dry-run     # show the plan
#   scripts/set-ghcr-token.sh               # organization secret
#   scripts/set-ghcr-token.sh --per-repo    # repository secrets instead
#
# Options:
#   --org NAME          Organization (default: HomericIntelligence)
#   --secret-name NAME  Secret name (default: GHCR_TOKEN)
#   --repos A,B         Limit to these repositories (with --per-repo)
#   --per-repo          Skip the organization secret; write repository secrets
#   --dry-run           Print actions without changing anything
#   --verify IMAGE      Check the token can pull this image
#
# The token is read from GHCR_TOKEN and is never printed, logged, or passed as a
# command-line argument.
set -euo pipefail

ORG="${GHCR_SECRET_ORG:-HomericIntelligence}"
SECRET_NAME="${GHCR_SECRET_NAME:-GHCR_TOKEN}"
REGISTRY="ghcr.io"
NAMESPACE="homericintelligence"
VERIFY_IMAGE="achaean-telemachy-ci"
MODE="organization"
DRY_RUN=0
REPOS=""

usage() {
    # Print the leading comment block, stopping at the first non-comment line.
    awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "${BASH_SOURCE[0]}"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --org) ORG="${2:?--org requires a value}"; shift 2 ;;
        --secret-name) SECRET_NAME="${2:?--secret-name requires a value}"; shift 2 ;;
        --repos) REPOS="${2:?--repos requires a value}"; shift 2 ;;
        --per-repo) MODE="repository"; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        --verify) VERIFY_IMAGE="${2:?--verify requires a value}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if ! command -v gh >/dev/null; then
    echo 'The GitHub CLI (gh) is required.' >&2
    exit 1
fi

if [ -z "${GHCR_TOKEN:-}" ]; then
    echo 'Set GHCR_TOKEN to a classic personal access token with read:packages.' >&2
    echo 'Create one at https://github.com/settings/tokens/new (scope: read:packages).' >&2
    exit 1
fi

# Refuse an unusable credential before it reaches a repository secret. GHCR
# accepts a classic token only as the password half of Basic auth.
verify_token() {
    local image="$1"
    local scope="repository:${NAMESPACE}/${image}:pull"
    local credentials
    local status
    credentials="$(printf 'git:%s' "${GHCR_TOKEN}" | base64 | tr -d '\n')"
    status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
        --header "Authorization: Basic ${credentials}" \
        "https://${REGISTRY}/token?scope=${scope}&service=${REGISTRY}")"
    if [ "${status}" != "200" ]; then
        echo "The credential cannot mint a pull token for ${NAMESPACE}/${image} (HTTP ${status})." >&2
        echo 'A classic token with read:packages for the organization is required.' >&2
        echo 'Fine-grained tokens and unapproved SSO both return 401 here.' >&2
        exit 1
    fi
    echo "Credential pull OK: ${NAMESPACE}/${image}"
}

verify_token "${VERIFY_IMAGE}"

repo_names() {
    if [ -n "${REPOS}" ]; then
        printf '%s\n' "${REPOS}" | tr ',' '\n' | sed '/^$/d'
        return
    fi
    gh repo list "${ORG}" --limit 1000 --json name --jq '.[].name' | sort
}

set_secret() {
    if [ "${DRY_RUN}" -eq 1 ]; then
        echo "[dry-run] gh secret set ${SECRET_NAME} $*"
        return
    fi
    gh secret set "${SECRET_NAME}" "$@" --body "${GHCR_TOKEN}" >/dev/null
    echo "Stored ${SECRET_NAME} $*"
}

if [ "${MODE}" = "organization" ]; then
    # Organization scope is the single-source form: a new repository inherits
    # the credential, and no workflow changes when the fleet adds one.
    repositories="$(repo_names | wc -l | tr -d ' ')"
    echo "Organization ${ORG} has ${repositories} repositories in scope."
    if set_secret --org "${ORG}" --visibility all && [ "${DRY_RUN}" -eq 0 ]; then
        gh api "orgs/${ORG}/actions/secrets/${SECRET_NAME}" --jq '.name' >/dev/null
        echo "Verified organization secret ${ORG}/${SECRET_NAME} (visibility: all)."
    else
        echo "Could not write the organization secret; run with --per-repo," >&2
        echo "which needs admin rights on each repository instead." >&2
        exit 1
    fi
    exit 0
fi

written=0
failed=""
while IFS= read -r repo; do
    [ -n "${repo}" ] || continue
    if set_secret --repo "${ORG}/${repo}"; then
        written=$((written + 1))
    else
        failed="${failed} ${repo}"
    fi
done < <(repo_names)

echo "Repository secrets written: ${written}"
if [ -n "${failed}" ]; then
    echo "Failed repositories:${failed}" >&2
    exit 1
fi
