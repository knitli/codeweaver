<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Config Command Fixes Summary

## Overview
Fixed critical issues in `/src/codeweaver/cli/commands/config.py` as specified in the CLI corrections plan.

## Issues Fixed

### 1. Registry Integration (Lines 162-216)
**Problem**: Hardcoded provider list showing only 4 providers, missing 30+ available providers

**Solution**:
- Integrated `ProviderRegistry` via `get_provider_registry()`
- Dynamic provider listing using `registry.list_providers(ProviderKind.EMBEDDING)`
- Provider availability checking with `registry.is_provider_available()`
- Shows all available providers dynamically

**Benefits**:
- Automatically discovers all installed providers
- Shows actual availability (library installed + working)
- No maintenance needed when providers are added
- Accurate provider list matching system capabilities

### 2. Sparse Embedding Provider Selection (Lines 244-270)
**Problem**: Hardcoded sparse provider logic, didn't check registry

**Solution**:
- Query registry for sparse providers: `registry.list_providers(ProviderKind.SPARSE_EMBEDDING)`
- Check current provider against registry, not using deprecated `.is_sparse_provider()`
- Fallback logic respects actual availability

### 3. Reranking Provider Selection (Lines 279-317)
**Problem**: Hardcoded reranking provider list

**Solution**:
- Query registry for reranking providers
- Dynamic menu construction based on availability
- Registry-driven provider selection

### 4. Settings Construction (Lines 346-429) - **CRITICAL FIX**
**Problem**: Manual dict construction bypassed pydantic-settings hierarchy, losing:
- Environment variables (CODEWEAVER_*, VOYAGE_API_KEY, etc.)
- .env file loading
- Secrets manager integration
- Settings precedence hierarchy

**Solution**:
- Use proper TypedDict structures (`EmbeddingProviderSettings`, `SparseEmbeddingProviderSettings`, etc.)
- Build settings with `Provider.from_string()` for proper enum conversion
- Use `SecretStr` for API keys (pydantic security)
- Let `CodeWeaverSettings()` constructor handle precedence:
  1. Direct args (what user configured)
  2. Env vars (CODEWEAVER_PROJECT_PATH, etc.)
  3. .env files
  4. Secrets managers (AWS, Azure, Google)
  5. Existing config files

**Code Pattern**:
```python
# OLD (WRONG) - Bypassed pydantic-settings
settings_data = {
    "project_path": project_path,
    "provider": {"embedding": {"provider": embedding_provider_name, "enabled": True}},
}
settings = CodeWeaverSettings(**settings_data)

# NEW (CORRECT) - Uses pydantic-settings hierarchy
embedding_model_settings: EmbeddingModelSettings = {"model": f"{embedding_provider_name}:default"}
embedding_provider_settings: EmbeddingProviderSettings = {
    "provider": Provider.from_string(embedding_provider_name),
    "enabled": True,
    "model_settings": embedding_model_settings,
}
if api_key:
    embedding_provider_settings["api_key"] = SecretStr(api_key)

settings = CodeWeaverSettings(
    project_path=project_path,
    provider={"embedding": (embedding_provider_settings,), ...},
)
# pydantic-settings automatically merges with env vars, .env, secrets
```

## Testing Recommendations

### Verify Registry Integration
```bash
# Should show all 35+ available providers
codeweaver config init

# Should not error with env vars set
export CODEWEAVER_PROJECT_PATH=/tmp/test
codeweaver config init --quick
```

### Verify Settings Precedence
```bash
# Set env var
export VOYAGE_API_KEY=test-key

# Run config init without providing key
codeweaver config init

# Settings should merge env var with config file
# Verify with: codeweaver config --show
```

### Verify Provider Availability
```bash
# Without voyageai installed
pip uninstall voyageai
codeweaver config init  # Should NOT show voyage in list

# With voyageai installed
pip install voyageai
codeweaver config init  # Should show voyage in list
```

## Files Modified
- `/src/codeweaver/cli/commands/config.py` - All fixes applied

## Dependencies
- `codeweaver.common.registry.get_provider_registry()` - Provider discovery
- `codeweaver.config.providers` - TypedDict structures
- `codeweaver.config.settings.CodeWeaverSettings` - Settings hierarchy
- `pydantic.SecretStr` - Secure API key handling

## Impact
- **High**: Settings construction now respects pydantic-settings precedence
- **High**: Provider selection shows actual system capabilities
- **Medium**: Better UX with accurate provider lists
- **Medium**: No maintenance needed when providers are added/removed

## Evidence Sources
- Provider registry: `/src/codeweaver/common/registry/provider.py` lines 1345-1539
- Settings precedence: `/src/codeweaver/config/settings.py` lines 556-694
- Correction plan: `/claudedocs/CLI_CORRECTIONS_PLAN.md` lines 60-103, 447-500
