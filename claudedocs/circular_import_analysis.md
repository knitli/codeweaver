# Circular Import Analysis & Recommended Fix

**Date**: 2025-01-10
**Status**: Analysis Complete
**Impact**: Prevents pytest execution across entire codebase

## Circular Import Chain

### Complete Dependency Cycle

```
language.py (line 25)
  ↓ imports CustomDelimiter
settings_types.py (line 66)
  ↓ imports LanguageFamily
services/chunker/delimiters/families.py
  ↓ triggers import of
services/__init__.py (line 7)
  ↓ imports FileDiscoveryService
services/discovery.py (line 10)
  ↓ imports DiscoveredFile
_data_structures.py (line 67)
  ↓ imports ConfigLanguage, SemanticSearchLanguage
language.py ← CYCLE COMPLETES
```

### Impact Analysis

**Affected Operations**:
- ❌ Pytest test execution fails
- ❌ Direct module imports from `codeweaver.language` fail when triggered through certain paths
- ✅ Direct imports work when not going through `services/__init__.py`

**Root Cause**:
The cycle is triggered when importing from `settings_types`, which pulls in `services.chunker.delimiters.families`, which triggers Python to load `services/__init__.py`, which then imports `FileDiscoveryService`, creating the full circular dependency.

## Usage Pattern Analysis

### 1. language.py → CustomDelimiter

**Import**: `from codeweaver.settings_types import CustomDelimiter`

**Usage**:
```python
# Line 945: Module-level variable
_custom_delimiters: list[CustomDelimiter] = []

# Line 969: Method return type
def _chunkers(self) -> list[CustomDelimiter]:

# Line 1038: Class method return type
def custom_delimiters(cls) -> list[CustomDelimiter]:

# Line 1066: Method parameter type
def register_custom_chunker(cls, chunker: CustomDelimiter) -> None:
```

**Analysis**:
- ✅ All uses are type annotations
- ✅ Module-level variable `_custom_delimiters` is initialized to empty list
- ✅ No runtime evaluation of CustomDelimiter needed at import time
- ✅ Can use `TYPE_CHECKING` guard

### 2. _data_structures.py → ConfigLanguage, SemanticSearchLanguage

**Import**: `from codeweaver.language import ConfigLanguage, SemanticSearchLanguage`

**Usage**:
```python
# Type annotations in function signatures
def from_node(..., language: SemanticSearchLanguage | None)
def _has_semantic_extension(ext: str) -> SemanticSearchLanguage | None:

# Type annotations in dataclasses
language: str | SemanticSearchLanguage | ConfigLanguage
language: SemanticSearchLanguage | str | None = None

# Runtime usage in function bodies
if isinstance(language, SemanticSearchLanguage):  # Runtime check
if semantic := SemanticSearchLanguage.from_string(language):  # Runtime method call
for config in iter(SemanticSearchLanguage.filename_pairs())  # Runtime iteration
```

**Analysis**:
- ⚠️ Mix of type annotations AND runtime usage
- ❌ Cannot use simple `TYPE_CHECKING` guard for all imports
- ✅ Can defer runtime imports to function bodies
- ✅ Can use `TYPE_CHECKING` for type annotation imports

## Recommended Fix Strategies

### Strategy 1: TYPE_CHECKING Guards (Recommended)

**Complexity**: Low
**Risk**: Low
**Effectiveness**: High

Break the cycle by using `TYPE_CHECKING` guards to defer type annotation imports.

#### Fix for language.py

```python
from __future__ import annotations

from typing import TYPE_CHECKING

# ... other imports ...

if TYPE_CHECKING:
    from codeweaver.settings_types import CustomDelimiter

# Module-level variable works with string annotation
_custom_delimiters: list["CustomDelimiter"] = []

class Chunker(int, BaseEnum):
    def _chunkers(self) -> list["CustomDelimiter"]:  # String annotation
        global _custom_delimiters
        return _custom_delimiters

    @classmethod
    def register_custom_chunker(cls, chunker: "CustomDelimiter") -> None:
        # Import at runtime when actually needed
        global _custom_delimiters
        _custom_delimiters.append(chunker)
```

**Benefits**:
- ✅ Breaks circular import cleanly
- ✅ Minimal code changes
- ✅ Maintains all type checking
- ✅ Standard Python pattern

#### Fix for _data_structures.py

```python
from __future__ import annotations

from typing import TYPE_CHECKING

# ... other imports ...

if TYPE_CHECKING:
    from codeweaver.language import ConfigLanguage, SemanticSearchLanguage

# In function bodies that need runtime access, import locally
def from_node(
    cls,
    node: AstNode[SgNode] | SgNode,
    language: "SemanticSearchLanguage | None"  # String annotation
):
    from codeweaver.language import SemanticSearchLanguage  # Local import

    if isinstance(language, SemanticSearchLanguage):
        ...

def _has_semantic_extension(ext: str) -> "SemanticSearchLanguage | None":
    from codeweaver.language import SemanticSearchLanguage  # Local import

    return next(
        (lang for lang_ext, lang in SemanticSearchLanguage.ext_pairs() if lang_ext == ext),
        None
    )
```

**Benefits**:
- ✅ Type annotations work with string literals
- ✅ Runtime imports only happen when functions are called
- ✅ Breaks circular dependency at import time
- ✅ Common pattern for resolving circular imports

### Strategy 2: Reorganize Module Structure

**Complexity**: High
**Risk**: Medium
**Effectiveness**: High

