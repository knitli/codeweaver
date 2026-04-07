# Implementation Plan: Issue #307 - Fix bootstrap_settings Coroutine Never Awaited

## Summary

Fix the bug where `ensure_settings_initialized()` calls async `bootstrap_settings()` without awaiting it, causing RuntimeWarning spam and silent bootstrap failures.

**Solution**: Option 3 - Split into sync and async entry points with explicit contracts.

## Root Cause

`src/codeweaver/core/dependencies/utils.py:63` calls `bootstrap_settings()` (an async coroutine) from sync function `ensure_settings_initialized()` without awaiting. Python creates the coroutine object but never executes it, causing:
- `RuntimeWarning: coroutine 'bootstrap_settings' was never awaited`
- Settings initialization side effects (`settings._initialize()`, DI registration) never run
- State flag `_settings_initialized` set to True despite bootstrap not running

## Call Site Analysis

### Module-Level Sync Calls (2)
These run during import, before any event loop exists:

1. **`src/codeweaver/providers/dependencies/config.py:15`**
   ```python
   ensure_settings_initialized()  # Module-level import-time call
   ```

2. **`src/codeweaver/core/dependencies/services.py:11`**
   ```python
   ensure_settings_initialized()  # Module-level import-time call
   ```

**Strategy**: These need sync-safe version that checks if already initialized. If not, raise informative error directing user to bootstrap properly.

### Sync Function Call (1)

3. **`src/codeweaver/core/dependencies/component_settings.py:29`**
   ```python
   def _global_settings() -> CodeWeaverSettingsType:
       ensure_settings_initialized()  # Inside sync function
       container = get_container()
       return container[CodeWeaverSettingsType]
   ```

**Strategy**: This is called by `@dependency_provider` factories that are defined as sync but may be resolved from async contexts. Keep sync version but ensure it checks for existing settings.

### Async Function Call (1)

4. **`src/codeweaver/providers/dependencies/capabilities.py:87`**
   ```python
   @dependency_provider(ConfiguredCapability, scope="singleton", collection=True)
   async def _create_all_configured_capabilities() -> tuple[ConfiguredCapability, ...]:
       ensure_settings_initialized()  # ← Inside async function!
       ...
   ```

**Strategy**: Replace with `await ensure_settings_initialized_async()`.

## Implementation Steps

### 1. Create `ensure_settings_initialized_async()` in `utils.py`

```python
async def ensure_settings_initialized_async() -> None:
    """Ensure settings are initialized in the DI container (async version).

    This should be called from async contexts to properly bootstrap settings.
    It will await the async bootstrap_settings() if needed.

    Raises:
        Exception: If settings initialization fails
    """
    if globals()["_container_initialized"] is False:
        ensure_container_initialized()
    if globals()["_settings_initialized"] is False:
        if not _try_to_resolve_settings():
            from codeweaver.core.dependencies.core_settings import bootstrap_settings

            await bootstrap_settings()  # ← Properly awaited!
        globals()["_settings_initialized"] = True
```

### 2. Update `ensure_settings_initialized()` to be Sync-Safe

```python
def ensure_settings_initialized() -> None:
    """Ensure settings are initialized in the DI container (sync version).

    This checks if settings are already initialized. If not, it raises an error
    directing the caller to use the async version or bootstrap settings properly.

    Use this in sync contexts where settings should already be initialized
    (e.g., after async bootstrap has run).

    Raises:
        RuntimeError: If settings are not initialized
    """
    if globals()["_container_initialized"] is False:
        ensure_container_initialized()
    if globals()["_settings_initialized"] is False:
        if not _try_to_resolve_settings():
            raise RuntimeError(
                "Settings are not initialized. Settings must be initialized from an async "
                "context using ensure_settings_initialized_async() or bootstrap_settings() "
                "before accessing them from sync code.\n\n"
                "Common causes:\n"
                "  - Importing a module that depends on settings before bootstrapping\n"
                "  - Calling settings-dependent code outside an async context\n\n"
                "Solutions:\n"
                "  - Call await ensure_settings_initialized_async() from an async function\n"
                "  - Use the server/CLI startup paths that handle bootstrap automatically"
            )
        # If _try_to_resolve_settings() returned True, settings exist in container
        globals()["_settings_initialized"] = True
```

