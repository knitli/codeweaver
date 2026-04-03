# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# VS Code workspace-local zshrc
# Loaded because VS Code sets ZDOTDIR to this directory for integrated terminals.

typeset -i _mise_updated
typeset current_branch
typeset -i _cw_cmd_start=0
typeset -i _cw_cmd_elapsed=0

# -- palette (256-color) --
cw_blue="{66}"
cw_copper="{173}"
cw_offwhite="{231}"
cw_dim="{242}"
cw_green="{120}"
cw_red="{196}"
cw_yellow="{220}"
cw_purple="{139}"

# -- nerd font glyphs --
nerd_branch=$'\ue0a0'     # git branch
nerd_path=$'\uf07c'        # folder open
nerd_mise=$'\U000F0003'    # mise/tools
nerd_weave=$'\U000F0097'   # package/weave - project identity
nerd_dirty=$'\u25cf'       # filled circle
nerd_staged="+"
nerd_clean=$'\u2714'       # check mark
nerd_venv=$'\ue73c'        # python
nerd_timer=$'\U000F13E3'   # timer
nerd_loom=$'\u2502'        # vertical line connector

function _check_git_branch {
  branch="$(git branch --show-current 2>/dev/null || echo '')"
  echo "${branch}"
}

# git working tree status: dirty, staged, or clean
function _git_status_icon {
  local gs
  gs="$(command git status --porcelain=v1 2>/dev/null)" || return
  if [[ -z "${gs}" ]]; then
    echo "%F${cw_green}${nerd_clean}%f"
  elif echo "${gs}" | command grep -q '^[MADRCU]'; then
    echo "%F${cw_yellow}${nerd_staged}%f"
  else
    echo "%F${cw_red}${nerd_dirty}%f"
  fi
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

# command timer: capture start time
function _cw_preexec {
  _cw_cmd_start=${EPOCHSECONDS}
}

function _prompt {
  local exit_code=$?
  local branch="$(_check_git_branch)"

  # -- elapsed time (only show if >= 3s) --
  local timer_seg=""
  if (( _cw_cmd_start > 0 )); then
    _cw_cmd_elapsed=$(( EPOCHSECONDS - _cw_cmd_start ))
    _cw_cmd_start=0
    if (( _cw_cmd_elapsed >= 3 )); then
      local mins=$(( _cw_cmd_elapsed / 60 ))
      local secs=$(( _cw_cmd_elapsed % 60 ))
      if (( mins > 0 )); then
        timer_seg=" %F${cw_dim}${nerd_timer} ${mins}m${secs}s%f"
      else
        timer_seg=" %F${cw_dim}${nerd_timer} ${secs}s%f"
      fi
    fi
  fi

  # -- exit status --
  local status_seg
  if (( exit_code == 0 )); then
    status_seg="%F${cw_green}%f"
  else
    status_seg="%F${cw_red} ${exit_code}%f"
  fi

  # -- git branch + working tree status --
  local git_seg=""
  if [[ -n "${branch}" ]]; then
    local git_icon="$(_git_status_icon)"
    git_seg=" %F${cw_copper}${nerd_branch} ${branch}%f ${git_icon}"
  fi

  # -- venv indicator --
  local venv_seg=""
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    local venv_name="${VIRTUAL_ENV:t}"
    venv_seg=" %F${cw_purple}${nerd_venv} ${venv_name}%f"
  fi

  # -- mise env changed --
  local mise_seg=""
  if (( _mise_updated )); then
    mise_seg=" %F${cw_copper}${nerd_mise}%f"
  fi

  # -- two-line prompt --
  # line 1: project icon | path | git | venv | mise | timer
  # line 2: thread connector | status | input arrow
  PROMPT="%F${cw_blue}${nerd_weave}%f %F${cw_blue}${nerd_path}%f %F${cw_offwhite}%~%f${git_seg}${venv_seg}${mise_seg}${timer_seg}
%F${cw_dim}${nerd_loom}%f ${status_seg} %F${cw_blue}❯%f "
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
  add-zsh-hook preexec _cw_preexec
fi

# bun completions
[ -s "/home/knitli/.oh-my-zsh/completions/_bun" ] && source "/home/knitli/.oh-my-zsh/completions/_bun"
