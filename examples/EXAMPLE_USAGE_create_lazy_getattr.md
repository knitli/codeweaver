<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Using `create_lazy_getattr()` - Consolidating Package `__getattr__`

## Problem
Every package `__init__.py` duplicates the same `__getattr__` logic with minor variations, making it hard to maintain consistency.

## Solution
Use `create_lazy_getattr()` from `codeweaver.common.utils` to generate the function once.

## Before (Current Pattern)

```python
# src/codeweaver/tokenizers/__init__.py
from importlib import import_module
from types import MappingProxyType

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "Tokenizer": (__spec__.parent, "base"),
    "TiktokenTokenizer": (__spec__.parent, "tiktoken"),
    "Tokenizers": (__spec__.parent, "tokenizers"),
})

def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the tokenizer package."""
    if name in _dynamic_imports:
        module_name, submodule_name = _dynamic_imports[name]
        module = import_module(f"{module_name}.{submodule_name}")
        result = getattr(module, name)
        globals()[name] = result  # Cache in globals for future access
        return result
    if globals().get(name) is not None:
        return globals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")

__all__ = ("TiktokenTokenizer", "Tokenizer", "Tokenizers", "get_tokenizer")
```

## After (Using Helper)

```python
# src/codeweaver/tokenizers/__init__.py
from types import MappingProxyType
from codeweaver.common.utils import create_lazy_getattr

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "Tokenizer": (__spec__.parent, "base"),
    "TiktokenTokenizer": (__spec__.parent, "tiktoken"),
    "Tokenizers": (__spec__.parent, "tokenizers"),
})

# Single line replaces entire __getattr__ definition!
__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = ("TiktokenTokenizer", "Tokenizer", "Tokenizers", "get_tokenizer")
```

## Benefits

1. **Consistency** - All packages use identical import logic
2. **Maintainability** - Bug fixes in one place benefit all packages
3. **Brevity** - Reduces ~13 lines to 1 line per package
4. **Clarity** - Intent is obvious from single function call
5. **Type Safety** - Same typing behavior everywhere

## Migration

Each package can be migrated independently:

```python
# 1. Add import
from codeweaver.common.utils import create_lazy_getattr

# 2. Replace __getattr__ function with single line
__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

# 3. Remove the old __getattr__ function definition
# 4. Remove `from importlib import import_module` if no longer needed
```

## Validation

The validator script will continue to work unchanged - it tests the behavior, not the implementation.
