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
    print -P "%F{66}[codeweaver]%f %F{red}Failed to trust the Mise environment!%f"
  }
  mise run setup
}

prefix_color="%F{66}"
prefix="${prefix_color}[codeweaver]%f"

# Make sure Mise is installed and available
print -P "${prefix} Welcome to the ${prefix_color}CodeWeaver%f development environment!"
print -P "${prefix} If you run into any issues, please visit %F{cyan}https://github.com/knitli/codeweaver/issues%f for assistance."

# set a few aliases for convenience
alias mx='mise exec'
alias mr='mise run'

if command -v mise >/dev/null 2>&1; then
  # We have Mise installed, check if it's initialized for this workspace
  print -P "${prefix} You're all set!"
else
  REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "${PWD}")"
  # Mise is not installed, run the install script
  chmod -R +x "${REPO_ROOT}/scripts" || {
      print -P "${prefix} %F{red}Failed to make install scripts executable!%f"
    }
    print -P "${prefix} Installing Mise for the first time..."
    "${REPO_ROOT}/scripts/install-mise.sh" || {
      print -P "${prefix} %F{red}Failed to install Mise!%f Try running the install script manually: %F{cyan}${REPO_ROOT}/scripts/install-mise.sh%f"
    }
    full_setup
fi