Create a `types.py` module with shared type definitions to avoid bidirectional dependencies.

#### Changes Required

1. Create `codeweaver/types.py` with core types:
```python
# codeweaver/types.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codeweaver.language import ConfigLanguage, SemanticSearchLanguage
    from codeweaver.settings_types import CustomDelimiter

# Type aliases for easier imports
LanguageType = "ConfigLanguage | SemanticSearchLanguage"
DelimiterListType = "list[CustomDelimiter]"
```

2. Update imports to use central types module

**Benefits**:
- ✅ Cleaner long-term architecture
- ✅ Single source of truth for types
- ⚠️ Requires more refactoring

**Drawbacks**:
- ❌ More files to maintain
- ❌ Larger code changes
- ❌ Potential for confusion about where types live

### Strategy 3: Lazy Imports via __getattr__

**Complexity**: Medium
**Risk**: Medium
**Effectiveness**: Medium

Use module-level `__getattr__` to defer imports until actually accessed.

```python
# language.py
from __future__ import annotations

def __getattr__(name: str):
    if name == "CustomDelimiter":
        from codeweaver.settings_types import CustomDelimiter
        return CustomDelimiter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
```

**Benefits**:
- ✅ Defers import until first use
- ✅ Transparent to calling code

**Drawbacks**:
- ❌ More complex than TYPE_CHECKING
- ❌ Can hide import errors until runtime
- ❌ Harder to understand for maintainers

### Strategy 4: Remove services/__init__.py Export

**Complexity**: Low
**Risk**: Medium
**Effectiveness**: Medium

Stop exporting `FileDiscoveryService` from `services/__init__.py`.

```python
# services/__init__.py - REMOVE THIS:
from codeweaver.services.discovery import FileDiscoveryService

__all__ = ("FileDiscoveryService",)

# Replace with empty or minimal __init__.py
```

**Change all imports**:
```python
# Before
from codeweaver.services import FileDiscoveryService

# After
from codeweaver.services.discovery import FileDiscoveryService
```

**Benefits**:
- ✅ Breaks the cycle at services level
- ✅ More explicit imports

**Drawbacks**:
- ❌ Breaks existing import patterns
- ❌ Less convenient API
- ❌ Requires changes throughout codebase

## Recommended Solution

### Primary Recommendation: Strategy 1 (TYPE_CHECKING Guards)

**Why**:
1. **Minimal changes**: Only affects 2 files significantly
2. **Standard pattern**: Well-known Python idiom for circular imports
3. **Low risk**: Doesn't change module structure or API
4. **High effectiveness**: Cleanly breaks the cycle
5. **Maintains type safety**: Type checkers still work perfectly

**Implementation Priority**:

1. **Phase 1**: Fix `language.py`
   - Add `TYPE_CHECKING` guard for `CustomDelimiter`
   - Use string annotations for type hints
   - ~5-10 minutes

2. **Phase 2**: Fix `_data_structures.py`
   - Add `TYPE_CHECKING` guard for language types
   - Move runtime imports to function bodies
   - Use string annotations
   - ~15-20 minutes

3. **Phase 3**: Validation
   - Run pytest to confirm circular import resolved
   - Run linting to ensure code quality
   - Verify type checking still works
   - ~10 minutes

**Total Estimated Time**: 30-45 minutes

### Alternative Recommendation: Strategy 4 + Strategy 1

If Strategy 1 alone doesn't fully resolve all import paths:

1. Remove `services/__init__.py` exports (Strategy 4)
2. Apply TYPE_CHECKING guards (Strategy 1)
3. Update imports throughout codebase

**Total Estimated Time**: 1-2 hours

## Testing Plan

### Before Fix
```bash
# Current state - should fail
pytest tests/semantic/test_grammar_classifier.py

# Expected output: ImportError: cannot import name 'ConfigLanguage' from partially initialized module
```

### After Fix
```bash
# Should succeed after fix
pytest tests/semantic/test_grammar_classifier.py
pytest tests/semantic/
pytest tests/

# Should all pass without circular import errors
```

### Validation Checklist
- [ ] Pytest runs without ImportError
- [ ] All semantic package tests execute
- [ ] Type checking (pyright/mypy) passes
- [ ] Linting passes
- [ ] No runtime errors in basic usage

## Risk Assessment

### Strategy 1 (TYPE_CHECKING)
- **Risk Level**: Low
- **Breaking Changes**: None (string annotations backward compatible)
- **Rollback**: Easy (just revert changes)

### Strategy 2 (Reorganize)
- **Risk Level**: Medium
- **Breaking Changes**: Potentially affects many imports
- **Rollback**: Difficult (structural changes)

### Strategy 3 (__getattr__)
- **Risk Level**: Medium
- **Breaking Changes**: None
- **Rollback**: Easy

### Strategy 4 (Remove __init__ exports)
- **Risk Level**: Medium
- **Breaking Changes**: Yes (import paths change)
- **Rollback**: Easy (restore __init__.py)

## Conclusion

**Recommendation**: Implement **Strategy 1 (TYPE_CHECKING Guards)** first.

This approach:
- ✅ Fixes the circular import with minimal changes
- ✅ Uses standard Python patterns
- ✅ Maintains full type safety
- ✅ Low risk, easy to implement and test
- ✅ Can be completed in 30-45 minutes

If Strategy 1 doesn't fully resolve all cases, follow up with Strategy 4 (removing services/__init__.py exports) as a secondary fix.
