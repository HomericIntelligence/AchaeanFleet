#!/usr/bin/env bash
# Resolves current SHA256 digests for base images and rewrites FROM lines in bases/Dockerfile.*.
#
# Usage:
#   ./scripts/update-base-digests.sh           # update digests in-place
#   ./scripts/update-base-digests.sh --check   # exit non-zero if any digest is stale
#
# Requires: docker (with buildx), sed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CHECK_MODE=false
if [[ "${1:-}" == "--check" ]]; then
  CHECK_MODE=true
fi

declare -A IMAGE_TO_DOCKERFILE=(
  ["node:20-slim"]="bases/Dockerfile.node"
  ["python:3.12-slim"]="bases/Dockerfile.python"
  ["debian:bookworm-slim"]="bases/Dockerfile.minimal"
)

stale_count=0

for image in "${!IMAGE_TO_DOCKERFILE[@]}"; do
  dockerfile="${REPO_ROOT}/${IMAGE_TO_DOCKERFILE[$image]}"

  echo "Resolving digest for ${image}..."
  live_digest=$(docker buildx imagetools inspect --format '{{json .Manifest}}' "${image}" 2>/dev/null | grep -o '"digest":"sha256:[a-f0-9]*"' | head -1 | sed 's/"digest":"//;s/"//')

  if [[ -z "$live_digest" ]]; then
    echo "ERROR: Could not resolve digest for ${image}" >&2
    exit 1
  fi

  pinned="${image}@${live_digest}"
  current_line=$(grep "^FROM " "${dockerfile}")
  current_digest=$(echo "${current_line}" | grep -o 'sha256:[a-f0-9]\{64\}' || true)

  if [[ "$live_digest" == "$current_digest" ]]; then
    echo "  OK: ${image} digest is current (${live_digest:0:16}...)"
    continue
  fi

  if [[ "$CHECK_MODE" == true ]]; then
    echo "  STALE: ${image}"
    echo "    current: ${current_digest:-<unpinned>}"
    echo "    live:    ${live_digest}"
    stale_count=$((stale_count + 1))
  else
    echo "  Updating ${dockerfile##"${REPO_ROOT}/"}..."
    sed -i "s|^FROM ${image}[^ ]* |FROM ${pinned} |;s|^FROM ${image}[^ ]*$|FROM ${pinned}|" "${dockerfile}"
    echo "  Updated: ${live_digest:0:16}..."
  fi
done

if [[ "$CHECK_MODE" == true ]]; then
  if [[ $stale_count -gt 0 ]]; then
    echo ""
    echo "ERROR: ${stale_count} base image digest(s) are stale. Run ./scripts/update-base-digests.sh to refresh." >&2
    exit 1
  fi
  echo "All base image digests are current."
fi
