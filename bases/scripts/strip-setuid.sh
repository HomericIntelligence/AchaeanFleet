#!/bin/bash
set -e

# Strip setuid/setgid bits unconditionally at build time.
# dpkg-statoverride registers overrides so apt upgrades don't re-apply setuid.
# find strips any additional binaries not tracked by dpkg.
#
# ── dpkg-statoverride coverage by base image (verified 2026-04-28, follow-up to #76) ──
#
# Slim Debian variants (python:3.14-slim, debian:bookworm-slim) do NOT ship
# login utilities (su, newgrp, passwd, chsh, chfn) or mount utilities
# (mount, umount). These packages are excluded from the slim image.
# The `2>/dev/null || true` guards make each call non-fatal when the path is absent.
#
# Load-bearing call:
#   The `find … -perm /6000` sweep at the end IS load-bearing — it catches any
#   setuid/setgid binaries present regardless of how they were installed.
#
# Precautionary calls (binary absent from slim variants; || true makes them no-ops):
#   /usr/bin/su, /usr/bin/newgrp, /usr/bin/passwd, /usr/bin/chsh, /usr/bin/chfn
#   /bin/mount, /bin/umount — all absent from python:3.14-slim and debian:bookworm-slim
#
# These are kept as belt-and-suspenders: if a future apt-get install step pulls
# in a package that includes login utilities (e.g. util-linux), the statoverride
# entry will already be registered to prevent apt from restoring setuid on upgrade.
# node:25-slim (used in Dockerfile.node) is also a Debian slim variant;
# the same analysis applies.

dpkg-statoverride --update --add root root 0755 /usr/bin/su          2>/dev/null || true
dpkg-statoverride --update --add root root 0755 /usr/bin/newgrp      2>/dev/null || true
dpkg-statoverride --update --add root root 0755 /usr/bin/passwd      2>/dev/null || true
dpkg-statoverride --update --add root root 0755 /usr/bin/chsh        2>/dev/null || true
dpkg-statoverride --update --add root root 0755 /usr/bin/chfn        2>/dev/null || true
dpkg-statoverride --update --add root root 0755 /bin/mount           2>/dev/null || true
dpkg-statoverride --update --add root root 0755 /bin/umount          2>/dev/null || true
find / -xdev -perm /6000 -type f -exec chmod a-s {} \; 2>/dev/null || true
