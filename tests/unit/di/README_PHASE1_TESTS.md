<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Phase 1 Container Tests Documentation

## Overview

This document provides detailed information about the Phase 1 container test suite in `test_container_phase1.py`.

## Test File Structure

```
test_container_phase1.py (900+ lines)
├── Imports and Setup
├── Test Fixtures (15 helper classes)
│   ├── Service Classes (ServiceA, ServiceB, ServiceC)
│   ├── Circular Dependency Classes
│   ├── Generator Factories
│   ├── Counter Service
│   └── Union Type Implementations
└── Test Sections (6 main sections, 38 tests)
    ├── 1. Circular Dependency Detection (4 tests)
    ├── 2. Generator Dependencies (6 tests)
    ├── 3. Scope Lifecycle (6 tests)
    ├── 4. Error Aggregation (4 tests)
    ├── 5. Union Type Resolution (7 tests)
    ├── 6. use_cache Flag (6 tests)
    └── 7. Edge Cases and Integration (4 tests)
```

## Test Fixtures Reference

### Basic Service Classes

```python
class ServiceA:
    """Simple service for dependency injection testing"""
    def __init__(self, value: str = "A")

class ServiceB:
    """Service that depends on ServiceA"""
    def __init__(self, service_a: Annotated[ServiceA, Depends()])

class ServiceC:
    """Service that depends on ServiceB"""
    def __init__(self, service_b: Annotated[ServiceB, Depends()])
```

### Circular Dependency Classes

```python
class CircularServiceA:
    """A → B circular dependency"""
    def __init__(self, service_b: Annotated[CircularServiceB, Depends()])

class CircularServiceB:
    """B → A circular dependency"""
    def __init__(self, service_a: Annotated[CircularServiceA, Depends()])
```

### Generator Factories

```python
async def async_generator_factory() -> AsyncIterator[ServiceA]:
    """Async generator with cleanup tracking"""
    service = ServiceA("async_gen")
    service.cleanup_called = False
    try:
        yield service
    finally:
        service.cleanup_called = True

def sync_generator_factory() -> Iterator[ServiceA]:
    """Sync generator with cleanup tracking"""
    service = ServiceA("sync_gen")
    service.cleanup_called = False
    try:
        yield service
    finally:
        service.cleanup_called = True
```

### Counter Service

```python
class CounterService:
    """Tracks instantiation count for caching tests"""
    instance_count = 0  # Class variable

    def __init__(self):
        CounterService.instance_count += 1
        self.instance_id = CounterService.instance_count

    @classmethod
    def reset(cls):
        cls.instance_count = 0
```

**Usage Pattern:**
```python
CounterService.reset()  # Always reset before use
container.register(CounterService)
s1 = await container.resolve(CounterService)
s2 = await container.resolve(CounterService)
assert CounterService.instance_count == 1  # Singleton
assert s1 is s2
```

### Union Type Implementations

```python
class ImplementationX:
    """First union type option"""
    def __init__(self):
        self.name = "X"

class ImplementationY:
    """Second union type option"""
    def __init__(self):
        self.name = "Y"
```

## Test Patterns and Best Practices

### Pattern 1: Basic Container Test

```python
@pytest.mark.asyncio
async def test_basic_feature():
    """Test description."""
    # Setup
    container = Container()
    container.register(ServiceA)

    # Execute
    service = await container.resolve(ServiceA)

    # Assert
    assert isinstance(service, ServiceA)
```

### Pattern 2: Error Testing

```python
@pytest.mark.asyncio
async def test_error_condition():
    """Test that error is raised correctly."""
    container = Container()
    container.register(CircularServiceA)
    container.register(CircularServiceB)

    with pytest.raises(CircularDependencyError) as exc_info:
        await container.resolve(CircularServiceA)

    # Verify error details
    assert "CircularServiceA" in exc_info.value.cycle
```

### Pattern 3: Lifecycle Testing

```python
@pytest.mark.asyncio
async def test_with_lifespan():
    """Test lifecycle with cleanup."""
    container = Container()

    async with container.lifespan():
        # Setup within lifespan
        container.register(ServiceA, async_generator_factory)
        service = await container.resolve(ServiceA)

        # Use service
        assert service.cleanup_called is False

    # After lifespan - verify cleanup
    assert service.cleanup_called is True
```

### Pattern 4: Caching Tests

```python
@pytest.mark.asyncio
async def test_caching_behavior():
    """Test caching with CounterService."""
    CounterService.reset()  # CRITICAL: Always reset
    container = Container()
    container.register(CounterService, singleton=True)

    s1 = await container.resolve(CounterService)
    s2 = await container.resolve(CounterService)

    assert s1 is s2
    assert CounterService.instance_count == 1
```

