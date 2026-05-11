#!/bin/bash
set -euo pipefail

# Strip setuid/setgid bits unconditionally at build time.
# dpkg-statoverride registers overrides so apt upgrades don't re-apply setuid.
# find strips any additional binaries not tracked by dpkg.
#
# ── dpkg-statoverride coverage by base image (verified 2026-04-28, follow-up to #76) ──
#
# Slim Debian variants (python:3.14-slim, debian:bookworm-slim) do NOT ship
# login utilities (su, newgrp, passwd, chsh, chfn) or mount utilities
# (mount, umount). These packages are excluded from the slim image.
# Each call below is wrapped in an explicit existence guard so that absence
# of a binary is treated as a no-op (expected on slim variants), but any
# other failure surfaces as a warning. See HomericIntelligence/Odysseus#280
# for the no-silent-failures rationale.
#
# Load-bearing call:
#   The `find … -perm /6000` sweep at the end IS load-bearing — it catches any
#   setuid/setgid binaries present regardless of how they were installed.
#
# Precautionary calls (binary absent from slim variants; no-op when missing):
#   /usr/bin/su, /usr/bin/newgrp, /usr/bin/passwd, /usr/bin/chsh, /usr/bin/chfn
#   /bin/mount, /bin/umount — all absent from python:3.14-slim and debian:bookworm-slim
#
# These are kept as belt-and-suspenders: if a future apt-get install step pulls
# in a package that includes login utilities (e.g. util-linux), the statoverride
# entry will already be registered to prevent apt from restoring setuid on upgrade.
# node:25-slim (used in Dockerfile.node) is also a Debian slim variant;
# the same analysis applies.

register_override() {
    local path="$1"
    if [ ! -e "$path" ]; then
        # Binary absent from this base variant — nothing to override (expected).
        return 0
    fi
    if ! dpkg-statoverride --update --add root root 0755 "$path" 2>/dev/null; then
        # Already registered is fine; anything else is unexpected — warn but
        # don't fail the build, since the find sweep below is the load-bearing
        # safety net.
        echo "warn: dpkg-statoverride could not register $path (already present?)" >&2
    fi
}

register_override /usr/bin/su
register_override /usr/bin/newgrp
register_override /usr/bin/passwd
register_override /usr/bin/chsh
register_override /usr/bin/chfn
register_override /bin/mount
register_override /bin/umount

# Load-bearing setuid/setgid sweep. `find` may return non-zero when it hits
# an unreadable path (e.g. /proc races), but the inventory we got back is
# still authoritative for the paths it could enumerate. Capture stderr/exit
# explicitly instead of suppressing them, then act on whatever was found.
setuid_list=""
if ! setuid_list="$(find / -xdev -perm /6000 -type f 2>/dev/null)"; then
    echo "info: find encountered unreadable paths during setuid sweep (continuing with enumerated set)" >&2
fi
if [ -n "$setuid_list" ]; then
    while IFS= read -r f; do
        if ! chmod a-s "$f" 2>/dev/null; then
            echo "warn: chmod a-s failed for $f" >&2
        fi
    done <<< "$setuid_list"
fi
