#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

set -euo pipefail

# Launch an interactive zsh that sources our init script. This ensures the first
# VS Code terminal session activates the .venv and runs extras.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." >/dev/null 2>&1 && pwd)"

INIT_SCRIPT="${REPO_ROOT}/scripts/dev-shell-init.zsh"

if [[ -t 1 ]]; then
  export CODEWEAVER_IN_VSCODE=1
fi

if [[ -f "${INIT_SCRIPT}" ]]; then
  exec zsh -i -c "source '${INIT_SCRIPT}'; exec zsh -i"
else
  exec zsh -i
fi
