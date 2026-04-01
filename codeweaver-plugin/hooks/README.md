<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Hooks

This directory contains Claude Code hooks for event-driven automation.

## Current Hooks

### SessionStart Hook
Detects first-run to trigger interactive onboarding. Checks for a configured flag and sets `CODEWEAVER_FIRST_RUN=true` if not found, which activates the onboarding agent.

**Files:**
- `hooks.json` - Hook configuration
- `scripts/check-first-run.sh` - First-run detection script

## Coming Soon

We're planning to add additional hooks for:
- **Pre-search optimization**: Query enhancement before code search
- **Post-search enrichment**: Adding context to search results
- **Indexing triggers**: Automatic reindexing on file changes
- **Result filtering**: Custom filtering logic for search results

## Hook Types

Claude Code supports several hook types:
- `user-prompt-submit`: Run before Claude processes your message
- `tool-call`: Run before/after tool execution
- `file-edit`: Run when files are modified
- And more...

## Contributing

Interested in contributing hooks? Open a [plugin contribution issue](https://github.com/knitli/codeweaver/issues/new?template=plugin-contribution.yml) to propose a new hook or track progress on planned hooks.

## Structure

Hooks are shell scripts that follow naming conventions:
```
hooks/
  user-prompt-submit.sh    # Runs on every message
  tool-call-before.sh      # Runs before tool calls
  tool-call-after.sh       # Runs after tool calls
```

See [Claude Code hooks documentation](https://code.claude.com/docs/en/hooks) for details.
