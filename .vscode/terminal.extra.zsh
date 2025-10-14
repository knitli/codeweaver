#!/usr/bin/env zsh
# SPDX-FileCopyrightText: 2025 Knitli Inc. <knitli@knit.li>
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
#
# VS Code workspace-local zshrc
# Loaded because VS Code sets ZDOTDIR to this directory for integrated terminals.
# The workspace zshrc (.vscode/zsh/.zshrc) sources the main dev shell init script, and runs this file afterwards.
# This file can be customized per workspace for additional setup.

setup_env() {
  eval "$(mise -q activate zsh)"
  eval "$(mise -q env -s zsh)"
  print -P "%F{green}[codeweaver]%f Mise environment activated."
  mise -q reshim || {
    print -P "%F{red}[codeweaver]%f Failed to reshim Mise!"
  }
}

full_setup() {
  setup_env
  mise -q trust -y || {
    print -P "%F{red}[codeweaver]%f Failed to trust the Mise environment!"
  }
  mise -q reshim || {
    print -P "%F{red}[codeweaver]%f Failed to reshim the Mise environment!"
  }
  # Skip 'mise run setup' to avoid circular activation
}

# Make sure Mise is installed and available
print -P "%F{cyan}[codeweaver]%fWelcome to the CodeWeaver development environment!"
print -P "%F{green}[codeweaver]%fIf you encounter any issues, please visit https://github.com/knitli/codeweaver-mcp/issues for assistance."
print -P "%F{magenta}[codeweaver]%fWe're going to setup your environment now..."
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
cd "$REPO_ROOT" || {
  print -P "%F{red}[codeweaver]%f Failed to change directory to the repository root!"
}
if command -v mise >/dev/null 2>&1; then
  # We have Mise installed, check if it's initialized for this workspace
  setup_env
else
  # Mise is not installed, run the install script
    chmod -R +x "${REPO_ROOT}/scripts" || {
      print -P "%F{red}[codeweaver]%f Failed to make install scripts executable!"
    }
    print -P "%F{yellow}[codeweaver]%f Installing Mise for the first time..."
    "${REPO_ROOT}/scripts/install-mise.sh" || {
      print -P "%F{red}[codeweaver]%f Failed to install Mise! Try running the install script manually: %F{cyan}${REPO_ROOT}/scripts/install-mise.sh%f"
    }
    full_setup
fi
# Mise activation already handled above, no need to repeat
# This prevents double-activation which could cause loops
