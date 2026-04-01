<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Onboarding Agent

Interactive first-run setup for the CodeWeaver plugin. Runs automatically on first session via SessionStart hook.

## Overview

This agent guides users through:
1. **Embedding provider selection** (Voyage AI or FastEmbed)
2. **API credential configuration** (secure keychain storage)
3. **Repository indexing** (initial codebase scan)
4. **Connection verification** (test search)
5. **Completion flag** (prevents re-run)

## Trigger Mechanism

The onboarding agent is triggered by the SessionStart hook when `CODEWEAVER_FIRST_RUN=true` is set by the `check-first-run.sh` script.

**Flow:**
1. User starts new Claude Code session after plugin install
2. SessionStart hook runs `hooks/scripts/check-first-run.sh`
3. Script checks for `${CLAUDE_PLUGIN_DATA}/state/codeweaver/.configured`
4. If flag missing → sets `CODEWEAVER_FIRST_RUN=true`
5. Onboarding agent activates (condition in SKILL.md frontmatter)
6. Interactive setup begins

## Provider Options

### Voyage AI (Recommended)
- **Quality**: Best-in-class code embeddings (Voyage-4 model)
- **Performance**: Optimized for semantic code search
- **Cost**: Free tier available, pay-as-you-go
- **Setup**: Requires API key from https://voyage.ai
- **Storage**: Credentials stored securely in system keychain

### FastEmbed (Local)
- **Quality**: Good embedding quality
- **Performance**: Runs entirely on local machine
- **Cost**: Zero cost (no API)
- **Setup**: No configuration needed
- **Storage**: Models cached locally

## Configuration Storage

### API Keys (Secure)
Stored via Claude Code's `userConfig` system with `sensitive: true`:
- **macOS**: Keychain Access
- **Linux**: Secret Service (GNOME Keyring, KWallet)
- **Windows**: Credential Manager

### Configured Flag
Location: `${CLAUDE_PLUGIN_DATA}/state/codeweaver/.configured`

This empty file signals that onboarding completed successfully. Only written after all steps pass.

## Error Handling

The agent handles common failures gracefully:

### API Key Validation Fails
- Test key with Voyage API before saving
- If invalid: explain error, offer retry or switch to FastEmbed
- Never save invalid credentials

### Repository Detection Fails
- Try `git rev-parse --show-toplevel` first
- Fall back to `pwd` if not in git repo
- Ask user to confirm or provide correct path

### Indexing Fails
- Check for permission errors, disk space issues
- Show clear error messages
- Offer recovery steps (retry, different path)

### Search Test Fails
- Verify indexing completed successfully
- Check provider configuration
- Suggest running `cw doctor` for diagnostics

### Interrupted Setup
- Safe to restart - no flag written until complete
- User can re-run from beginning
- Partial configuration won't break future attempts

## Testing the Onboarding

To test the onboarding flow manually:

1. **Remove configured flag:**
   ```bash
   rm "${CLAUDE_PLUGIN_DATA}/state/codeweaver/.configured"
   ```

2. **Start new Claude Code session** - onboarding should trigger automatically

3. **Or trigger manually** via the condition in testing:
   ```bash
   export CODEWEAVER_FIRST_RUN=true
   ```

## Related Files

- `hooks/hooks.json` - SessionStart hook configuration
- `hooks/scripts/check-first-run.sh` - First-run detection
- `skills/setup/SKILL.md` - Reconfiguration skill (`/codeweaver:setup`)
- `.claude-plugin/plugin.json` - User config definition for credentials

## Success Criteria

Onboarding completes successfully when:

1. ✓ Embedding provider selected and validated
2. ✓ API credentials stored (if applicable)
3. ✓ Repository path confirmed
4. ✓ Indexing completed without errors
5. ✓ Test search returns results
6. ✓ Configured flag written

Only when ALL criteria are met is the flag written, preventing the onboarding from running again.

## User Experience Notes

- **First impression matters**: Be warm, clear, and efficient
- **Show progress**: Users should always know what's happening
- **Validate everything**: Test API keys, verify paths, confirm search works
- **Fail gracefully**: Clear error messages with recovery steps
- **Security conscious**: Emphasize that credentials are stored securely
- **One-time only**: Never trigger again after successful completion

## Future Enhancements

Potential improvements for future versions:

- Multi-repository support (index multiple projects)
- Provider auto-detection (recommend based on project size)
- Progress bars for indexing
- Diagnostic mode (pre-flight checks before setup)
- Alternative providers (Cohere, OpenAI, HuggingFace)
