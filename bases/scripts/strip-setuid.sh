#!/bin/bash
set -e

# Strip setuid/setgid bits unconditionally at build time.
# dpkg-statoverride registers overrides so apt upgrades don't re-apply setuid.
# find strips any additional binaries not tracked by dpkg.

dpkg-statoverride --update --add root root 0755 /usr/bin/su          2>/dev/null || true
dpkg-statoverride --update --add root root 0755 /usr/bin/newgrp      2>/dev/null || true
dpkg-statoverride --update --add root root 0755 /usr/bin/passwd      2>/dev/null || true
dpkg-statoverride --update --add root root 0755 /usr/bin/chsh        2>/dev/null || true
dpkg-statoverride --update --add root root 0755 /usr/bin/chfn        2>/dev/null || true
dpkg-statoverride --update --add root root 0755 /bin/mount           2>/dev/null || true
dpkg-statoverride --update --add root root 0755 /bin/umount          2>/dev/null || true
find / -xdev -perm /6000 -type f -exec chmod a-s {} \; 2>/dev/null || true