## Common Test Scenarios

### Testing Circular Dependencies

**Goal:** Verify circular dependency detection and error messages

**Setup:**
1. Create circular dependency classes (A depends on B, B depends on A)
2. Register both with container
3. Attempt to resolve

**Verification:**
- `CircularDependencyError` is raised
- Cycle string contains both class names
- Error message is descriptive

### Testing Generator Cleanup

**Goal:** Verify generators are properly cleaned up via AsyncExitStack

**Setup:**
1. Create generator factory with cleanup tracking
2. Use within `async with container.lifespan()` context
3. Resolve dependency

**Verification:**
- Service is yielded correctly
- `cleanup_called` is False while in context
- `cleanup_called` is True after context exits

### Testing Scopes

**Goal:** Verify singleton/request/function scope behavior

**Setup:**
1. Use `CounterService` to track instantiations
2. Register with specific scope or use `Depends(scope=...)`
3. Resolve multiple times

**Verification:**
- **Singleton**: Same instance, count = 1
- **Request**: Same within request, different after `clear_request_cache()`
- **Function**: New instance each time, count = number of resolves

### Testing Error Aggregation

**Goal:** Verify `collect_errors=True` aggregates multiple errors

**Setup:**
1. Create service with multiple failing dependencies
2. Call `_call_with_injection(collect_errors=True)`

**Verification:**
- Returns `ResolutionResult` (not exception)
- `result.errors` contains all errors
- `result.values` contains successful dependencies

### Testing Union Types

**Goal:** Verify Union[X, Y] resolution logic

**Setup:**
1. Register one or both union member types
2. Resolve Union type

**Verification:**
- First registered/resolvable type wins
- `None` types are skipped
- Raises ValueError if no type can be resolved

## Debugging Failed Tests

### CounterService.instance_count is wrong

**Problem:** Test fails because instance count doesn't match expected

**Solution:**
```python
# Always reset before use
CounterService.reset()
```

### cleanup_called is False after lifespan

**Problem:** Generator cleanup not called

**Check:**
1. Is generator registered with container?
2. Is resolution happening within `async with container.lifespan():`?
3. Is the generator using `try/finally` pattern?

### CircularDependencyError not raised

**Problem:** Expected circular dependency not detected

**Check:**
1. Are both services registered?
2. Do they actually form a cycle?
3. Is `resolve()` being called (not just registration)?

### ResolutionResult not returned

**Problem:** Expected `ResolutionResult` but got exception or instance

**Check:**
1. Using `_call_with_injection(collect_errors=True)`?
2. Is there actually an error to collect?
3. If no errors, instance is returned (not `ResolutionResult`)

## Test Isolation

Each test:
- Creates its own `Container()` instance
- Resets `CounterService.instance_count` when needed
- Does not share state with other tests
- Uses `@pytest.mark.asyncio` for async tests

## Performance Considerations

### Test Execution Time

- Fast tests: < 10ms (basic resolution, caching)
- Medium tests: 10-50ms (circular detection, error aggregation)
- Slow tests: 50-100ms (multiple generators, integration tests)

### Optimization Tips

1. **Minimize generator tests**: Lifespan contexts add overhead
2. **Batch similar tests**: Group tests by feature to improve cache locality
3. **Use simple fixtures**: Complex fixtures slow down test setup
4. **Avoid nested containers**: Creates additional overhead

## Adding New Tests

### Checklist for New Tests

- [ ] Add `@pytest.mark.asyncio` for async tests
- [ ] Use descriptive test name starting with `test_`
- [ ] Include docstring explaining what is tested
- [ ] Reset `CounterService` if using it
- [ ] Create fresh `Container()` instance
- [ ] Use appropriate assertions (2-5 per test)
- [ ] Test both success and failure paths
- [ ] Add to appropriate section in file
- [ ] Update this README if adding new fixture

### Example Template

```python
@pytest.mark.asyncio
async def test_new_feature():
    """Test [feature] does [expected behavior].

    This test verifies that [specific aspect] works correctly
    when [specific condition].
    """
    # Setup
    container = Container()
    container.register(ServiceA)

    # Execute
    result = await container.resolve(ServiceA)

    # Assert
    assert isinstance(result, ServiceA)
    assert result.value == "expected"
```

## Related Files

- **Implementation**: `/src/codeweaver/di/container.py`
- **Exceptions**: `/src/codeweaver/core/exceptions.py`
- **Depends Marker**: `/src/codeweaver/di/depends.py`
- **Existing Tests**: `/tests/unit/di/test_container.py`
- **Test Summary**: `/claudedocs/PHASE1_TESTS_SUMMARY.md`
