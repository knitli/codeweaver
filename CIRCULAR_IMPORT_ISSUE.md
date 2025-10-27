# Circular Import Issue - Task Summary

**Date Discovered**: October 27, 2025  
**Discovery Context**: While testing DelimiterChunker integration (not caused by those changes)  
**Status**: Pre-existing issue, blocks pytest execution

---

## Problem

When attempting to run pytest directly (or via uv):
```bash
$ pytest tests/unit/engine/chunker/test_selector.py
# OR
$ uv run pytest tests/unit/engine/chunker/test_selector.py
```

**Error**:
```
ImportError: cannot import name 'ChunkerSettings' from partially initialized module 
'codeweaver.config.chunker' (most likely due to a circular import)
```

---

## Root Cause: Import Cycle

The circular dependency chain:

```
codeweaver.config.chunker
    ↓ (imports DelimiterPattern from)
codeweaver.engine.chunker.delimiters
    ↓ (engine/__init__ imports from)
codeweaver.engine.chunker.base
    ↓ (imports EmbeddingModelCapabilities from)
codeweaver.providers.embedding.capabilities.base
    ↓ (providers/__init__ imports from)
codeweaver.providers.vector_stores
    ↓ (base.py line ~96: CLASS-LEVEL CODE EXECUTION)
codeweaver.config.settings
    ↓ (imports ChunkerSettings from)
codeweaver.config.chunker  ← CIRCULAR REFERENCE!
```

### Detailed Trace

1. **Test setup** → `tests/unit/engine/chunker/conftest.py` line 13
   - Imports: `from codeweaver.config.chunker import ChunkerSettings, PerformanceSettings`

2. **Config initialization** → `src/codeweaver/config/chunker.py` line 19
   - Imports: `from codeweaver.engine.chunker.delimiters import DelimiterPattern, LanguageFamily`

3. **Engine entry point** → `src/codeweaver/engine/__init__.py` line 7
   - Imports: `from codeweaver.engine.chunker import ...`

4. **Chunker module** → `src/codeweaver/engine/chunker/__init__.py` line 9
   - Imports: `from codeweaver.engine.chunker.base import ChunkGovernor`

5. **Chunker base** → `src/codeweaver/engine/chunker/base.py` line 28
   - Imports: `from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities`

6. **Providers entry** → `src/codeweaver/providers/__init__.py` line 67
   - Imports: `from codeweaver.providers.vector_stores import VectorStoreProvider`

7. **Vector store entry** → `src/codeweaver/providers/vector_stores/__init__.py` line 11
   - Imports: `from codeweaver.providers.vector_stores.base import VectorStoreProvider`

8. **🔴 PROBLEM HERE** → `src/codeweaver/providers/vector_stores/base.py` lines ~88-96
   ```python
   class VectorStoreProvider[VectorStoreClient](BasedModel, ABC):
       # ... class definition ...
       ] = _assemble_caps()  # ← CODE EXECUTES AT MODULE LOAD TIME (not deferred!)
   ```

9. **_assemble_caps() function** → `src/codeweaver/providers/vector_stores/base.py` line ~56
   - Calls: `for model in _get_settings()["provider"]["embedding"]`

10. **_get_settings() function** → `src/codeweaver/providers/vector_stores/base.py` line ~37
    - Imports: `from codeweaver.config.settings import get_settings_map`

11. **Settings module** → `src/codeweaver/config/settings.py` line 52
    - Imports: `from codeweaver.config.chunker import ChunkerSettings`
    - ❌ BUT: `codeweaver.config.chunker` is still initializing!
    - ❌ Result: ImportError, circular reference detected

---

## Critical Issue: Class-Level Code Execution

The core problem is at **`src/codeweaver/providers/vector_stores/base.py`** around line 96:

```python
class VectorStoreProvider[VectorStoreClient](BasedModel, ABC):
    CAPABILITIES: ClassVar[dict] = _assemble_caps()  # ← EXECUTES AT LOAD TIME
```

