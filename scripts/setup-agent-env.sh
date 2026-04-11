#!/usr/bin/env bash
# Shared agent environment setup — run as root in all base Dockerfiles.
# Assumes: 'agent' user already exists.
set -euo pipefail

# --- tmux config ---
mkdir -p /home/agent
echo "set -g mouse on"             >> /home/agent/.tmux.conf
echo "set -g history-limit 50000"  >> /home/agent/.tmux.conf
echo "set -g status-bg colour235"  >> /home/agent/.tmux.conf
echo "set -g status-fg colour136"  >> /home/agent/.tmux.conf
chown -R agent:agent /home/agent

# --- Oh My Zsh (must run as agent user) ---
su agent -c 'sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended'

# --- Workspace and app directories ---
mkdir -p /workspace /app
chown -R agent:agent /workspace /app
