#!/usr/bin/env bash
# verify-trivyignore-prune.sh — reproducible evidence for the issue #760
# .trivyignore prune (PR #780).
#
# Rebuilds the affected images and scans them WITHOUT --ignorefile, asserting
# that none of the 20 pruned suppression IDs still fire. This is the runnable
# check behind the "# NOTE (issue #760 ...)" block in .trivyignore; the PR's
# CI "Trivy scan vessel image (gate)" jobs remain the authoritative gate.
#
# Requires: docker. Run from the repo root: bash scripts/verify-trivyignore-prune.sh
set -euo pipefail

PRUNED_IDS=(
  # claude-code bundled-npm set (cleared by claude-code 2.1.233)
  CVE-2024-21538 CVE-2025-64756 CVE-2026-26996
  CVE-2026-27903 CVE-2026-27904 CVE-2026-23745
  # stale-published-image aider python set (cleared by aider-chat 0.86.2 +
  # vessels/aider/requirements-security-overrides.txt)
  CVE-2026-35030 CVE-2026-35029 GHSA-69x8-hrgq-fjj8 CVE-2025-69223
  CVE-2025-48379 CVE-2026-25990 CVE-2026-40192
  CVE-2025-4565 CVE-2026-0994
  CVE-2026-23490 CVE-2026-30922
  CVE-2025-66418 CVE-2025-66471 CVE-2026-21441
)

TRIVY="${TRIVY:-docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image}"
SCAN_ARGS=(--severity HIGH,CRITICAL --ignore-unfixed)

scan() {
  local image="$1"
  echo "== Scanning ${image} (no ignorefile) =="
  ${TRIVY} "${SCAN_ARGS[@]}" "${image}" >"/tmp/trivy-${image//[:\/]/-}.txt"
}

failures=()
for image in achaean-aider:latest achaean-claude:latest; do
  scan "${image}"
  report="/tmp/trivy-${image//[:\/]/-}.txt"
  for id in "${PRUNED_IDS[@]}"; do
    if grep -qE "│ ${id}[^A-Za-z0-9-]" "${report}"; then
      failures+=("${image}: ${id}")
    fi
  done
done

if ((${#failures[@]})); then
  echo "FAIL — pruned CVEs still firing:" >&2
  printf '  %s\n' "${failures[@]}" >&2
  exit 1
fi

echo "OK — none of the ${#PRUNED_IDS[@]} pruned IDs fire in fresh scans of achaean-aider/achaean-claude"
