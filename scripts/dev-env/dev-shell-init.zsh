# CodeWeaver dev shell initialization (zsh)
# - Idempotently activate this repo's .venv
# - Optionally source workspace-specific extra commands

# If already initialized in this shell session, do nothing
if [[ -n "${__CODEWEAVER_DEV_SHELL_INIT_DONE:-}" ]]; then
  return 0
fi
typeset -g __CODEWEAVER_DEV_SHELL_INIT_DONE=1

# Resolve path to this file when sourced in zsh
__cw_this_file="${(%):-%N}"
__cw_dirname() { builtin cd -- "${1%/*}" 2>/dev/null && pwd; }
__cw_script_dir="$(__cw_dirname "$__cw_this_file")"

# Compute repo root (script lives in <repo>/scripts)
if [[ -n "$__cw_script_dir" ]]; then
  REPO_ROOT="$(builtin cd "${__cw_script_dir}/../.." 2>/dev/null && pwd)"
fi

# Fallback: try git if above failed
if [[ -z "${REPO_ROOT:-}" ]]; then
  if command -v git >/dev/null 2>&1; then
    REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
  fi
fi

# Last resort: current working directory
REPO_ROOT="${REPO_ROOT:-$PWD}"

# Idempotent venv activation for this repo
_cw_repo_venv_path="${REPO_ROOT}/.venv"
_cw_venv_activate="${_cw_repo_venv_path}/bin/activate"

if [[ -f "${_cw_venv_activate}" ]]; then
  # Only activate if not already active or if a different venv is active
  if [[ -z "${VIRTUAL_ENV:-}" || "${VIRTUAL_ENV}" != "${_cw_repo_venv_path}" ]]; then
    # shellcheck disable=SC1090
    source "${_cw_venv_activate}"
  fi
else
  # Helpful hint if .venv is missing (non-fatal)
  if [[ -z "${CODEWEAVER_SILENT_SHELL:-}" ]]; then
    print -P "%F{yellow}[codeweaver]%f .venv not found at %F{cyan}${_cw_repo_venv_path}%f"
    print -P "%F{yellow}[codeweaver]%f Create it with: uv venv && uv sync  (requires uv)"
  fi
fi

# Source optional workspace extras if provided
_cw_extras="${REPO_ROOT}/.vscode/terminal.extra.zsh"
if [[ -f "${_cw_extras}" ]]; then
  # shellcheck disable=SC1090
  source "${_cw_extras}"
fi

unset __cw_this_file __cw_script_dir _cw_repo_venv_path _cw_venv_activate _cw_extras
