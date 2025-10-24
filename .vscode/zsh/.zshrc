# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# VS Code workspace-local zshrc
# Loaded because VS Code sets ZDOTDIR to this directory for integrated terminals.

# Source repo dev shell init (idempotent), then hand off to user's normal zshrc.
REPO_ROOT="${PWD}"
if [[ -n "${VSCODE_CWD:-}" ]]; then
  REPO_ROOT="${VSCODE_CWD}"
fi

if [[ -f "${REPO_ROOT}/scripts/dev-env/dev-shell-init.zsh" ]]; then
  # shellcheck disable=SC1090
  source "${REPO_ROOT}/scripts/dev-env/dev-shell-init.zsh"
fi

# After workspace init, source the user's real ~/.zshrc if it exists
if [[ -f "${HOME}/.zshrc" ]]; then
  # Avoid infinite loop if ZDOTDIR points here
  if [[ "${ZDOTDIR:-}" != "${HOME}" ]]; then
    ZDOTDIR="${HOME}"
  fi
  # shellcheck disable=SC1090
  source "${HOME}/.zshrc"
fi

# PERSONALIZE: You can add more *local* customizations in .vscode/terminal.local.zsh
# (This file is gitignored so it won't be checked in.)
if [[ -f "${ZDOTDIR:-${HOME}}/.vscode/terminal.local.zsh" ]]; then
  source "${ZDOTDIR:-${HOME}}/.vscode/terminal.local.zsh"
fi