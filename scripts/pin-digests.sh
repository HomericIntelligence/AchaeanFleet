#!/usr/bin/env bash
# pin-digests.sh — Fetch current digests for all AchaeanFleet base images.
#
# Run this script when bumping base image versions. It pulls the current image,
# prints the pinned FROM line to paste into the corresponding Dockerfile, and
# also shows the latest Oh My Zsh master commit to update OHMYZSH_COMMIT.
#
# Usage: bash scripts/pin-digests.sh

set -euo pipefail

BASE_IMAGES=(
    "node:20-slim"
    "python:3.12-slim"
    "debian:bookworm-slim"
)

echo "=== Base image digests ==="
for image in "${BASE_IMAGES[@]}"; do
    echo -n "Pulling ${image} ... "
    docker pull --quiet "${image}"
    digest=$(docker inspect --format='{{index .RepoDigests 0}}' "${image}")
    # Extract just the sha256 portion and reformat as image:tag@sha256:...
    tag_part="${image}"
    sha_part="${digest#*@}"
    echo "FROM ${tag_part}@${sha_part}"
done

echo ""
echo "=== Oh My Zsh latest master commit ==="
ohmyzsh_commit=$(curl -fsSL "https://api.github.com/repos/ohmyzsh/ohmyzsh/commits/master" \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['sha'])")
echo "ENV OHMYZSH_COMMIT=${ohmyzsh_commit}"

echo ""
echo "Update the FROM lines in bases/Dockerfile.{node,python,minimal} and"
echo "update OHMYZSH_COMMIT in all three files, then commit the changes."
