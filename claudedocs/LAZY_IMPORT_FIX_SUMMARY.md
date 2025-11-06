<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Lazy Import Investigation - COMPLETE ✅

## Quick Summary

**Problem Solved**: IDEs couldn't resolve imports from codeweaver.core, codeweaver.config, and codeweaver.common.

**Root Cause Found**: Missing `TYPE_CHECKING` blocks that provide type information to IDEs.

**Solution Applied**: Added TYPE_CHECKING blocks to all three modules, matching Pydantic's proven pattern.

**Result**: Full IDE support (autocomplete, type hints, go-to-definition) while maintaining lazy loading.

---

## What Was Done

### 1. Investigation ✅
- Compared CodeWeaver's implementation with Pydantic's lazy import pattern
- Identified missing TYPE_CHECKING blocks as the critical issue
- Found minor discrepancies in __all__ declarations

### 2. Fixes Applied ✅
- Added comprehensive TYPE_CHECKING blocks to:
  - `src/codeweaver/core/__init__.py`
  - `src/codeweaver/config/__init__.py`
  - `src/codeweaver/common/__init__.py`
- Fixed __all__ discrepancies:
  - Removed non-existent `FileFilterSettings` from codeweaver.config
  - Added missing `DeserializationKwargs` to codeweaver.core

### 3. Validation Tools Created ✅
- `scripts/utils/validate-lazy-imports.py` - Comprehensive validation script
- `scripts/utils/test-lazy-import-ide-support.py` - IDE support verification test

### 4. Documentation ✅
- Enhanced LazyImport docstring with TYPE_CHECKING examples
- Created comprehensive investigation report in `docs/lazy-import-investigation.md`

---

## Testing

Run these commands to verify the fixes:

```bash
# Test IDE support structure
python scripts/utils/test-lazy-import-ide-support.py

# Validate import consistency
python scripts/utils/validate-lazy-imports.py
```

Both tests pass! ✅

---

## Before & After

### Before (Not Working in IDE)
```python
# No TYPE_CHECKING block
from importlib import import_module

_dynamic_imports = {'BasedModel': (__spec__.parent, 'types')}

def __getattr__(name):
    # ... lazy loading ...
```

**Result**: IDE couldn't see types ❌

### After (Works in IDE)
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # IDE sees this!
    from codeweaver.core.types import BasedModel
    
_dynamic_imports = {'BasedModel': (__spec__.parent, 'types')}

def __getattr__(name):
    # ... lazy loading ...
```

**Result**: IDE sees types, runtime is still lazy ✅

---

## LazyImport Class

**Investigated**: Can we improve IDE support for the LazyImport class itself?

**Answer**: No changes needed. The class works well as-is.

**Recommendation**: Users who need IDE support with direct LazyImport usage should use the TYPE_CHECKING pattern:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from actual.module import RealType
else:
    RealType = lazy_import("actual.module", "RealType")
```

This pattern is now documented in the LazyImport docstring.

---

## Key Insight

The pattern that makes this work is called **TYPE_CHECKING Pattern**:

1. **Static Analysis Time** (TYPE_CHECKING=True): IDE/type checkers see real imports
2. **Runtime** (TYPE_CHECKING=False): Imports are lazy via __getattr__

This is a standard Python pattern used by:
- Pydantic ✓
- Pandas ✓
- FastAPI ✓
- Many other major libraries ✓

---

## Files Modified

1. `src/codeweaver/core/__init__.py` - Added TYPE_CHECKING, fixed __all__
2. `src/codeweaver/config/__init__.py` - Added TYPE_CHECKING, fixed __all__
3. `src/codeweaver/common/__init__.py` - Added TYPE_CHECKING
4. `src/codeweaver/common/utils/lazy_importer.py` - Enhanced docs
5. `scripts/utils/validate-lazy-imports.py` - New (validation)
6. `scripts/utils/test-lazy-import-ide-support.py` - New (testing)
7. `docs/lazy-import-investigation.md` - New (documentation)

---

## Try It Out

Open your IDE and test:

```python
from codeweaver.core import BasedModel  # Should autocomplete!
from codeweaver.config import CodeWeaverSettings  # Type hints should work!
from codeweaver.common import lazy_import  # Go-to-definition should work!
```

You should now see:
- ✅ Autocomplete suggestions
- ✅ Type information on hover
- ✅ Go-to-definition (Cmd/Ctrl + Click)
- ✅ No import errors in IDE

---

## Questions Answered

### Q1: Why weren't IDEs resolving the imports?
**A**: Missing TYPE_CHECKING blocks. IDEs perform static analysis and couldn't see the types that were only loaded dynamically at runtime.

### Q2: Does this affect runtime performance?
**A**: No! TYPE_CHECKING blocks are never executed at runtime. The lazy loading still works exactly as before.

### Q3: Will this work with all IDEs?
**A**: Yes! All modern Python IDEs and type checkers (PyCharm, VSCode, mypy, pyright) respect TYPE_CHECKING blocks.

### Q4: Do we need to change the LazyImport class?
**A**: No. The TYPE_CHECKING pattern is the idiomatic solution. LazyImport works well as-is for runtime lazy loading.

---

## Maintenance

The validation script (`scripts/utils/validate-lazy-imports.py`) should be run when:
- Adding new exports to __all__
- Modifying _dynamic_imports
- Changing module structure

This prevents future regressions.

---

## Success Metrics

✅ All three modules now have TYPE_CHECKING blocks
✅ All validation tests pass
✅ IDE support verification test passes
✅ Documentation complete
✅ No runtime changes or performance impact
✅ Follows industry standard patterns (matches Pydantic)

---

## References

- Problem statement: Original issue described IDE resolution problems
- Solution: PEP 484 TYPE_CHECKING pattern
- Pattern source: Pydantic's __init__.py implementation
- Validation: Custom validation script + test script
- Documentation: Complete investigation in docs/lazy-import-investigation.md
