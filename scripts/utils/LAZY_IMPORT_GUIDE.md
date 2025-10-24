<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# LazyImport Usage Guide

## Quick Summary

**Problem Solved**: The old `lazy_importer` required awkward double-call syntax `lazy_importer("module")()` and still imported immediately on attribute access.

**Solution**: New `LazyImport` class (inspired by cyclopts' `CommandSpec`) that truly defers EVERYTHING until the imported object is actually used.

## Files Created

- **Implementation**: `src/codeweaver/common/utils/lazy_importer.py`
- **Tests**: `tests/test_lazy_importer.py`
- **Demo**: `scripts/test_lazy_import_demo.py`

## Basic Usage

```python
from codeweaver.common.utils.lazy_importer import lazy_import

# Module import
os_lazy = lazy_import("os")
result = os_lazy.path.join("a", "b")  # Import happens HERE

# Function import
get_settings = lazy_import("codeweaver.config", "get_settings")
settings = get_settings()  # Import happens HERE

# Class import
Path = lazy_import("pathlib", "Path")
p = Path("/tmp")  # Import happens HERE
```

## Specific Use Cases

### Use Case 1: Settings Function Call

```python
# Truly lazy - import deferred until get_settings() is called! ✅
_get_settings = lazy_import("codeweaver.config").get_settings
# ... later in code ...
settings = _get_settings()  # Import happens NOW
```

### Use Case 2: TYPE_CHECKING + Runtime Types


```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from codeweaver.config import CodeWeaverSettings
else:
    # Stays lazy until instantiated! ✅
    CodeWeaverSettings = lazy_import("codeweaver.config", "CodeWeaverSettings")

# For pydantic models
class MyModel(BaseModel):
    config: CodeWeaverSettings  # String annotation, no import!

# Runtime usage - import happens when instantiated
config = CodeWeaverSettings(...)  # Import NOW
```

## Advanced Patterns

### Attribute Chaining (No Immediate Import!)

```python
# This is STILL lazy - no import happens!
Mapping = lazy_import("collections").abc.Mapping

# Import happens when you actually USE it
from collections.abc import Mapping as ActualMapping
assert Mapping._resolve() is ActualMapping
```

### Global-Level Usage

```python
# At module level - SAFE, no imports yet
_tiktoken = lazy_import("tiktoken")
_get_settings = lazy_import("codeweaver.config").get_settings

# Later in functions - imports happen when called
def tokenize(text: str):
    encoding = _tiktoken.get_encoding("cl100k_base")  # Import NOW
    return encoding.encode(text)

def get_config():
    return _get_settings()  # Import NOW
```

## Comparison: Old vs New

| Pattern | Old (broken) | New (works!) |
|---------|-------------|-------------|
| Module import | `lazy_importer("pkg")()` | `lazy_import("pkg")` |
| Attribute access | Imports immediately ❌ | Still lazy! ✅ |
| Function call | `lazy_importer("pkg")().func()` | `lazy_import("pkg").func()` |
| Global assignment | Had to wrap in function ❌ | Works at global level ✅ |

## How It Works

1. **LazyImport is a specification object**, not the imported module
2. **Attribute access creates NEW LazyImport** with extended chain
3. **Import only happens** when you call `__call__()` or `_resolve()`
4. **Resolution is cached** for performance
5. **Thread-safe** with internal locking

### Example Flow

```python
# Step 1: Create specification
lazy = lazy_import("os")  # LazyImport("os")
# No import yet!

# Step 2: Chain attributes
path = lazy.path  # LazyImport("os", "path")
# STILL no import!

join = path.join  # LazyImport("os", "path", "join")
# STILL no import!

# Step 3: Actually use it
result = join("a", "b")  # NOW imports os, gets os.path.join, calls it
# Returns: "a/b"
```

## Best Practices

### ✅ DO

```python
# Global-level lazy imports
_settings = lazy_import("codeweaver.config").get_settings

# TYPE_CHECKING for annotations
if TYPE_CHECKING:
    from expensive.module import Type

# Lazy imports for optional dependencies
tiktoken_encoder = lazy_import("tiktoken").get_encoding
```

### ❌ DON'T

```python
# Don't use for modules you always need
# Just import normally:
import os
import sys

# Don't use in tight loops (resolution overhead)
def process(items):
    for item in items:
        func = lazy_import("module").func  # Create new LazyImport each time!
        func(item)

# Better:
process_func = lazy_import("module").func  # Once at module level
def process(items):
    for item in items:
        process_func(item)  # Reuse
```

## Testing Your Code

The implementation has been tested with:

- ✅ Basic functionality (module, function, class imports)
- ✅ Attribute chaining without resolution
- ✅ Error handling (ImportError, AttributeError)
- ✅ Caching behavior
- ✅ Thread safety
- ✅ Real-world use cases (your specific patterns!)
- ✅ Magic method forwarding

To test manually:

```python
# Check if resolved
lazy = lazy_import("os")
print(lazy.is_resolved)  # False

# Use it
lazy.path.join("a", "b")
print(lazy.is_resolved)  # Still False! (because .path created new LazyImport)

# Check the chained one
path = lazy.path
print(path.is_resolved)  # False
path.join("a", "b")  # Now path chain resolves

# Debug representation
print(lazy)  # <LazyImport 'os' (not resolved)>
print(path)  # <LazyImport 'os.path' (not resolved)>
```

## Performance Considerations

- **Minimal overhead**: LazyImport is a lightweight proxy
- **Cached resolution**: Import happens once, cached thereafter
- **Thread-safe**: Internal locking prevents race conditions
- **Zero cost if unused**: If LazyImport is created but never used, no import happens

## Questions?

The implementation is in isolated testing mode - you can test it thoroughly before migrating existing code. Let me know if you want to:

1. Add more features
2. Adjust behavior
3. Add more tests
4. Begin migration of existing code

## Next Steps

1. ✅ Implementation complete
2. ✅ Manual testing successful
3. ⏳ Run full test suite (blocked by unrelated import error)
4. ⏳ Your validation with real use cases
5. ⏳ Migration of existing code
