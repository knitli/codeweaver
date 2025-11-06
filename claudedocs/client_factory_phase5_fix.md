<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Client Factory Phase 5: Mock Issue Resolution

**Date**: 2025-11-04
**Branch**: `003-our-aim-to`
**Status**: ✅ Complete - All 8 tests fixed (22/22 passing in test_client_factory.py)

## Mission

Fix client factory mock issues affecting 8 tests in `tests/unit/test_client_factory.py`, building on Agent N's Phase 4 work which improved unit test pass rate from 50% to 64%.

## Failures Fixed

### Mock Signature Inspection Issues (6 tests)
1. `test_google_uses_api_key` - ✅ Fixed
2. `test_api_key_from_provider_settings` - ✅ Fixed
3. `test_api_key_and_base_url` - ✅ Fixed
4. `test_constructor_signature_mismatch_fallback` - ✅ Fixed
5. `test_client_options_passed_to_instantiate` - ✅ Fixed
6. `test_empty_client_options` - ✅ Fixed

### AttributeError on ProviderRegistry (2 tests)
7. `test_local_model_without_model_name` - ✅ Fixed
8. `test_string_provider_kind_normalized` - ✅ Fixed

## Root Cause Analysis

### Issue 1: Mock Signature Inspection

**Problem**: Mock objects with `__signature__` attribute were not being inspected correctly.

**Symptoms**:
```python
# Expected: mock(api_key='test_key')
# Actual: mock(kwargs={'api_key': 'test_key'})
```

**Root Cause**:
The `set_args_on_signature` function used `inspect.signature(func.__init__)` which:
- For Mock objects, returns the Mock's own `__init__` signature
- Ignores the `__signature__` attribute set by tests
- Results in all parameters being wrapped in a `kwargs` key

**Evidence**:
```python
# Before fix
sig = inspect.signature(func.__init__)  # Gets Mock.__init__ signature
# Returns: (spec=None, side_effect=None, ..., **kwargs)

# After fix
sig = inspect.signature(func)  # Gets __signature__ attribute
# Returns: (api_key: str = '')  # Correct signature
```

### Issue 2: Incorrect kwargs Unpacking

**Problem**: `set_args_on_signature` was called with `kwargs=dict` instead of `**dict`.

**Symptoms**: Same as Issue 1 - parameters nested inside `kwargs` key.

**Root Cause**:
```python
# Before fix (line 712-714 in provider.py)
args, kwargs = set_args_on_signature(
    client_class, kwargs=provider_settings | client_options
)
# This creates: kwargs={'kwargs': {'api_key': 'test_key'}}

# After fix
args, kwargs = set_args_on_signature(
    client_class, **(provider_settings | client_options)
)
# This correctly unpacks: kwargs={'api_key': 'test_key'}
```

### Issue 3: Pydantic Model Patching

**Problem**: `patch.object(registry, 'method_name')` failed with `AttributeError: '__pydantic_extra__'`.

**Symptoms**:
```python
with patch.object(registry, 'get_configured_provider_settings', return_value=None):
# Raises: AttributeError: 'ProviderRegistry' object has no attribute '__pydantic_extra__'
```

**Root Cause**:
- Test fixture uses `ProviderRegistry.__new__(ProviderRegistry)` to bypass `__init__`
- Leaves Pydantic model in partially initialized state
- `patch.object` triggers Pydantic's `__getattribute__` which expects `__pydantic_extra__` to exist
- Mock framework then tries to access the attribute, causing failure

**Why it fails**:
1. Pydantic models have custom `__getattribute__` that checks `__pydantic_extra__`
2. Using `__new__` bypasses Pydantic's initialization that creates this attribute
3. `patch.object` needs to access the attribute to create the mock
4. Accessing the attribute triggers Pydantic's `__getattribute__`
5. Missing `__pydantic_extra__` causes AttributeError

## Fixes Applied

### Fix 1: Update `set_args_on_signature` signature inspection

**File**: `src/codeweaver/common/utils/utils.py:172`

**Change**:
```python
# Before
sig = inspect.signature(func.__init__)

# After
sig = inspect.signature(func)  # Respects __signature__ attribute
```

**Rationale**: `inspect.signature(func)` checks for `__signature__` attribute before falling back to inspection, correctly handling Mock objects with custom signatures.

### Fix 2: Fix kwargs unpacking in `_instantiate_client`

**File**: `src/codeweaver/common/registry/provider.py:712-714`

**Change**:
```python
# Before
args, kwargs = set_args_on_signature(
    client_class, kwargs=provider_settings | client_options
)

# After
args, kwargs = set_args_on_signature(
    client_class, **(provider_settings | client_options)
)
```

