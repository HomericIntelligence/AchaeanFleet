#!/usr/bin/env bash
# scripts/tag-images.sh — Apply versioned tags to locally-built AchaeanFleet images
#
# After building images locally (e.g. via `just build-all` or `just build-vessel`),
# run this script to apply git SHA and date tags so locally-built images match the
# multi-tag set produced by CI on push to main.
#
# Usage:
#   bash scripts/tag-images.sh                    # tag all vessels
#   bash scripts/tag-images.sh achaean-claude     # tag a single vessel
#   REGISTRY=ghcr.io/homericintelligence bash scripts/tag-images.sh   # also tag with registry prefix
#
# Tags applied:
#   <name>:git-<7-char-sha>   — git SHA of HEAD
#   <name>:YYYY-MM-DD         — today's date
#   <name>:latest             — no-op, already present
#   <registry>/<name>:<tag>   — if REGISTRY is set, mirrors all tags with registry prefix

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

CONTAINER_CMD="${CONTAINER_CMD:-$(which podman 2>/dev/null || echo docker)}"
REGISTRY="${REGISTRY:-}"

# All vessel image names
ALL_VESSELS=(
  achaean-claude
  achaean-codex
  achaean-aider
  achaean-goose
  achaean-cline
  achaean-opencode
  achaean-codebuff
  achaean-ampcode
  achaean-worker
)

# Determine which vessels to tag
if [[ $# -gt 0 ]]; then
  VESSELS=("$@")
else
  VESSELS=("${ALL_VESSELS[@]}")
fi

# Compute tags
SHORT_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")"
DATESTAMP="$(date -u +%Y-%m-%d)"

echo "Container runtime : ${CONTAINER_CMD}"
echo "Short SHA         : ${SHORT_SHA}"
echo "Datestamp         : ${DATESTAMP}"
[[ -n "${REGISTRY}" ]] && echo "Registry          : ${REGISTRY}"
echo ""

tagged=0
skipped=0

for vessel in "${VESSELS[@]}"; do
  source_tag="${vessel}:latest"

  # Check that the source image exists
  if ! ${CONTAINER_CMD} inspect "${source_tag}" &>/dev/null; then
    echo "  SKIP ${vessel} — image '${source_tag}' not found locally (build it first)"
    skipped=$((skipped + 1))
    continue
  fi

  echo "Tagging ${vessel}:"

  sha_tag="${vessel}:git-${SHORT_SHA}"
  date_tag="${vessel}:${DATESTAMP}"

  ${CONTAINER_CMD} tag "${source_tag}" "${sha_tag}"
  echo "  + ${sha_tag}"

  ${CONTAINER_CMD} tag "${source_tag}" "${date_tag}"
  echo "  + ${date_tag}"

  if [[ -n "${REGISTRY}" ]]; then
    ${CONTAINER_CMD} tag "${source_tag}" "${REGISTRY}/${vessel}:latest"
    echo "  + ${REGISTRY}/${vessel}:latest"
    ${CONTAINER_CMD} tag "${source_tag}" "${REGISTRY}/${vessel}:git-${SHORT_SHA}"
    echo "  + ${REGISTRY}/${vessel}:git-${SHORT_SHA}"
    ${CONTAINER_CMD} tag "${source_tag}" "${REGISTRY}/${vessel}:${DATESTAMP}"
    echo "  + ${REGISTRY}/${vessel}:${DATESTAMP}"
  fi

  tagged=$((tagged + 1))
done

echo ""
echo "=== Done: ${tagged} tagged, ${skipped} skipped ==="