### 3. Update Call Sites

#### `src/codeweaver/providers/dependencies/capabilities.py:87`
```python
# BEFORE
ensure_settings_initialized()

# AFTER
await ensure_settings_initialized_async()
```

Also update import:
```python
from codeweaver.core.dependencies.utils import ensure_settings_initialized_async
```

#### Other Call Sites (Keep Sync Version)
The module-level calls in `config.py` and `services.py` will now raise informative errors if settings aren't already initialized. This is correct behavior - these modules shouldn't be imported before settings bootstrap.

The `_global_settings()` call will also raise if settings don't exist, which is correct - it's a helper that assumes settings are available.

### 4. Update `__all__` Exports

In `src/codeweaver/core/dependencies/utils.py`:
```python
__all__ = ("ensure_container_initialized", "ensure_settings_initialized", "ensure_settings_initialized_async")
```

Also update exports in:
- `src/codeweaver/core/dependencies/__init__.py`
- `src/codeweaver/core/__init__.py`
- `src/codeweaver/__init__.py`

### 5. Add Tests

Create test cases in appropriate test file (likely `tests/unit/test_dependencies.py` or similar):

1. **Test async version properly awaits**:
   - Call `ensure_settings_initialized_async()` from async test
   - Verify no warnings
   - Verify settings are in container

2. **Test sync version when settings exist**:
   - Bootstrap settings first (async)
   - Call sync `ensure_settings_initialized()`
   - Should succeed without errors

3. **Test sync version when settings don't exist**:
   - Don't bootstrap
   - Call sync `ensure_settings_initialized()`
   - Should raise RuntimeError with helpful message

4. **Test idempotency**:
   - Call async version multiple times
   - Should not re-bootstrap

## Expected Behavior After Fix

### ✅ Correct Paths

1. **CLI/Server startup**: Async bootstrap runs, then sync code can use settings
2. **Integration tests**: Async fixtures bootstrap, sync test code works
3. **Async dependency factories**: Can call `await ensure_settings_initialized_async()`

### 🚫 Prevented Errors

1. **Module import before bootstrap**: Clear error message instead of silent failure
2. **Sync call to async bootstrap**: No more coroutine warnings
3. **Partially initialized state**: Settings initialization is all-or-nothing

## Rollout Considerations

### Breaking Changes?

**Minimal**. The only breaking change is that code attempting to import settings-dependent modules before bootstrap will now get a clear error instead of silently failing.

This is actually a **fix** - code that was silently broken will now fail loudly with instructions.

### Migration Guide

If users encounter the new error:

1. **For CLI users**: No changes needed - CLI handles bootstrap
2. **For test writers**: Use async fixtures to bootstrap (already best practice)
3. **For library users**: Call `await ensure_settings_initialized_async()` before importing settings-dependent modules

## Testing Strategy

1. Run existing integration tests - should pass (they use async fixtures)
2. Add new unit tests for both versions
3. Verify no `RuntimeWarning` in CI logs
4. Manual test: Try to import a settings-dependent module before bootstrap, verify clear error

## Success Criteria

- [ ] No `RuntimeWarning: coroutine 'bootstrap_settings' was never awaited` in CI
- [ ] Integration tests pass
- [ ] Unit tests cover both sync and async paths
- [ ] Clear error messages when sync path hit inappropriately
- [ ] Code review approved
- [ ] PR merged

## References

- Original issue: #307
- Related PR: #302 (where warnings were discovered)
- DI integration guide: `.specify/memory/di-integration-progress.md`
