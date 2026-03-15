#!/usr/bin/env bash
# notify-proteus.sh — Notify ProjectProteus that images were pushed.
# Triggers a repository_dispatch to Myrmidons via ProjectProteus.
# Called by: just push-and-notify
set -euo pipefail

GITHUB_TOKEN=${GITHUB_TOKEN:-}
ORG=${GITHUB_ORG:-homeric-intelligence}
REPO=${NOTIFY_REPO:-Myrmidons}
IMAGE_TAG=${IMAGE_TAG:-latest}

if [ -z "$GITHUB_TOKEN" ]; then
    echo "GITHUB_TOKEN not set — skipping remote dispatch"
    echo "To enable: export GITHUB_TOKEN=<your-token>"
    exit 0
fi

echo "Dispatching image-pushed event to ${ORG}/${REPO}..."
response=$(curl -sf -o /dev/null -w "%{http_code}" \
    -X POST \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    "https://api.github.com/repos/${ORG}/${REPO}/dispatches" \
    -d "{\"event_type\": \"image-pushed\", \"client_payload\": {\"image_tag\": \"${IMAGE_TAG}\", \"source\": \"AchaeanFleet\"}}")

if [ "$response" = "204" ]; then
    echo "Dispatch sent successfully (HTTP 204)"
else
    echo "Dispatch failed (HTTP ${response})"
    exit 1
fi