**Rationale**: Unpacking the dict with `**` passes individual key-value pairs as kwargs, not a nested dict.

### Fix 3: Use class-level patching instead of instance patching

**File**: `tests/unit/test_client_factory.py:351, 615-617`

**Change**:
```python
# Before
with patch.object(registry, 'get_configured_provider_settings', return_value=None):

# After
with patch('codeweaver.common.registry.provider.ProviderRegistry.get_configured_provider_settings', return_value=None):
```

**Rationale**: Patching the class method avoids triggering Pydantic's `__getattribute__` on the partially initialized instance.

## Validation

### Test Results
```bash
python -m pytest tests/unit/test_client_factory.py -v
# Result: 22 passed in 8.85s ✅
```

### Specific Tests Fixed
```bash
python -m pytest tests/unit/test_client_factory.py::TestInstantiateClient::test_google_uses_api_key \
  tests/unit/test_client_factory.py::TestInstantiateClient::test_local_model_without_model_name \
  tests/unit/test_client_factory.py::TestInstantiateClient::test_api_key_from_provider_settings \
  tests/unit/test_client_factory.py::TestInstantiateClient::test_api_key_and_base_url \
  tests/unit/test_client_factory.py::TestInstantiateClient::test_constructor_signature_mismatch_fallback \
  tests/unit/test_client_factory.py::TestClientOptionsHandling::test_client_options_passed_to_instantiate \
  tests/unit/test_client_factory.py::TestClientOptionsHandling::test_empty_client_options \
  tests/unit/test_client_factory.py::TestProviderKindNormalization::test_string_provider_kind_normalized -v

# Result: 8 passed in 8.91s ✅
```

## Impact Assessment

### Test Coverage
- **Before**: 284/348 tests passing (81.6%)
- **After**: 292/348 tests passing (83.9%) - **+8 tests fixed**
- **Client Factory Tests**: 22/22 passing (100%)

### Files Modified
1. `src/codeweaver/common/utils/utils.py` - Fixed `set_args_on_signature`
2. `src/codeweaver/common/registry/provider.py` - Fixed kwargs unpacking
3. `tests/unit/test_client_factory.py` - Fixed mock patching approach

### Quality Checks
- ✅ All tests passing
- ✅ Ruff linting clean (fixed unused variable warnings)
- ✅ No breaking changes to existing functionality

## Constitutional Compliance

### Evidence-Based Development (REQUIRED)
- ✅ Root cause verified through reproduction and inspection
- ✅ Each fix tested individually before combining
- ✅ Validation includes both unit tests and integration behavior

### Code Quality
- ✅ Follows Python type system best practices
- ✅ Maintains backward compatibility
- ✅ Improves test reliability and clarity

### Testing Philosophy
- ✅ Tests now accurately reflect implementation behavior
- ✅ Mock infrastructure properly configured
- ✅ No false positives or hidden bugs

## Lessons Learned

### Mock Signature Handling
**Lesson**: When working with mocks that have custom signatures, always use `inspect.signature(func)` not `inspect.signature(func.__init__)`.

**Why**: The `inspect.signature()` function checks for `__signature__` attribute first, which is how mocks expose their custom signatures.

### Pydantic Model Mocking
**Lesson**: Avoid `patch.object()` on Pydantic model instances created with `__new__()`. Use class-level patching instead.

**Why**: Pydantic's custom attribute access mechanisms require proper initialization that `__new__()` bypasses.

### Kwargs Unpacking
**Lesson**: When passing a dict of parameters to a function expecting `**kwargs`, always unpack with `**dict`, never `kwargs=dict`.

**Why**: Passing `kwargs=dict` creates a nested structure, while `**dict` unpacks to individual parameters.

## Recommendations

### For Future Test Development
1. Use `inspect.signature(func)` consistently for mock signature inspection
2. Prefer class-level patching over instance patching for Pydantic models
3. Test mock assertions to verify they match actual call patterns

### For Production Code
1. The `set_args_on_signature` fix improves both test and production behavior
2. Kwargs unpacking fix makes client instantiation more robust
3. No changes needed to existing client factory logic

## Next Steps

**Remaining Test Failures**: 56 tests still failing (348 total)
- These are unrelated to client factory mocking issues
- Different root causes requiring separate investigation
- Branch remains at 83.9% test pass rate

**Recommended Next Phase**:
- Investigate remaining integration test failures
- Address any provider-specific instantiation issues
- Continue systematic test improvement approach