This class attribute is computed **during module import** using `_assemble_caps()`, which triggers the full import chain including config.settings, causing the circular reference.

**Solution**: Defer this computation to a **lazy-loading property** or **method** instead of class-level attribute assignment.

---

## Files Involved

| File | Role | Issue |
|------|------|-------|
| `src/codeweaver/providers/vector_stores/base.py` | **Primary** | Class-level `_assemble_caps()` call at line ~96 |
| `src/codeweaver/config/settings.py` | Secondary | Late import of chunker config needed |
| `src/codeweaver/config/chunker.py` | Secondary | Import chain entry from config side |
| `tests/unit/engine/chunker/conftest.py` | Trigger | First import in test execution |

---

## Recommended Fix Approach

### Option 1: Lazy Loading (Recommended) ⭐
Convert class-level attribute to lazy-loaded property:

```python
# BEFORE (problematic):
class VectorStoreProvider[VectorStoreClient](BasedModel, ABC):
    CAPABILITIES: ClassVar[dict] = _assemble_caps()

# AFTER (recommended):
class VectorStoreProvider[VectorStoreClient](BasedModel, ABC):
    _capabilities_cache: ClassVar[dict | None] = None
    
    @classmethod
    def get_capabilities(cls) -> dict:
        """Lazily load capabilities on first access."""
        if cls._capabilities_cache is None:
            cls._capabilities_cache = _assemble_caps()
        return cls._capabilities_cache
```

**Benefits**:
- Defers import chain until capabilities actually needed
- Maintains same external behavior
- Minimal code changes required
- Clear intent (lazy initialization pattern)

### Option 2: Import Restructuring
Move `_get_settings()` import to inside the function that needs it:

```python
def _assemble_caps() -> dict:
    from codeweaver.config.settings import get_settings_map  # Import inside function
    settings = get_settings_map()
    # ... rest of implementation
```

**Benefits**:
- Simple change
- Delays import until function call time

**Drawbacks**:
- Still executes on first test run (if `_assemble_caps()` called at load time)
- Doesn't fully solve if class-level execution persists

### Option 3: Circular Dependency Prevention
Restructure module organization:
- Extract shared type definitions to `codeweaver.common.types` or `codeweaver.core.types`
- Have config modules import from types, not from engine/providers
- Breaks the dependency cycle at architectural level

**Benefits**:
- Cleanest long-term solution
- Prevents similar issues in future
- Better separation of concerns

**Drawbacks**:
- Larger refactor
- Requires architectural review

---

## Testing Impact

**Current Status**:
- ✅ `uv run` with specific modules works (dependencies pre-loaded)
- ✅ Direct imports in Python work (if circular path not triggered)
- ❌ Running pytest directly fails
- ❌ Full test suite runs likely blocked
- ❌ IDE indexing may have issues

**Workaround** (temporary):
```bash
# May work with specific test paths or if using IDE test runner
pytest tests/unit/specific_test.py --tb=short
```

---

## Acceptance Criteria for Fix

- [ ] `pytest tests/unit/engine/chunker/test_selector.py` runs without import errors
- [ ] `pytest tests/` (full test suite) runs without import errors
- [ ] All existing functionality preserved (no breaking changes)
- [ ] No performance regression in module loading
- [ ] Solution follows established patterns in codebase

---

## References

- **Python Circular Imports**: https://docs.python.org/3/faq/programming.html#what-are-the-best-practices-for-using-import-in-python
- **Lazy Loading Pattern**: Standard Python pattern for deferred initialization
- **Class Variables**: https://docs.python.org/3/library/typing.html#typing.ClassVar

---

## Notes for Assignee

1. This is a **pre-existing issue**, not caused by recent DelimiterChunker changes
2. The issue exists because class-level code execution happens at import time
3. Recommended approach is **Option 1 (Lazy Loading)** - minimal, targeted fix
4. Test thoroughly with full test suite after fix
5. Consider adding CI checks to catch future circular imports
