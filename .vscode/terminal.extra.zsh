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

# -- welcome banner --
print -P ""
print -P "  %F{66}    ╔═══════════════════════════════════╗%f"
print -P "  %F{66}    ║%f  %F{173}CodeWeaver%f %F{242}dev environment%f       %F{66}║%f"
print -P "  %F{66}    ╚═══════════════════════════════════╝%f"
print -P ""
print -P "  %F{242}aliases:%f  %F{231}mr%f %F{242}= mise run%f  %F{242}|%f  %F{231}mx%f %F{242}= mise exec%f"
print -P "  %F{242}issues:%f   %F{cyan}https://github.com/knitli/codeweaver/issues%f"
print -P ""

# set a few aliases for convenience
alias mx='mise exec'
alias mr='mise run'

if command -v mise >/dev/null 2>&1; then
  print -P "  ${prefix} %F{120}Ready.%f"
else
  REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "${PWD}")"
  chmod -R +x "${REPO_ROOT}/scripts" || {
    print -P "${prefix} %F{red}Failed to make install scripts executable!%f"
  }
  print -P "${prefix} Installing Mise for the first time..."
  "${REPO_ROOT}/scripts/install-mise.sh" || {
    print -P "${prefix} %F{red}Failed to install Mise!%f Try running the install script manually: %F{cyan}${REPO_ROOT}/scripts/install-mise.sh%f"
  }
  full_setup
fi
print -P ""
