# Runbook: Dependency Audit Allowlists

## Overview

AchaeanFleet maintains two separate allowlist files for known-unfixable CVEs in the
aider-chat transitive dependency tree:

| File | Scanner | Scope |
|---|---|---|
| `.pip-audit-ignore.aider-chat.txt` | pip-audit | Python wheel metadata (aider-chat deps) |
| `.trivyignore` | Trivy | Container image layers |

**Dual suppression is intentional.** Trivy scans container image layers; pip-audit scans Python
wheel metadata. The same CVE may appear in both tools via different detection paths. When removing
an entry, search **both files**.

## Background

aider-chat==0.82.3 hard-pins all transitive dependencies with `==` constraints. This means 57
known CVEs across 14 packages (aiohttp, diskcache, filelock, gitpython, litellm, pillow, pip,
protobuf, pyasn1, pygments, python-dotenv, requests, setuptools, urllib3) cannot be resolved
without a new aider-chat release. All 57 IDs are listed in `.pip-audit-ignore.aider-chat.txt`.

See: HomericIntelligence/AchaeanFleet#655

**Note:** The pip-audit CI step that consumes `.pip-audit-ignore.aider-chat.txt` is currently
disabled because the aider vessel was disabled in #665. Restore the step from PR #662 history
when re-enabling aider. The allowlist file is maintained here so it is ready on re-enablement.

## Resolution Paths

Pick one when unblocking the aider vessel:

1. **Wait for upstream aider-chat to bump deps.** Track aider-chat release notes. Run the
   re-audit procedure below after each new aider-chat release and prune resolved ignores.
   Recommended if aider-chat is already pinned to the latest release.

2. **Replace aider-chat** with a different agent backend if upstream is unresponsive on CVE
   resolution. Remove `.pip-audit-ignore.aider-chat.txt` entirely once the replacement is in place.

3. **Drop the audit step** if aider-chat's transitive tree is permanently downstream-uncontrollable.
   The allowlist provides no security value if every CVE is indefinitely suppressed.

## 2026-08-10 Review Checkpoint

At review time, run:

```bash
# Install latest aider-chat in a clean venv
python3 -m venv /tmp/aider-audit-venv
source /tmp/aider-audit-venv/bin/activate
pip install pip-audit aider-chat

# Re-audit and compare against the allowlist
pip-audit --desc 2>&1 | tee /tmp/pip-audit-fresh.txt

# Check which allowlisted IDs are no longer present
while IFS= read -r id; do
  if ! grep -q "$id" /tmp/pip-audit-fresh.txt; then
    echo "RESOLVED (remove from allowlist): $id"
  fi
done < <(grep -vE '^\s*(#|$)' .pip-audit-ignore.aider-chat.txt)

deactivate
rm -rf /tmp/aider-audit-venv /tmp/pip-audit-fresh.txt
```

After pruning resolved IDs:
1. Remove each resolved ID from `.pip-audit-ignore.aider-chat.txt`.
2. Search `.trivyignore` for each removed ID — remove from there too if present.
3. Update the `# Expires:` header in `.pip-audit-ignore.aider-chat.txt` to the next review date
   (90 days from now).
4. Update the count assertion in the `Validate pip-audit allowlist format` CI step if the count
   changed.
5. Open a PR referencing #655.

## Format Validation

`.pip-audit-ignore.aider-chat.txt` must contain:
- One CVE/GHSA/PYSEC ID per line.
- Lines matching: `^(GHSA-[0-9a-z-]+|PYSEC-[0-9]{4}-[0-9]+|CVE-[0-9]{4}-[0-9]+)$`
- Blank lines and `#` comment lines are ignored.
- A `# Expires: YYYY-MM-DD` header with the next review date.

GHSA and PYSEC IDs use lowercase hex (per GitHub advisory database convention).
CVE IDs use uppercase.

## Overlapping IDs

One ID appears in both allowlist files: `GHSA-69x8-hrgq-fjj8` (litellm password hash exposure).
Trivy detected this via image layer scan; pip-audit via wheel metadata. Both suppressions are
intentional and should be removed together when litellm is upgraded past 1.83.0.

## CI Steps (when aider is re-enabled)

The three CI steps that consume `.pip-audit-ignore.aider-chat.txt` (from PR #662 history):

```yaml
- name: Validate pip-audit allowlist format
  run: |
    set -euo pipefail
    file=".pip-audit-ignore.aider-chat.txt"
    # GHSA/PYSEC IDs are lowercase per GitHub advisory database; CVE IDs uppercase.
    bad=$(grep -vE '^\s*(#|$)' "$file" \
      | grep -vE '^(GHSA-[0-9a-z-]+|PYSEC-[0-9]{4}-[0-9]+|CVE-[0-9]{4}-[0-9]+)$' || true)
    if [[ -n "$bad" ]]; then
      echo "ERROR: malformed entries in $file:"; echo "$bad"; exit 1
    fi
    count=$(grep -cvE '^\s*(#|$)' "$file")
    echo "NOTE: allowlist count: $count. Update this assertion intentionally when count changes."

- name: Check pip-audit allowlist expiry
  run: |
    set -euo pipefail
    file=".pip-audit-ignore.aider-chat.txt"
    today=$(date -u +%Y-%m-%d)
    expired=0
    while IFS= read -r line; do
      if [[ "$line" =~ ^#\ Expires:\ ([0-9]{4}-[0-9]{2}-[0-9]{2})$ ]]; then
        if [[ "${BASH_REMATCH[1]}" < "$today" ]]; then
          echo "ERROR: pip-audit allowlist expired: ${BASH_REMATCH[1]}"; expired=1
        fi
      fi
    done < "$file"
    [[ $expired -eq 0 ]] || exit 1

- name: Audit Python dependencies (aider-chat)
  run: |
    set -euo pipefail
    pip install --quiet pip-audit aider-chat
    # bash 5+ (GHA ubuntu-latest) — mapfile builtin required
    mapfile -t ignores < <(grep -vE '^\s*(#|$)' .pip-audit-ignore.aider-chat.txt)
    args=()
    for id in "${ignores[@]}"; do args+=(--ignore-vuln "$id"); done
    pip-audit --desc "${args[@]}"
```
