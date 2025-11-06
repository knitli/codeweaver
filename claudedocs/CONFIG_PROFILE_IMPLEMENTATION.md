<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Claude Code <noreply@anthropic.com>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Config Profile Support Implementation

**Date**: 2025-11-06
**Status**: ✅ Completed
**File**: `src/codeweaver/cli/commands/config.py`

## Overview

Added quick setup options and config profile support to the `codeweaver config init` command, enabling users to create configurations in <30 seconds using recommended defaults instead of the lengthy interactive wizard.

## Features Implemented

### 1. ConfigProfile Enum ✅

Added enum for three pre-defined configuration profiles:

```python
class ConfigProfile(str, Enum):
    """Configuration profiles for quick setup."""

    RECOMMENDED = "recommended"  # Voyage + Qdrant (high quality)
    LOCAL_ONLY = "local-only"    # FastEmbed + local Qdrant (offline)
    MINIMAL = "minimal"          # Bare minimum config
```

### 2. Quick Setup Flag (`--quick`) ✅

**Usage**: `codeweaver config init --quick`

**Behavior**:
- Uses `profiles.recommended_default()` for instant setup
- Creates config with Voyage (embedding + reranking) + Qdrant
- Completes in <30 seconds
- No interactive prompts

**Implementation**: `_quick_setup()` function

**Output**:
```
Profile: Voyage (embedding + reranking) + Qdrant (vector store)
Features: High-quality embeddings, optimized for code search

✓ Configuration created: /path/to/codeweaver.toml

Next steps:
  1. Set VOYAGE_API_KEY environment variable
  2. Run: codeweaver index
  3. Run: codeweaver serve
```

### 3. Profile Selection (`--profile`) ✅

**Usage**: `codeweaver config init --profile <profile-name>`

**Profiles**:

#### recommended
- **Providers**: Voyage (embedding + reranking) + Qdrant
- **Requires**: `VOYAGE_API_KEY` environment variable
- **Best for**: Production use, high-quality results
- **Source**: `profiles.recommended_default()`

#### local-only
- **Providers**: FastEmbed (dense + sparse) + in-memory Qdrant
- **Requires**: No API keys
- **Best for**: Offline development, testing
- **Features**: Runs completely offline, no external dependencies

#### minimal
- **Providers**: Bare minimum configuration
- **Requires**: Nothing
- **Best for**: Custom configuration starting point

**Implementation**: `_profile_setup()` function

### 4. Config Location Options ✅

#### `--user` Flag
- **Location**: `~/.config/codeweaver/config.toml` (Linux/Mac)
- **Location**: `%APPDATA%\codeweaver\config.toml` (Windows)
- **Usage**: User-level configuration affecting all projects
- **Created**: Directory auto-created if doesn't exist

#### `--local` Flag
- **Location**: `./.codeweaver.toml` (current directory)
- **Usage**: Local override for specific project
- **Priority**: Highest precedence in config hierarchy

#### Default Behavior (no flags)
- **Location**: `<project_path>/codeweaver.toml`
- **Usage**: Project-specific configuration

**Implementation**: `_get_config_path()` function

**Config Hierarchy** (from highest to lowest precedence):
1. `--output` custom path
2. `--user` flag → user config directory
3. `--local` flag → current directory `.codeweaver.toml`
4. Default → project directory `codeweaver.toml`

### 5. Enhanced Sparse Embedding Guidance ✅

**Added to Interactive Wizard**:

```
Sparse Embedding (Hybrid Search)

CodeWeaver supports hybrid search combining dense + sparse embeddings.
Sparse embeddings improve keyword matching and run locally (no API cost).

Note: fastembed supports both dense and sparse embeddings

Available sparse providers:
  1. fastembed - FastEmbed Splade (recommended, local)
  2. sentence-transformers - Sentence Transformers (local)
  3. Skip sparse embeddings (dense-only search)
```

**Benefits**:
- Educates users about hybrid search capabilities
- Highlights local/offline sparse embedding options
- Shows which dense embedding providers also support sparse
- No additional API costs for sparse embeddings

## Usage Examples

### Quick Setup (Fastest)
```bash
# Creates config with recommended defaults in <30s
codeweaver config init --quick

# Quick setup in user config location
codeweaver config init --quick --user
```

### Profile-Based Setup
```bash
# Use recommended profile (Voyage + Qdrant)
codeweaver config init --profile recommended

# Use local-only profile (no API keys)
codeweaver config init --profile local-only

# Use minimal profile (customize yourself)
codeweaver config init --profile minimal
```

### Location-Specific Setup
```bash
# Create user-level config
codeweaver config init --user

# Create local override config
codeweaver config init --local

# Create config at custom location
codeweaver config init --output /path/to/config.toml
```

### Combined Options
```bash
# Quick setup with local config file
codeweaver config init --quick --local

# Profile-based setup in user config
codeweaver config init --profile local-only --user
```

## Implementation Details

### Helper Functions

#### `_get_config_path()`
```python
def _get_config_path(
    output: Path | None,
    user: bool,
    local: bool,
    project_path: Path,
) -> Path:
    """Determine config path based on flags."""
```

**Logic**:
1. If `output` provided → use custom path
2. If `user` flag → user config directory
3. If `local` flag → `.codeweaver.toml` in current directory
4. Default → `codeweaver.toml` in project directory

#### `_quick_setup()`
```python
def _quick_setup(
    output: Path | None,
    force: bool,
    user: bool,
    local: bool,
) -> None:
    """Quick setup using recommended defaults."""
```

**Steps**:
1. Display profile information
2. Get project path from `get_project_path()`
3. Determine config path using `_get_config_path()`
4. Check for existing config (respect `--force`)
5. Load recommended profile from `profiles.recommended_default()`
6. Create `CodeWeaverSettings` with profile
7. Save to file using `settings.save_to_file()`
8. Display next steps and required environment variables

