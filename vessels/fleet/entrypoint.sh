#!/bin/sh
set -eu
umask 077
if [ "$(id -u)" -eq 0 ]; then
    echo "Fleet workers must run as a non-root user." >&2
    exit 1
fi
if [ "$(codex --version)" != "codex-cli 0.153.4" ]; then
    echo "Fleet requires codex-cli 0.153.4." >&2
    exit 1
fi
exec hephaestus-fleet-worker "$@"
