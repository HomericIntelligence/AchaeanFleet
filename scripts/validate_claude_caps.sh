#!/usr/bin/env bash
# validate_claude_caps.sh — Validate that achaean-claude:latest starts under cap_drop=ALL
#
# Usage: scripts/validate_claude_caps.sh [--image IMAGE] [--out REPORT]
#
# Probe: "claude --version" — exits 0 without contacting the Anthropic API,
# so it never conflates auth failures with capability failures.
#
# Pass criteria: docker run exits 0 under --cap-drop=ALL --security-opt=no-new-privileges.
# If it fails and stderr contains EPERM/capset/prctl/permission denied, that is a
# capability gap; the script exits non-zero and documents the failure in REPORT.
#
# Related: nomad/PATTERNS.md §Capability validation, issue #305

set -euo pipefail

IMAGE="${IMAGE:-achaean-claude:latest}"
REPORT="${REPORT:-cap_validation_report.json}"

# Parse flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --image) IMAGE="$2"; shift 2 ;;
    --out)   REPORT="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

# Guard: Docker must be reachable
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker daemon not reachable — cannot run cap validation" >&2
  exit 1
fi

# Guard: image must exist
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "ERROR: Image '$IMAGE' not found. Build it first:" >&2
  echo "  docker build -f bases/Dockerfile.node -t achaean-base-node:latest ." >&2
  echo "  docker build -f vessels/claude/Dockerfile --build-arg BASE_IMAGE=achaean-base-node:latest -t achaean-claude:latest ." >&2
  exit 1
fi

IMAGE_DIGEST=$(docker inspect --format '{{index .RepoDigests 0}}' "$IMAGE" 2>/dev/null || echo "local-build")
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

echo "Validating cap_drop=ALL for image: $IMAGE"
echo "Probe: claude --version"
echo "Constraints: --cap-drop=ALL --security-opt=no-new-privileges"

# Run probe — 30s timeout; no workspace mount; fresh container each call
STDERR_FILE=$(mktemp)
trap 'rm -f "$STDERR_FILE"' EXIT

set +e
timeout 30 docker run --rm \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --entrypoint="" \
  "$IMAGE" \
  claude --version >"$STDERR_FILE.stdout" 2>"$STDERR_FILE" </dev/null
EXIT_CODE=$?
set -e

STDOUT_CONTENT=$(cat "$STDERR_FILE.stdout" 2>/dev/null || true)
STDERR_CONTENT=$(cat "$STDERR_FILE" 2>/dev/null || true)

# Classify result
if [[ $EXIT_CODE -eq 0 ]]; then
  VERSION_CHECK="pass"
  FAILURE_CLASS="none"
elif echo "$STDERR_CONTENT" | grep -qiE "EPERM|Operation not permitted|capset|prctl|permission denied"; then
  VERSION_CHECK="fail"
  FAILURE_CLASS="capability"
elif [[ $EXIT_CODE -eq 124 ]]; then
  VERSION_CHECK="fail"
  FAILURE_CLASS="timeout"
else
  VERSION_CHECK="fail"
  FAILURE_CLASS="env"
fi

rm -f "$STDERR_FILE.stdout"

# Write JSON report
cat > "$REPORT" <<EOF
{
  "image": "$IMAGE",
  "image_digest": "$IMAGE_DIGEST",
  "timestamp": "$TIMESTAMP",
  "cap_drop": ["ALL"],
  "cap_add": [],
  "no_new_privs": true,
  "probe": "claude --version",
  "exit_code": $EXIT_CODE,
  "version_check": "$VERSION_CHECK",
  "version_stdout": $(echo "$STDOUT_CONTENT" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))'),
  "failure_class": "$FAILURE_CLASS",
  "stderr": $(echo "$STDERR_CONTENT" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().strip()))')
}
EOF

echo ""
echo "Result: version_check=$VERSION_CHECK (exit_code=$EXIT_CODE, failure_class=$FAILURE_CLASS)"
echo "Report written to: $REPORT"

if [[ "$VERSION_CHECK" != "pass" ]]; then
  echo ""
  echo "FAILURE: cap_drop=ALL validation failed for $IMAGE" >&2
  echo "  failure_class: $FAILURE_CLASS" >&2
  if [[ -n "$STDERR_CONTENT" ]]; then
    echo "  stderr: $STDERR_CONTENT" >&2
  fi
  echo "" >&2
  echo "Next steps:" >&2
  case "$FAILURE_CLASS" in
    capability)
      echo "  1. Inspect the stderr above for specific EPERM syscalls" >&2
      echo "  2. Map the syscalls to Linux capabilities via capabilities(7)" >&2
      echo "  3. Add cap_add = [\"<CAP>\"] to nomad/mesh.nomad.hcl with a comment citing this report" >&2
      ;;
    env)
      echo "  1. Verify the image is built correctly: docker run --rm $IMAGE claude --version" >&2
      echo "  2. Ensure ENTRYPOINT/CMD are set correctly in the vessel Dockerfile" >&2
      ;;
    timeout)
      echo "  1. The probe timed out after 30s — check if the container hangs on startup" >&2
      ;;
  esac
  exit 1
fi

echo "PASS: achaean-claude starts correctly under cap_drop=ALL with no_new_privs=true"
