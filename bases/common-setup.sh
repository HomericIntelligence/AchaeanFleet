#!/bin/bash
# bases/common-setup.sh — Shared setup steps for AchaeanFleet base images.
#
# NOTE: This script is not currently called by any Dockerfile. It exists as
# a reference implementation of the common setup steps. To use it, copy it
# into a Dockerfile build context and invoke it as shown below.
#
# Intended to be run during Docker build (as root) to:
#   1. Configure tmux for the 'agent' user
#   2. Install Oh My Zsh for the 'agent' user
#   3. Create /workspace and /app directories with correct ownership
#
# Usage in a Dockerfile:
#   COPY bases/common-setup.sh /tmp/common-setup.sh
#   RUN bash /tmp/common-setup.sh && rm /tmp/common-setup.sh

set -euo pipefail

# ── tmux config ────────────────────────────────────────────────────────────────
mkdir -p /home/agent
cat >> /home/agent/.tmux.conf <<'EOF'
set -g mouse on
set -g history-limit 50000
set -g status-bg colour235
set -g status-fg colour136
EOF
chown -R agent:agent /home/agent

# ── Oh My Zsh ─────────────────────────────────────────────────────────────────
su - agent -s /bin/bash -c \
  'sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended'

# ── workspace & app directories ───────────────────────────────────────────────
mkdir -p /workspace /app
chown -R agent:agent /workspace /app
