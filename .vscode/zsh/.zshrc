# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# VS Code workspace-local zshrc
# Loaded because VS Code sets ZDOTDIR to this directory for integrated terminals.

typeset -i _mise_updated
typeset current_branch

cw_blue="{66}"
cw_copper="{173}"
cw_offwhite="{231}"

nerd_branch=""
nerd_path=""
nerd_mise=""

function _check_git_branch {
  branch="$(git branch --show-current 2>/dev/null || echo '')"
  echo "${branch}"
}

current_branch=""
_check_git_branch

# replace default mise hook
function _mise_hook {
  local diff=${__MISE_DIFF}
  current_branch="$(_check_git_branch)"
  source <(command mise hook-env -s zsh)
  [[ ${diff} == ${__MISE_DIFF} ]]
  _mise_updated=$?
}

function _prompt {
  local branch="$(_check_git_branch)"
  local branch_seg=""
  if [[ -n "${branch}" ]]; then
    branch_seg=" %F${cw_copper}${nerd_branch} ${branch}%f"
  fi

  local mise_seg=""
  if (( _mise_updated )); then
    mise_seg=" %F${cw_copper}${nerd_mise}%f"
  fi

  PROMPT="%(?.%F{120}%f.%F{196}%f) %F${cw_blue}${nerd_path}%f %F${cw_offwhite}%~%f${branch_seg}${mise_seg} %F${cw_blue}❯%f "
}


# Source repo dev shell init (idempotent), then hand off to user's normal zshrc.
REPO_ROOT="${PWD}"
if [[ -n "${VSCODE_CWD:-}" ]]; then
  REPO_ROOT="${VSCODE_CWD}"
fi

if [[ -f "${REPO_ROOT}/scripts/dev-env/dev-shell-init.zsh" ]]; then
  # shellcheck disable=SC1090
  source "${REPO_ROOT}/scripts/dev-env/dev-shell-init.zsh"
fi

if [[ -f "${ZDOTDIR:-${HOME}}/.vscode/terminal.extra.zsh" ]]; then
  source "${ZDOTDIR:-${HOME}}/.vscode/terminal.extra.zsh"
fi

# PERSONALIZE: You can add more *local* customizations in .vscode/terminal.local.zsh
# (This file is gitignored so it won't be checked in.)
if [[ -f "${ZDOTDIR:-${HOME}}/.vscode/terminal.local.zsh" ]]; then
  source "${ZDOTDIR:-${HOME}}/.vscode/terminal.local.zsh"
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

autoload -Uz add-zsh-hook 2>/dev/null
if (( $+functions[add-zsh-hook] )); then
  add-zsh-hook precmd _prompt
fi

