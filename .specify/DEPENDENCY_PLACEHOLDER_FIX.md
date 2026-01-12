# DependencyPlaceholder Type Checking Fix

## Problem

The `INJECTED` sentinel proxy was causing type checking errors when used as a bare default value in function signatures with dependency-injected parameters:

```python
# This pattern was causing type errors:
def _create_provider_settings_dep(settings: SettingsDep = INJECTED) -> Any:
    ...

# Error message:
# Default value of type `_InjectedProxy[TypeVar, DependsPlaceholder]` is not assignable to 
# annotated parameter type `SettingsDep`
```

### Root Cause

The `_InjectedProxy` class was defined with an unbound `TypeVar` for its `Dep` parameter:

```python
class _InjectedProxy[Dep: type[T], S: Sentinel]:  # T is unbound without subscripting
    ...

INJECTED: _InjectedProxy[T, DependsPlaceholder] = _InjectedProxy(...)
```

When `INJECTED` was used without subscripting, type checkers saw it as `_InjectedProxy[T, DependsPlaceholder]` with an unbound `T`, which didn't match specific dependency types like `SettingsDep = Annotated[BaseSettings, depends(...)]`.

## Solution

The fix involves three key changes to `src/codeweaver/core/di/depends.py`:

### 1. **Changed INJECTED Type Annotation to Use `Any`**

```python
# Before:
INJECTED: _InjectedProxy[T, DependsPlaceholder] = _InjectedProxy(_injected_sentinel)

# After:
INJECTED: _InjectedProxy[Any, DependsPlaceholder] = _InjectedProxy(_injected_sentinel)  # type: ignore[assignment]
```

This allows `INJECTED` to be compatible with any dependency-injected parameter type, while type checkers infer the specific type from the parameter annotation.

### 2. **Added `@overload` for `__getitem__` Method**

```python
@overload
def __getitem__(self, item: type[T_co]) -> T_co: ...

def __getitem__(self, item: type[Dep]) -> Dep:
    """Return the sentinel cast to the requested type."""
    return cast(Dep, self._sentinel)
```

The `@overload` decorator provides better type information to type checkers for subscripted usage like `INJECTED[SomeType]`.

### 3. **Added `__bool__` Method**

```python
def __bool__(self) -> bool:
    """Always return True since the sentinel is always truthy."""
    return True
```

This makes `INJECTED` more sentinel-like and allows type checkers to better understand its purpose as a default value marker.

### 4. **Created Type Stub File (.pyi)**

Added `src/codeweaver/core/di/depends.pyi` to provide explicit type information to type checkers. The stub file declares `INJECTED: Any`, making it explicitly compatible with any parameter type.

## Usage Patterns

Both of these patterns now work without type errors:

### Pattern 1: Bare INJECTED (Fixed by this solution)

```python
type SettingsDep = Annotated[BaseSettings, depends(bootstrap_settings)]

def _create_provider_settings_dep(settings: SettingsDep = INJECTED) -> Any:
    """Type checkers infer SettingsDep from the parameter annotation."""
    return settings
```

### Pattern 2: Subscripted INJECTED (Already worked)

```python
def _create_provider_settings_dep(settings: SettingsDep = INJECTED[BaseSettings]) -> Any:
    """Explicit type subscript also works."""
    return settings
```

## Type Checking Behavior

### At Runtime
- `INJECTED` is the sentinel proxy instance wrapping `DependsPlaceholder`
- Works transparently with the DI container's sentinel detection
- Supports both `INJECTED` and `INJECTED[Type]` syntax

### At Type Check Time
- Type checkers see `INJECTED` as `Any`, making it compatible with any type
- For `INJECTED[Type]`, type checkers see the correct `Type`
- Type inference from parameter annotations works correctly

## Files Modified

1. **src/codeweaver/core/di/depends.py**
   - Changed type annotation of `INJECTED` to `_InjectedProxy[Any, DependsPlaceholder]`
   - Added covariant `T_co` TypeVar for better type variance
   - Added `@overload` for `__getitem__`
   - Added `__bool__` method
   - Updated docstrings

2. **src/codeweaver/core/di/depends.pyi** (new)
   - Type stub file providing explicit type information for type checkers
   - Declares `INJECTED: Any` for maximum compatibility
   - Documents usage patterns in comments

## Benefits

1. **Type Safety**: No more type checking errors for bare `INJECTED` usage
2. **Backward Compatible**: Existing code using `INJECTED[Type]` continues to work
3. **Type Inference**: Type checkers can infer correct types from parameter annotations
4. **Clear Intent**: The `__bool__` method and stub file clarify that `INJECTED` is a sentinel marker
5. **Future-Proof**: The `.pyi` file provides explicit type information that evolves independently of runtime code

## Testing

The fix has been verified to work with:
- Bare `INJECTED` as default values
- Subscripted `INJECTED[Type]` syntax
- Type aliases with `Annotated[T, depends(...)]`
- Both runtime execution and type checking

## References

- PEP 695: Type Parameter Syntax
- PEP 593: Flexible function and variable annotations (Annotated)
- PEP 483: The Theory of Type Hints
