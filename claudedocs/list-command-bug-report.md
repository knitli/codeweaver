# CodeWeaver List Command Bug Report

**Date**: 2025-11-07
**Severity**: CRITICAL
**Affected Commands**: All `codeweaver list` subcommands
**User Report**: "Never returns results"

## Executive Summary

The `codeweaver list` command has TWO critical bugs that prevent it from functioning:

1. **BLOCKER**: The `init` command has broken FastMCP imports, preventing ALL CLI commands from loading
2. **CORE ISSUE**: The provider registry is never initialized, resulting in empty provider lists

## Bug 1: Broken FastMCP Imports in init.py (BLOCKER)

### Root Cause
File: `/home/knitli/codeweaver-mcp/src/codeweaver/cli/commands/init.py` Line 24

```python
from fastmcp import claude_code, claude_desktop, cursor, gemini_cli, mcp_json
```

**Error**: These modules don't exist in the current FastMCP API.

### Impact
- Prevents the entire CLI from loading due to cyclopts lazy loading mechanism
- All commands fail with: `Fatal error: Cannot import module 'codeweaver.cli.commands.init' from 'codeweaver.cli.commands.init:app'`
- User cannot use ANY CLI commands, not just `init`

### Available FastMCP Exports
```python
['Client', 'Context', 'FastMCP', 'Settings', 'client', 'exceptions',
 'fastmcp', 'mcp_config', 'prompts', 'resources', 'server', 'settings',
 'tools', 'utilities', 'warnings']
```

The correct module is `mcp_config` which contains `update_config_file`.

### Fix Required
Replace the broken imports in `init.py` lines 24 with:
```python
from fastmcp.mcp_config import update_config_file
```

Then refactor the code that uses `claude_code`, `claude_desktop`, etc. These appear to be client configuration helpers that no longer exist in the FastMCP API.

### Temporary Workaround Applied
Commented out the init command registration in `/home/knitli/codeweaver-mcp/src/codeweaver/cli/__main__.py`:
```python
# TEMPORARILY DISABLED: init command has FastMCP API compatibility issues
# app.command("codeweaver.cli.commands.init:app", name="init")
```

This allows other commands to function, revealing Bug #2.

## Bug 2: Provider Registry Never Initialized (CORE ISSUE)

### Root Cause
File: `/home/knitli/codeweaver-mcp/src/codeweaver/common/registry/provider.py`

The `get_provider_registry()` function creates a `ProviderRegistry` instance but never calls `_register_builtin_providers()`:

```python
def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry instance."""
    global _provider_registry
    if _provider_registry is None:
        _provider_registry = ProviderRegistry()  # <-- MISSING INITIALIZATION
    return _provider_registry
```

### Current Behavior
1. Registry is created with empty provider dictionaries:
   - `_embedding_providers = {}`
   - `_sparse_embedding_providers = {}`
   - `_vector_store_providers = {}`
   - `_reranking_providers = {}`
   - `_agent_providers = {}`
   - `_data_providers = {}`

2. The `list_providers()` method returns empty lists for all kinds

3. User sees: `No providers found for kind: embedding`

### Impact
- ALL `codeweaver list` subcommands return empty results
- `codeweaver list providers` returns empty table
- `codeweaver list embedding` returns "No providers found"
- `codeweaver list models <provider>` fails silently
- Users cannot discover available providers or models

### Fix Required

**Option 1: Call registration in __init__**
```python
class ProviderRegistry(BasedModel):
    def __init__(self) -> None:
        """Initialize the provider registry."""
        # ... existing initialization code ...

        # Register builtin providers
        self._register_builtin_providers()
        self._register_builtin_pydantic_ai_providers()
```

**Option 2: Call registration in get_provider_registry**
```python
def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry instance."""
    global _provider_registry
    if _provider_registry is None:
        _provider_registry = ProviderRegistry()
        _provider_registry._register_builtin_providers()
        _provider_registry._register_builtin_pydantic_ai_providers()
    return _provider_registry
```

**Recommendation**: Option 1 is cleaner and follows initialization best practices.

## Test Results After Temporary Fix

With init command disabled:

### Working Commands
```bash
$ codeweaver list --help
# Shows all subcommands correctly

$ codeweaver list providers
# Returns "No providers found" (Bug #2)

$ codeweaver list embedding
# Returns "No providers found" (Bug #2)

$ codeweaver list models voyage
# Returns nothing (Bug #2)
```

### Provider Verification
```bash
$ python -c "from codeweaver.providers.provider import Provider; print(len([p for p in Provider if p != Provider.NOT_SET]))"
28  # Providers exist in enum

$ python -c "from codeweaver.common.registry.provider import get_provider_registry; r = get_provider_registry(); print(r.list_providers('embedding'))"
[]  # Registry is empty
```

## Affected Subcommands

All of these commands fail silently due to empty registry:

1. `codeweaver list providers [--kind <kind>]`
2. `codeweaver list models <provider>`
3. `codeweaver list embedding` (shortcut)
4. `codeweaver list sparse_embedding` (shortcut)
5. `codeweaver list vector_store` (shortcut)
6. `codeweaver list reranking` (shortcut)
7. `codeweaver list agent` (shortcut)
8. `codeweaver list data` (shortcut)

Also alias: `codeweaver ls` (same as `list`)

## List Command Logic Analysis

