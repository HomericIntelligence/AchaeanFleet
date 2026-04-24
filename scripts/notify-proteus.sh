#!/usr/bin/env bash
# notify-proteus.sh — Notify ProjectProteus that images were pushed.
# Dispatch chain: AchaeanFleet → ProjectProteus (image-pushed)
#                 → Myrmidons (agamemnon-apply) via Proteus cross-repo-dispatch.yml
# Called by: just push-and-notify, ci.yml push-to-registry job
set -euo pipefail

GITHUB_TOKEN=${GITHUB_TOKEN:-}
ORG=${GITHUB_ORG:-HomericIntelligence}
REPO=${NOTIFY_REPO:-Myrmidons}
IMAGE_TAG=${IMAGE_TAG:-latest}
HOST=${AGAMEMNON_HOST:-hermes}
VESSEL_DIGEST=${VESSEL_DIGEST:-}

if [ -z "$GITHUB_TOKEN" ]; then
    echo "GITHUB_TOKEN not set — skipping remote dispatch"
    echo "To enable: export GITHUB_TOKEN=<your-token>"
    exit 0
fi

# Build payload — include vessel_digest only when provided
if [ -n "$VESSEL_DIGEST" ]; then
  PAYLOAD="{\"event_type\": \"image-pushed\", \"client_payload\": {\"image_tag\": \"${IMAGE_TAG}\", \"source\": \"AchaeanFleet\", \"host\": \"${HOST}\", \"vessel_digest\": \"${VESSEL_DIGEST}\"}}"
else
  PAYLOAD="{\"event_type\": \"image-pushed\", \"client_payload\": {\"image_tag\": \"${IMAGE_TAG}\", \"source\": \"AchaeanFleet\", \"host\": \"${HOST}\"}}"
fi

echo "Dispatching image-pushed event to ${ORG}/${REPO}..."
response=$(curl -sf -o /dev/null -w "%{http_code}" \
    -X POST \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    "https://api.github.com/repos/${ORG}/${REPO}/dispatches" \
    -d "$PAYLOAD")

if [ "$response" = "204" ]; then
    echo "Dispatch sent successfully (HTTP 204)"
else
    echo "Dispatch failed (HTTP ${response})"
    exit 1
fi
