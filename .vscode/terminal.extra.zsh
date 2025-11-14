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

full_setup() {
  mise -q -y trust || {
    print -P "%F{209}[codeweaver]%f %F{red}Failed to trust the Mise environment!%f"
  }
  mise run setup
  # Skip 'mise run setup' to avoid circular activation
}

# Make sure Mise is installed and available
print -P "%F{209}[codeweaver]%f Welcome to the%f %F{209}CodeWeaver%f development environment!"
print -P "%F{209}[codeweaver]%f If you run into any issues, please visit %F{cyan}https://github.com/knitli/codeweaver-mcp/issues%f for assistance."
print -P "%F{209}[codeweaver]%f We're going to set up your environment now..."
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
cd "$REPO_ROOT" || {
  print -P "%F{209}[codeweaver]%f %F{red}Failed to change directory to the repository root!%f"
}
if command -v mise >/dev/null 2>&1; then
  # We have Mise installed, check if it's initialized for this workspace
  print -P "%F{209}[codeweaver]%f You're all set!"
else
  # Mise is not installed, run the install script
    chmod -R +x "${REPO_ROOT}/scripts" || {
      print -P "%F{209}[codeweaver]%f %F{red}Failed to make install scripts executable!%f"
    }
    print -P "%F{209}[codeweaver]%f Installing Mise for the first time..."
    "${REPO_ROOT}/scripts/install-mise.sh" || {
      print -P "%F{209}[codeweaver]%f %F{red}Failed to install Mise!%f Try running the install script manually: %F{cyan}${REPO_ROOT}/scripts/install-mise.sh%f"
    }
    full_setup
fi