# Lazy Import Investigation - Summary & Recommendations

## Problem Statement

The codeweaver.core, codeweaver.config, and codeweaver.common modules used a lazy import pattern borrowed from Pydantic, but IDEs couldn't resolve the import chain. The pattern worked at runtime but failed to provide IDE support.

## Root Cause

**The missing ingredient was TYPE_CHECKING blocks.**

While CodeWeaver had implemented:
- ✅ `_dynamic_imports` dictionary mapping names to modules
- ✅ `__getattr__` for runtime lazy loading
- ✅ `__all__` for public API declaration

It was **missing**:
- ❌ `TYPE_CHECKING` blocks with real imports for IDE/type checker support

This is the key difference between Pydantic's implementation (which works in IDEs) and CodeWeaver's original implementation (which didn't).

## How Pydantic's Pattern Works

Pydantic uses a clever combination:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Real imports that IDEs and type checkers see
    from .main import BaseModel
    from .fields import Field
    # ... etc

# Dynamic imports dict for runtime lazy loading
_dynamic_imports = {
    'BaseModel': (__spec__.parent, '.main'),
    'Field': (__spec__.parent, '.fields'),
    # ... etc
}

def __getattr__(name: str):
    # Runtime lazy loading logic
    if name in _dynamic_imports:
        module = import_module(...)
        return getattr(module, name)
    raise AttributeError(...)

__all__ = ('BaseModel', 'Field', ...)
```

### Why This Works

1. **IDE/Type Checker**: Sees the imports in the `TYPE_CHECKING` block and provides full autocomplete and type information
2. **Runtime**: The `TYPE_CHECKING` block is never executed (TYPE_CHECKING is always False at runtime), so imports are actually lazy via `__getattr__`
3. **Result**: Best of both worlds - excellent IDE support AND lazy loading

## What We Fixed

### 1. Added TYPE_CHECKING Blocks

Added comprehensive `TYPE_CHECKING` blocks to all three modules:
- `codeweaver.core.__init__.py`
- `codeweaver.config.__init__.py`
- `codeweaver.common.__init__.py`

Each block imports all exported types/functions from their respective submodules.

### 2. Fixed __all__ / _dynamic_imports Discrepancies

- **codeweaver.config**: Removed `FileFilterSettings` from `__all__` (doesn't exist, only `FileFilterSettingsDict`)
- **codeweaver.core**: Added `DeserializationKwargs` to `__all__` (was in `_dynamic_imports` but missing from `__all__`)

### 3. Created Validation Script

Created `scripts/utils/validate-lazy-imports.py` to:
- Check consistency between `__all__` and `_dynamic_imports`
- Verify TYPE_CHECKING blocks exist
- Validate import paths
- Catch future regressions

## LazyImport Class - Recommendations

The `LazyImport` class (in `codeweaver.common.utils.lazy_importer`) is a different beast - it's for direct use by developers, not for the `__init__.py` pattern.

### Current State

✅ **Good as is** - The LazyImport class works well for its intended purpose (runtime lazy loading).

### IDE Support for LazyImport Users

The recommended pattern for users who want IDE support with LazyImport is documented in the class:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codeweaver.config import CodeWeaverSettings
else:
    CodeWeaverSettings = lazy_import("codeweaver.config", "CodeWeaverSettings")

# Now IDE knows the type, but import is still lazy at runtime
config: CodeWeaverSettings = CodeWeaverSettings()
```

### Why Not Change LazyImport?

LazyImport is a dynamic proxy pattern. Possible "improvements" like type stubs or enhanced generics would either:
1. Require significant maintenance burden (type stubs)
2. Not actually improve IDE support (generics still resolve to `Any`)
3. Defeat the purpose of lazy loading (`__dir__` would trigger resolution)

The TYPE_CHECKING pattern is the idiomatic Python solution used throughout the ecosystem.

## Testing & Validation

### Manual Testing

```bash
# Run validation script
python scripts/utils/validate-lazy-imports.py

# Test imports work at runtime
python -c "
from codeweaver.core import BasedModel
from codeweaver.config import CodeWeaverSettings  
from codeweaver.common import lazy_import
print('✓ All imports successful')
"
```

### IDE Testing

Open a Python file in your IDE and try:

```python
from codeweaver.core import BasedModel
from codeweaver.config import CodeWeaverSettings

# IDE should now provide:
# - Autocomplete for BasedModel and CodeWeaverSettings
# - Type hints
# - Go-to-definition
# - Signature help
```

## Comparison: Before vs After

### Before (No TYPE_CHECKING)

```python
# codeweaver/core/__init__.py
from importlib import import_module

_dynamic_imports = {
    'BasedModel': (__spec__.parent, 'types'),
}

def __getattr__(name: str):
    # ...lazy import logic...
```

**Result**: 
- ❌ IDE can't see `BasedModel` type
- ❌ No autocomplete
- ❌ No go-to-definition
- ✅ Lazy loading works at runtime

### After (With TYPE_CHECKING)

```python
# codeweaver/core/__init__.py
from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codeweaver.core.types import BasedModel

_dynamic_imports = {
    'BasedModel': (__spec__.parent, 'types'),
}

def __getattr__(name: str):
    # ...lazy import logic...
```

**Result**:
- ✅ IDE sees `BasedModel` type from TYPE_CHECKING block
- ✅ Full autocomplete
- ✅ Go-to-definition works
- ✅ Lazy loading still works at runtime (TYPE_CHECKING block never executes)

## Best Practices

### For Package __init__.py Modules

1. **Always use TYPE_CHECKING blocks** with real imports for IDE support
2. **Keep __all__ and _dynamic_imports in sync** 
3. **Run validation script** after making changes
4. **Import from actual modules** in TYPE_CHECKING, not re-exported paths

### For Direct LazyImport Usage

1. **Use TYPE_CHECKING pattern** when you need IDE support:
   ```python
   if TYPE_CHECKING:
       from actual.module import RealType
   else:
       RealType = lazy_import("actual.module", "RealType")
   ```

2. **Skip TYPE_CHECKING** if you don't need IDE support (simple scripts, etc.)

## Related Patterns

This investigation revealed the standard Python pattern for providing IDE support with lazy/dynamic imports:

1. **PEP 562** (`__getattr__` at module level) - Enables dynamic attribute access
2. **PEP 484** (TYPE_CHECKING) - Enables static type checking without runtime cost
3. **Combination** - Best of both worlds

This pattern is used by:
- Pydantic
- Pandas
- NumPy (partial)
- FastAPI (via Pydantic)
- Many other major libraries

## Conclusion

The lazy import pattern now works correctly in CodeWeaver:

✅ **Runtime**: Lazy loading via `__getattr__` - no eager imports, no circular import issues
✅ **IDE/Type Checking**: Full support via TYPE_CHECKING blocks - autocomplete, type hints, go-to-definition
✅ **Validation**: Automated checks via validation script
✅ **Documentation**: Pattern documented and explained

The pattern matches industry standards (Pydantic) and provides the best developer experience.
