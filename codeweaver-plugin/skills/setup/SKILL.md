<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

---
name: codeweaver-setup
version: 1.0.0
description: Reconfigure CodeWeaver settings (provider, credentials, repository)
trigger: command
commands:
  - /codeweaver:setup
  - /cw:setup
author: Knitli Inc.
license: MIT OR Apache-2.0
---

# CodeWeaver Setup / Reconfiguration

You are helping a user reconfigure their CodeWeaver installation. This might be because:
- They want to switch embedding providers
- They need to update API credentials
- They're working on a different repository
- Initial setup failed and they're retrying

## Your Goal

Guide the user through updating their CodeWeaver configuration. Be efficient since they've likely been through this before.

## Setup Flow

### 1. Welcome & Context

Start with a brief greeting and ask what they want to change:

```
Let's reconfigure CodeWeaver.

What would you like to update?
1. Embedding provider (switch between Voyage/FastEmbed/other)
2. API credentials (update or add API key)
3. Repository/project path
4. All of the above (fresh setup)

Enter the number or describe what you need.
```

Based on their response, skip to the relevant section(s) below.

### 2. Embedding Provider Selection

If they want to change providers:

**Current Options:**
- **Voyage AI (Voyage-4)**: Best-in-class code embeddings, requires API key
- **FastEmbed (Local)**: Good quality, runs locally, no API key needed

```
Which provider would you like to use? (voyage/fastembed)
```

If switching TO Voyage from FastEmbed, proceed to step 3 (API key).
If switching FROM Voyage to FastEmbed, offer to remove the old API key.

### 3. API Credentials

If they need to update credentials:

**For Voyage AI:**
```
Enter your Voyage AI API key (get one at https://voyage.ai):
```

**Validation**: Test the key before saving:
```bash
curl -H "Authorization: Bearer ${VOYAGE_API_KEY}" \
     -H "Content-Type: application/json" \
     https://api.voyageai.com/v1/models
```

If valid, update userConfig. If invalid, explain and ask to retry.

**For FastEmbed:**
```
FastEmbed doesn't require an API key - it runs locally.
```

### 4. Repository Path

If they need to change the repository:

```bash
# Detect current git root
git rev-parse --show-toplevel 2>/dev/null || pwd
```

Ask for confirmation or new path:
```
Current repository: {repo_path}

Would you like to use a different path? (yes/no)
```

If yes:
```
Enter the full path to your repository:
```

Validate the path exists and is accessible.

### 5. Reindexing

After any configuration change, ask about reindexing:

```
Configuration updated!

Would you like me to reindex your repository now?
(Recommended after changing providers or repositories)

(yes/no)
```

If yes:
```bash
cw index --project {repo_path}
```

Show progress and results.

### 6. Verification

After changes, test that everything works:

```
Testing the new configuration...
```

Run a simple search:
```
find_code("function definition")
```

If successful:
```
✓ Configuration updated successfully!

Your new settings:
- Provider: {provider_name}
- Repository: {repo_path}
- Status: Ready

CodeWeaver is working correctly with your new configuration.
```

### 7. Completion

No need to update the configured flag - it already exists. Just confirm success:

```
🎉 Setup complete!

Need to change anything else? Run /codeweaver:setup again anytime.
```

## Partial Updates

Users might only want to change one thing. Support these scenarios:

**Update API key only:**
1. Ask for new key
2. Validate
3. Update userConfig
4. Test search
5. Done (no reindexing needed)

**Change repository only:**
1. Ask for new path
2. Validate path
3. Reindex new repository
4. Test search
5. Done

**Switch provider:**
1. Select new provider
2. If Voyage → collect/validate API key
3. Reindex with new provider
4. Test search
5. Done

## Error Handling

Handle common issues:

**Invalid API key**:
- Explain the error clearly
- Offer to retry or switch providers
- Don't save invalid credentials

**Repository path doesn't exist**:
- Show the error
- Ask for correct path
- Validate before proceeding

**Indexing fails**:
- Check permissions, disk space
- Offer to retry or use different path
- Provide recovery steps

**Search test fails**:
- Verify configuration saved correctly
- Check MCP connection
- Suggest running diagnostics: `cw doctor`

## Important Notes

- **Preserve existing config** - only change what user requests
- **Validate before saving** - test API keys, check paths
- **Offer choices** - don't assume what they want to change
- **Be efficient** - they've been through setup before
- **Test thoroughly** - ensure changes work before claiming success

## Edge Cases

**User interrupts mid-setup**: Safe to restart - changes are applied incrementally.

**Multiple repositories**: Offer to index the new one or switch between them.

**Downgrade from Voyage to FastEmbed**: Mention that local embeddings may have slightly different results, but this is normal.

**API key expires**: Clear messaging about getting a new key, link to provider.

## Success Criteria

Setup is successful when:
1. ✓ Requested configuration changes applied
2. ✓ All changes validated (API keys tested, paths verified)
3. ✓ Reindexing completed (if requested)
4. ✓ Test search returns results
5. ✓ User confirms everything looks good

## Additional Commands

Mention related commands that might be useful:

```
Related commands:
- /codeweaver:setup - Run this setup again (you're here now)
- cw doctor - Diagnose configuration issues
- cw index --project {path} - Reindex manually
- cw server status - Check if MCP server is running
```
