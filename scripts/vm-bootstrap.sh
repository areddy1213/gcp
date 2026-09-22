#!/usr/bin/env bash
# Run this ON THE REHEARSAL VM. It installs the interview toolchain:
# terraform, tmux, jq, Node, Claude Code, and OpenCode.
set -euo pipefail

sudo apt-get update -y
sudo apt-get install -y tmux jq git curl unzip gnupg lsb-release vim nano

# Terraform (from HashiCorp's apt repo)
if ! command -v terraform >/dev/null; then
  curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp.gpg
  echo "deb [signed-by=/usr/share/keyrings/hashicorp.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
    | sudo tee /etc/apt/sources.list.d/hashicorp.list
  sudo apt-get update -y && sudo apt-get install -y terraform
fi

# gcloud comes preinstalled on Google's Debian images; install it if it's missing.
if ! command -v gcloud >/dev/null; then
  curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
  echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
    | sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list
  sudo apt-get update -y && sudo apt-get install -y google-cloud-cli
fi

# Node + the agents
if ! command -v node >/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
sudo npm install -g @anthropic-ai/claude-code opencode-ai

# Minimal tmux config: mouse on, and easy splits with Ctrl-b | and Ctrl-b -
cat > ~/.tmux.conf <<'TMUX'
set -g mouse on
set -g history-limit 50000
bind | split-window -h -c "#{pane_current_path}"
bind - split-window -v -c "#{pane_current_path}"
TMUX

cat <<MSG

Done. Next steps:
  1. Authenticate the agents: run 'claude' and 'opencode' once each (API key or login).
  2. tmux new -s interview   then Ctrl-b |   (agent on the left, verification shell on the right)
  3. ./scripts/orient.sh
MSG
