#!/usr/bin/env bash
# update-goose-version.sh
#
# Fetches the latest goose release from GitHub, computes SHA256s for both
# AMD64 and ARM64 Linux tarballs, and patches vessels/goose/Dockerfile in
# place. Intended to be run manually or from a scheduled GitHub Actions
# workflow to prevent the pinned goose version from drifting stale
# (tracking: HomericIntelligence/AchaeanFleet#325).
#
# Usage:
#   scripts/update-goose-version.sh                # latest release
#   scripts/update-goose-version.sh v1.2.3         # explicit version
#
# Requirements: curl, sha256sum, sed. No external services beyond GitHub
# api.github.com and github.com release downloads.
set -euo pipefail

REPO="block/goose"
DOCKERFILE="$(git rev-parse --show-toplevel)/vessels/goose/Dockerfile"

if [ ! -f "$DOCKERFILE" ]; then
  echo "error: Dockerfile not found at $DOCKERFILE" >&2
  exit 1
fi

if [ $# -ge 1 ]; then
  TAG="$1"
else
  TAG=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
    | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' \
    | head -1)
fi

if [ -z "$TAG" ]; then
  echo "error: could not determine release tag" >&2
  exit 1
fi

VERSION="${TAG#v}"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

declare -A SHAS
for arch_pair in "amd64:x86_64-unknown-linux-gnu" "arm64:aarch64-unknown-linux-gnu"; do
  arch="${arch_pair%%:*}"
  target="${arch_pair##*:}"
  tarball="goose-${target}.tar.gz"
  url="https://github.com/${REPO}/releases/download/${TAG}/${tarball}"
  echo "Fetching ${url}"
  curl -fsSL "$url" -o "${TMP}/${tarball}"
  SHAS["$arch"]=$(sha256sum "${TMP}/${tarball}" | awk '{print $1}')
  echo "  ${arch} sha256: ${SHAS[$arch]}"
done

# Patch Dockerfile. We rewrite three keys: GOOSE_VERSION, GOOSE_AMD64_SHA256,
# GOOSE_ARM64_SHA256. Use a temp file and mv for atomicity.
TMPDF=$(mktemp)
sed -E \
  -e "s/^(ARG[[:space:]]+GOOSE_VERSION=).*/\1${VERSION}/" \
  -e "s/^(ENV[[:space:]]+GOOSE_VERSION=).*/\1${VERSION}/" \
  -e "s/^(ARG[[:space:]]+GOOSE_AMD64_SHA256=).*/\1${SHAS[amd64]}/" \
  -e "s/^(ARG[[:space:]]+GOOSE_ARM64_SHA256=).*/\1${SHAS[arm64]}/" \
  "$DOCKERFILE" >"$TMPDF"
mv "$TMPDF" "$DOCKERFILE"

echo "Patched ${DOCKERFILE} to goose ${VERSION}."
echo "Review the diff with: git diff -- $DOCKERFILE"
