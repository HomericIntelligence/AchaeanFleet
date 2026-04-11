#!/usr/bin/env bash
# AchaeanFleet container entrypoint
#
# Startup order:
#   1. Start a detached tmux session (non-fatal if tmux is unavailable or
#      a session by that name already exists)
#   2. If /app/agent-server.js is present (bind-mounted at runtime by the
#      Agamemnon agent sidecar), exec it with any arguments passed to the
#      container (compose command: or docker run args).
#   3. If extra arguments were supplied on the command line, exec them directly.
#      This lets compose `command:` overrides work without removing ENTRYPOINT.
#   4. Last resort: drop to an interactive bash shell.
#
# Signal handling: every code path uses `exec` so the started process
# inherits PID 1 and receives SIGTERM/SIGINT from Docker correctly.

set -euo pipefail

# ---------------------------------------------------------------------------
# 1. Start tmux session
# ---------------------------------------------------------------------------
if command -v tmux &>/dev/null; then
    tmux new-session -d -s "${TMUX_SESSION_NAME:-agent-session}" 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# 2. Launch agent-server.js if bind-mounted at runtime
# ---------------------------------------------------------------------------
if [ -f /app/agent-server.js ]; then
    exec node /app/agent-server.js "$@"
fi

# ---------------------------------------------------------------------------
# 3. Forward any explicit arguments (compose command:, docker run <cmd>)
# ---------------------------------------------------------------------------
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

# ---------------------------------------------------------------------------
# 4. Fallback: interactive shell
# ---------------------------------------------------------------------------
exec bash
