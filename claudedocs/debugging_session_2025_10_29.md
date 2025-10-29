# Debugging Session: 2025-10-29

## Summary
Investigating and fixing critical bugs preventing the codebase from basic functionality: `get_settings()` hanging, circular imports, and potential test collection issues.

## Issues Identified

### 1. `try_git_rev_parse()` Subprocess Bug ✅ FIXED
**Location**: `src/codeweaver/common/utils/git.py:41-54`

**Problem**: The subprocess command incorrectly included shell pipe operators (`|`, `head`, `-1`) as direct arguments to the git command, causing the command to hang.

**Original Code**:
```python
output = subprocess.run(
    [
        git,
        "rev-parse",
        "--show-superproject-working-tree",
        "--show-toplevel",
        "|",      # ← Invalid: pipe operator as argument
        "head",   # ← Invalid: shell command as argument
        "-1",     # ← Invalid: shell command as argument
    ],
    capture_output=True,
    text=True,
)
```

**Fix**: Split into two separate subprocess calls without shell operators:
```python
# Try superproject first (for submodules)
output = subprocess.run(
    [git, "rev-parse", "--show-superproject-working-tree"],
    capture_output=True,
    text=True,
    check=False,
)
if output.returncode == 0 and output.stdout.strip():
    return Path(output.stdout.strip())

# Fall back to toplevel
output = subprocess.run(
    [git, "rev-parse", "--show-toplevel"],
    capture_output=True,
    text=True,
    check=False,
)
```

### 2. Circular Import: `config.settings` ↔ `engine.chunker.base` ✅ FIXED
**Problem**: Module-level function call caused circular dependency chain:
1. `codeweaver.config.settings` imports
2. `codeweaver.config.chunker` imports
3. `codeweaver.engine.chunker` (includes `base.py`) imports
4. `base.py` calls `_rebuild_models()` at module level (line 245)
5. `_rebuild_models()` imports `get_settings` from partially initialized `config.settings`
6. **CIRCULAR DEPENDENCY**

**Fix**: Made `_rebuild_models()` lazy - removed module-level call, added `model_post_init` hook to `ChunkGovernor`:
```python
_models_rebuilt = False

def _rebuild_models() -> None:
    """Rebuild pydantic models after all types are defined.

    This is called lazily on first use to avoid circular imports with the settings module.
    """
    global _models_rebuilt
    if _models_rebuilt:
        return
    # ... rebuild logic ...
    _models_rebuilt = True

# In ChunkGovernor class:
def model_post_init(self, __context: Any) -> None:
    """Ensure models are rebuilt on first instantiation."""
    _rebuild_models()
    super().model_post_init(__context)
```

### 3. Circular Import: `config.chunker` → `engine.chunker.delimiters` ✅ FIXED
**Location**: `src/codeweaver/config/chunker.py:19`

**Problem**: Top-level import of `DelimiterPattern` and `LanguageFamily` from `engine.chunker.delimiters` created circular dependency.

**Fix**: Use `TYPE_CHECKING` to defer imports and string annotations for forward references:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codeweaver.engine.chunker.delimiters import DelimiterPattern, LanguageFamily

class CustomLanguage(BasedModel):
    language_family: Annotated[
        "LanguageFamily | None",  # ← Quoted for forward reference
        Field(...)
    ] = None

class CustomDelimiter(BasedModel):
    delimiters: Annotated[
        "list[DelimiterPattern]",  # ← Quoted for forward reference
        Field(...)
    ]

class ChunkerSettings(BasedModel):
    custom_languages: Annotated[
        "dict[LanguageNameT, LanguageFamily] | None",  # ← Quoted for forward reference
        Field(...)
    ] = None
```

### 4. Pydantic Forward Reference Resolution ⏳ IN PROGRESS
**Problem**: After fixing circular imports, `CodeWeaverSettings` initialization fails with:
```
PydanticUserError: `CodeWeaverSettings` is not fully defined; you should define `LanguageFamily`,
then call `CodeWeaverSettings.model_rebuild()`.
```

**Root Cause**: Using `defer_build=True` in `ChunkGovernor.model_config` (line 48) and string annotations in `ChunkerSettings` requires explicit `model_rebuild()` after all types are available.

**Next Steps**:
1. Call `CodeWeaverSettings.model_rebuild()` after all types are imported
2. OR remove `defer_build=True` from `ChunkGovernor` if not needed
3. Ensure `ChunkerSettings.model_rebuild()` is called before `CodeWeaverSettings` instantiation

## Test Status

### Unit Tests
- **Not yet run** - waiting for `get_settings()` fix to complete

### Integration Tests
- **Potential hanging** - mentioned by user, not yet investigated
- Hypothesis: May be related to the same circular import issues

## Next Steps
1. ✅ Fix `try_git_rev_parse()` subprocess bug
2. ✅ Fix circular imports in `chunker/base.py`
3. ✅ Fix circular imports in `config/chunker.py`
4. ⏳ Fix Pydantic model_rebuild for forward references
5. ⏳ Run unit tests to verify fixes
6. ⏳ Investigate integration test collection hanging
7. ⏳ Verify all tests pass

## Testing Commands
```bash
# Test get_settings() import
source .venv/bin/activate && python -c "from codeweaver.config.settings import get_settings; s = get_settings(); print(f'Success: {s.project_path}')"

# Run unit tests
source .venv/bin/activate && pytest tests/unit -v

# Run integration tests
source .venv/bin/activate && pytest tests/integration -v

# Run all tests with markers
source .venv/bin/activate && pytest -v -m "not network and not external_api"
```
