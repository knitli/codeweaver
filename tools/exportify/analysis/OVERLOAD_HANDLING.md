# @overload Decorator Handling

## Overview

The AST parser now properly handles Python's `@overload` decorator to avoid treating overloaded function signatures as duplicate exports.

## Problem Statement

**Before**: Functions with `@overload` decorator were extracted as separate exports:
```python
from typing import overload

@overload
def process(x: int) -> int: ...

@overload
def process(x: str) -> str: ...

def process(x: int | str) -> int | str:
    return x
```

Would result in **3 separate exports** named "process", which:
- Caused duplication warnings
- Could be filtered out by deduplication logic
- Lost the important overload information

**After**: All overload signatures + implementation are treated as **ONE export** with metadata.

## Implementation

### New Module: `ast_parser_overload.py`

Two key functions:
1. `is_overloaded_function(node)` - Detects `@overload` decorator
2. `group_functions_by_name(tree)` - Groups all definitions of same function

### Detection Logic

Handles both import styles:
- `@overload` (direct import from typing)
- `@typing.overload` (module prefix)

### Metadata Added

For overloaded functions, `ParsedSymbol.metadata` contains:
```python
{
    "is_defined_here": True,
    "is_aliased": False,
    "is_overloaded": True,          # NEW
    "overload_count": 2,              # NEW - number of @overload signatures
    "has_implementation": True,       # NEW - whether non-@overload definition exists
}
```

For regular functions:
```python
{
    "is_defined_here": True,
    "is_aliased": False,
    "is_overloaded": False,           # Default
    "overload_count": 0,              # Default
    "has_implementation": True,       # Always True for non-overloaded
}
```

## Behavior Changes

### Function Grouping

**Old behavior**:
```python
# Input: 3 function definitions with name "process"
# Output: 3 separate ParsedSymbol objects

symbols = [
    ParsedSymbol(name="process", ...),  # First @overload
    ParsedSymbol(name="process", ...),  # Second @overload
    ParsedSymbol(name="process", ...),  # Implementation
]
```

**New behavior**:
```python
# Input: 3 function definitions with name "process"
# Output: 1 ParsedSymbol object with metadata

symbols = [
    ParsedSymbol(
        name="process",
        metadata={
            "is_overloaded": True,
            "overload_count": 2,
            "has_implementation": True,
        }
    )
]
```

### Docstring Extraction

Docstring is taken from:
1. Implementation (if exists) - preferred
2. First @overload signature (if no implementation)

### Line Number

Line number comes from the **first definition** (first @overload or regular function).

### Duplicate Detection Warning

Functions with multiple definitions but **without** `@overload` trigger a warning:
```python
def func():
    pass

def func():  # Duplicate without @overload
    pass

# Warning: "Function 'func' defined 2 times without @overload decorator"
```

## Edge Cases Handled

1. **Single @overload with implementation**
   - `overload_count=1`, `has_implementation=True`

2. **Only @overload, no implementation**
   - `has_implementation=False`
   - May indicate incomplete stub file

3. **Many overloads (5+)**
   - No limit, all counted correctly

4. **Async overloads**
   - Works with `async def` functions

5. **Mixed files**
   - Overloaded and regular functions coexist correctly

## Real-World Usage

### In CodeWeaver

Overloaded functions found:
- `kind_from_delimiter_tuple` - 2 overloads in `engine/chunker/delimiters/patterns.py`
- `_setup_server` - 2 overloads in `server/mcp/server.py`
- `_time_operation` - 6+ overloads in `server/mcp/middleware/statistics.py`
- `__init__` methods in various classes

### Export Behavior

```python
# File: patterns.py
__all__ = [
    "kind_from_delimiter_tuple",  # Appears ONCE
    # ... other exports
]

_dynamic_imports = {
    "kind_from_delimiter_tuple": ("codeweaver.engine.chunker.delimiters.patterns", "kind_from_delimiter_tuple"),
    # Single entry, not tripled
}
```

## Testing

Comprehensive test suite in `test_overload_handling.py`:
- 12 test cases covering all scenarios
- All tests passing ✅
- No regressions in existing tests ✅

### Test Coverage

1. **Basic Detection**
   - `@overload` decorator detection
   - `@typing.overload` prefix handling
   - Async function overloads

2. **Edge Cases**
   - Single overload
   - Many overloads (5+)
   - Overloads without implementation
   - Mixed overloaded and regular functions

3. **Metadata**
   - Correct overload counts
   - Implementation detection
   - Docstring from implementation

4. **Warnings**
   - Duplicate functions without @overload

5. **Real Files**
   - Tested with actual CodeWeaver files
   - Verified correct export counts

## Benefits

1. **Type Safety** - Preserves overload signatures for type checkers
2. **IDE Support** - IDEs show all overload signatures
3. **No Duplicates** - One export per function name
4. **Clear Metadata** - Explicit overload information
5. **Warning System** - Detects suspicious duplicate definitions

## Future Enhancements

Potential improvements (not currently needed):
1. Preserve all overload signatures in TYPE_CHECKING blocks
2. Validate overload signature compatibility
3. Check for implementation matching overload signatures
4. Generate stub files with complete overload information