File: `/home/knitli/codeweaver-mcp/src/codeweaver/cli/commands/list.py`

### providers() Command (lines 86-160)
**Logic Flow**:
1. Get provider registry
2. Call `registry.list_providers()` for each ProviderKind
3. Filter by `--kind` if specified
4. Build provider map with capabilities
5. Display table

**Bug**: Step 2 returns empty lists because registry is uninitialized

**Recent Fix**: Line 178 was previously fixed (correct provider conversion)
```python
# OLD (broken): provider = provider if isinstance(...)
# NEW (fixed):  provider = provider_name if isinstance(...)
```

### models() Command (lines 162-211)
**Logic Flow**:
1. Validate provider name
2. Get model registry
3. Call `registry.models_for_provider(provider)`
4. List embedding/sparse/reranking models

**Bug**: Step 3 likely returns empty because provider registry is uninitialized

### Shortcut Commands (lines 310-362)
All shortcuts call `providers(kind=ProviderKind.<KIND>)`, so they inherit the same bug.

## Code Quality Issues Found

### init.py (lines 37-43)
```python
client_modules = {
    "claude_code": claude_code,  # Undefined
    "claude_desktop": claude_desktop,  # Undefined
    "cursor": cursor,  # Undefined
    "mcpjson": mcp_json,  # Undefined
    "gemini_cli": gemini_cli,  # Undefined
}
```

All values reference undefined imports.

### list.py Line 91
```python
kind: Annotated[
    ProviderKind | None,
    cyclopts.Parameter(name=["--kind", "-k"], help="Filter by provider kind"),
] = ProviderKind.EMBEDDING,
```

Default value is `ProviderKind.EMBEDDING`, which means `codeweaver list providers` without arguments filters to embedding only. This may be intentional but seems surprising. Consider changing default to `None` to show all providers.

## Recommended Fix Priority

1. **IMMEDIATE**: Fix init.py FastMCP imports OR keep it disabled
2. **CRITICAL**: Add provider registration call to ProviderRegistry initialization
3. **IMPORTANT**: Test all list subcommands with real data
4. **NICE-TO-HAVE**: Consider default value for `--kind` parameter

## Verification Steps

After fixes are applied:

```bash
# Test 1: Providers list
codeweaver list providers
# Expected: Table with 28+ providers

# Test 2: Filtered providers
codeweaver list providers --kind embedding
# Expected: Subset of providers supporting embedding

# Test 3: Models for specific provider
codeweaver list models voyage
# Expected: Table of Voyage embedding models

# Test 4: Shortcuts
codeweaver list embedding
codeweaver list vector_store
codeweaver list reranking
# Expected: Filtered provider lists

# Test 5: Alias
codeweaver ls providers
# Expected: Same as codeweaver list providers
```

## Files Modified for Testing

- `/home/knitli/codeweaver-mcp/src/codeweaver/cli/__main__.py` (init command commented out)

## Files Requiring Fixes

1. `/home/knitli/codeweaver-mcp/src/codeweaver/cli/commands/init.py` (FastMCP imports)
2. `/home/knitli/codeweaver-mcp/src/codeweaver/common/registry/provider.py` (registration call)

## Bug 3: Registration Logic Error (DISCOVERED)

### Root Cause
File: `/home/knitli/codeweaver-mcp/src/codeweaver/common/registry/provider.py` Line 411

```python
def _get_embedding_provider_name(self, provider: Provider, module: partial[LazyImport[Any]]) -> str:
    """Get the provider name for embedding providers."""
    if provider == Provider.HUGGINGFACE_INFERENCE:
        return "HuggingFaceEmbeddingProvider"
    if module.args[0]._module_name == "codeweaver.providers.embedding.providers.openai_factory":
        #           ^^^ AttributeError: 'str' object has no attribute '_module_name'
        return "OpenAIEmbeddingBase"
    return f"{pascal(str(provider))}EmbeddingProvider"
```

### Error
```
AttributeError: 'str' object has no attribute '_module_name'
```

When calling `_register_builtin_providers()`, the code expects `module.args[0]` to be a LazyImport object with `_module_name` attribute, but it's actually a string.

### Impact
Even with the initialization fix applied, provider registration will crash during startup.

### Fix Required
The `_get_embedding_provider_name` method needs to handle both string and LazyImport module names:

```python
def _get_embedding_provider_name(self, provider: Provider, module: partial[LazyImport[Any]]) -> str:
    """Get the provider name for embedding providers."""
    if provider == Provider.HUGGINGFACE_INFERENCE:
        return "HuggingFaceEmbeddingProvider"

    # Handle both string and LazyImport module names
    module_name = module.args[0]
    if hasattr(module_name, '_module_name'):
        module_name = module_name._module_name

    if module_name == "codeweaver.providers.embedding.providers.openai_factory":
        return "OpenAIEmbeddingBase"
    return f"{pascal(str(provider))}EmbeddingProvider"
```

## Additional Context

The provider registry architecture is well-designed with:
- Lazy loading of provider implementations
- Clear separation of concerns
- Support for multiple provider kinds
- Extensibility for third-party providers

However, there are THREE interconnected bugs preventing functionality:
1. FastMCP API incompatibility blocking CLI initialization
2. Missing provider registration call
3. Type handling error in registration logic

All three must be fixed for the `list` command to work correctly.