#### `_profile_setup()`
```python
def _profile_setup(
    profile: ConfigProfile,
    output: Path | None,
    force: bool,
    user: bool,
    local: bool,
) -> None:
    """Setup using a named profile."""
```

**Profile Configuration**:

**RECOMMENDED**:
```python
provider_settings = recommended_default()
# Uses: Voyage (embedding + reranking) + Qdrant
# Requires: VOYAGE_API_KEY
```

**LOCAL_ONLY**:
```python
provider_settings = {
    "embedding": (
        EmbeddingProviderSettings(
            provider=Provider.FASTEMBED,
            model_settings={"model": "BAAI/bge-small-en-v1.5"},
        ),
    ),
    "sparse_embedding": (
        SparseEmbeddingProviderSettings(
            provider=Provider.FASTEMBED,
            model_settings={"model": "prithivida/Splade_PP_en_v1"},
        ),
    ),
    "vector": (
        VectorStoreProviderSettings(
            provider=Provider.QDRANT,
            provider_settings={"client_options": {"path": ":memory:"}},
        ),
    ),
}
# No API keys required, runs offline
```

**MINIMAL**:
```python
settings = CodeWeaverSettings(project_path=project_path)
# Bare minimum, user customizes
```

## Testing

All tests passed:

```
✓ ConfigProfile enum values correct
✓ Default config path works
✓ Local config path works
✓ Custom output path works
✓ Profile imports work correctly
```

## Command Help Output

```
Usage: config init [ARGS]

Interactive configuration wizard for first-time setup.

Creates a new .codeweaver.toml configuration file with guided prompts.

Quick start: codeweaver config init --quick
With profile: codeweaver config init --profile local-only
User config: codeweaver config init --user

╭─ Parameters ─────────────────────────────────────────╮
│ OUTPUT --output -o          │                        │
│ FORCE --force --no-force -f │ [default: False]       │
│ QUICK --quick --no-quick -q │ [default: False]       │
│ PROFILE --profile           │ [choices: recommended, │
│                             │  local-only, minimal]  │
│ USER --user --no-user       │ [default: False]       │
│ LOCAL --local --no-local    │ [default: False]       │
╰──────────────────────────────────────────────────────╯
```

## Integration with Existing Code

### Maintains Backward Compatibility ✅
- Interactive wizard still works as before
- All existing flags (`--output`, `--force`) still function
- No breaking changes to existing behavior

### Early Exit Pattern ✅
```python
# Handle quick setup flag
if quick:
    _quick_setup(output, force, user, local)
    return

# Handle profile-based setup
if profile:
    _profile_setup(profile, output, force, user, local)
    return

# Continue with interactive wizard...
```

### Reuses Existing Infrastructure ✅
- Uses `profiles.recommended_default()` from `config/profiles.py`
- Uses `CodeWeaverSettings` pydantic model
- Uses `settings.save_to_file()` for writing configs
- Uses `get_project_path()` for path detection
- Uses `get_user_config_dir()` for user config location

## Code Quality

### Linting ✅
- Passed all ruff checks
- No new linting violations introduced

### Type Checking ✅
- Passed pyright validation
- Proper type hints on all new functions
- Consistent with project typing standards

### Code Style ✅
- Follows project conventions
- Consistent with existing config command style
- Uses Rich console for formatted output
- Proper error handling with try/except

## Benefits

### User Experience
1. **Fast Setup**: <30 seconds with `--quick` flag
2. **Clear Choices**: Three named profiles with clear purposes
3. **Flexibility**: Config location options for different use cases
4. **Education**: Enhanced guidance about sparse embeddings

### Developer Experience
1. **Modular Design**: Separate functions for quick/profile/location logic
2. **Maintainable**: Clear separation of concerns
3. **Extensible**: Easy to add new profiles or options
4. **Testable**: Helper functions easily unit-testable

### Performance
1. **Zero Additional Dependencies**: Uses existing infrastructure
2. **Fast Execution**: Quick setup completes in seconds
3. **No Breaking Changes**: Fully backward compatible

## Future Enhancements

Possible future additions (not implemented):

1. **Additional Profiles**:
   - `enterprise`: For large-scale production deployments
   - `development`: Optimized for local development
   - `testing`: Minimal setup for CI/CD

2. **Profile Management**:
   - `codeweaver config list-profiles` - List available profiles
   - `codeweaver config show-profile <name>` - Show profile details
   - Custom user-defined profiles in `~/.config/codeweaver/profiles/`

3. **Interactive Profile Selection**:
   - Menu-driven profile selection in wizard
   - Profile recommendations based on project type

4. **Config Validation**:
   - `codeweaver config validate` - Validate current config
   - Check for required API keys and provider availability

## Related Files

- `/home/knitli/codeweaver-mcp/src/codeweaver/cli/commands/config.py` - Main implementation
- `/home/knitli/codeweaver-mcp/src/codeweaver/config/profiles.py` - Profile definitions
- `/home/knitli/codeweaver-mcp/src/codeweaver/config/settings.py` - Settings model
- `/home/knitli/codeweaver-mcp/src/codeweaver/common/utils/utils.py` - Utility functions

## Evidence

Implementation follows the correction plan from:
`/home/knitli/codeweaver-mcp/claudedocs/CLI_CORRECTIONS_PLAN.md` lines 336-357

All validation criteria met:
- ✅ `--quick` flag creates config in <30 seconds
- ✅ `--profile` supports all three profiles
- ✅ `--user` and `--local` create configs in correct locations
- ✅ Sparse embedding information displayed during interactive setup
- ✅ All options work with existing interactive wizard
