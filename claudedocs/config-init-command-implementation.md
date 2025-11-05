<!-- SPDX-FileCopyrightText: 2025 Knitli Inc. -->
<!-- SPDX-FileContributor: Claude Code (Anthropic) -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->

# Config Init Command Implementation

**Date**: 2025-11-05
**Status**: Complete
**File**: `/home/knitli/codeweaver-mcp/src/codeweaver/cli/commands/config.py`

## Overview

Implemented interactive configuration wizard command `codeweaver config init` for first-time project setup. The wizard guides users through creating a complete `.codeweaver.toml` configuration file with intelligent provider selection and validation.

## Features Implemented

### 1. Project Path Selection
- Default to current working directory
- Path validation (exists, is directory)
- Support for tilde expansion

### 2. Embedding Provider Selection
- Common providers with descriptions:
  - Voyage AI (recommended, API key required)
  - OpenAI (API key required)
  - FastEmbed (local, no API key)
  - Cohere (API key required)
- Option to see all available providers
- Dynamic list from PROVIDER_CAPABILITIES

### 3. API Key Management
- Secure password input for API keys
- Optional API key entry (can use env vars)
- Warning messages if keys not provided

### 4. Sparse Embedding Support
- Enabled by default (recommended)
- Automatic provider detection
- Fallback to FastEmbed if current provider doesn't support sparse embeddings

### 5. Reranking Configuration
- Optional feature (disabled by default)
- Provider choices: Voyage, Cohere, FastEmbed
- API key reuse detection (if same as embedding provider)

### 6. Vector Store Configuration
- Default location: `.codeweaver/qdrant` in project directory
- Customizable path

### 7. Configuration Generation
- Uses `CodeWeaverSettings.save_to_file()` method
- Generates valid TOML configuration
- Includes all user selections
- Validation before saving

### 8. User Experience
- Rich console formatting with colors and emojis
- Clear section headers and progress indicators
- Helpful next steps after completion
- Environment variable reminders
- Keyboard interrupt handling (Ctrl+C)

## Command Usage

```bash
# Interactive wizard
codeweaver config init

# Specify output location
codeweaver config init --output /path/to/.codeweaver.toml

# Force overwrite existing config
codeweaver config init --force
```

## Implementation Details

### Key Components

1. **Rich Prompts**: Uses `rich.prompt.Prompt` and `rich.prompt.Confirm` for interactive input
2. **Provider Detection**: Leverages `PROVIDER_CAPABILITIES` for dynamic provider lists
3. **Settings Creation**: Builds nested dictionary structure matching `CodeWeaverSettings` schema
4. **Error Handling**: Comprehensive exception handling with helpful error messages

### Configuration Structure Generated

```python
{
    "project_path": str,
    "provider": {
        "embedding": {
            "provider": str,
            "enabled": True,
            "api_key": str | None
        },
        "sparse_embedding": {
            "provider": str,
            "enabled": True
        } | None,
        "reranking": {
            "provider": str,
            "enabled": True,
            "api_key": str | None
        } | None,
        "vector_store": {
            "provider": "qdrant",
            "enabled": True,
            "client_options": {
                "path": str
            }
        }
    }
}
```

## Code Quality

- Follows project style guidelines (100 char line length)
- Google-style docstrings
- Type hints throughout
- Clean error handling with appropriate exit codes
- Rich console formatting for professional output

## Testing Recommendations

1. **Unit Tests** (future):
   - Mock user input scenarios
   - Test various provider combinations
   - Validate generated configuration structure

2. **Integration Tests** (future):
   - End-to-end wizard flow
   - Configuration file creation and validation
   - Error handling paths

3. **Manual Testing**:
   ```bash
   # Test basic flow
   codeweaver config init

   # Verify config created
   cat .codeweaver.toml

   # Test with existing config
   codeweaver config init  # Should prompt for overwrite

   # Test force flag
   codeweaver config init --force
   ```

## Next Steps

Users can now:
1. Run the wizard: `codeweaver config init`
2. Review configuration: `codeweaver config --show`
3. Index their codebase: `codeweaver index`
4. Start the MCP server: `codeweaver serve`

## Related Files

- `/home/knitli/codeweaver-mcp/src/codeweaver/cli/commands/config.py` - Main implementation
- `/home/knitli/codeweaver-mcp/src/codeweaver/config/settings.py` - Settings model and save_to_file()
- `/home/knitli/codeweaver-mcp/src/codeweaver/providers/capabilities.py` - Provider capability definitions
- `/home/knitli/codeweaver-mcp/src/codeweaver/providers/provider.py` - Provider enum

## Verification

- Syntax check passed
- Import verification successful
- No linting errors introduced
- Follows existing project patterns
