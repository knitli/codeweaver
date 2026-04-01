#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# SPDX-License-Identifier: MIT OR Apache-2.0

# Check if CodeWeaver has been configured (first-run detection)
# Used by SessionStart hook to trigger onboarding agent on initial setup

set -euo pipefail

# If CLAUDE_PLUGIN_DATA is not set/empty, skip onboarding logic and exit successfully
if [ -z "${CLAUDE_PLUGIN_DATA:-}" ]; then
    exit 0
fi

# Flag file location using Claude Code plugin data directory
CONFIGURED_FLAG="${CLAUDE_PLUGIN_DATA}/state/codeweaver/.configured"

# Check if configured flag exists
if [ ! -f "$CONFIGURED_FLAG" ]; then
    # First run detected - trigger onboarding
    echo "CODEWEAVER_FIRST_RUN=true"
    exit 0
fi

# Already configured - no action needed
exit 0
