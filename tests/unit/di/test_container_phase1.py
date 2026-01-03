# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Comprehensive tests for Phase 1 container improvements.

Tests for:
1. Circular dependency detection
2. Generator dependencies (sync and async)
3. Scope lifecycle (singleton/request/function)
4. Error aggregation with collect_errors flag
5. Union type resolution
6. use_cache flag behavior
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Annotated, Union

import pytest

from codeweaver.core import INJECTED, Container, Depends, ResolutionResult
from codeweaver.core.exceptions import CircularDependencyError, DependencyInjectionError


# ===========================================================================
# *                    Test Fixtures and Helper Classes
# ===========================================================================


class ServiceA:
    """Simple service A."""

    def __init__(self, value: str = "A"):
        self.value = value


class ServiceB:
    """Service B that depends on A."""

    def __init__(self, service_a: Annotated[ServiceA, Depends()] = INJECTED[ServiceA]):
        self.service_a = service_a


class ServiceC:
    """Service C that depends on B."""

    def __init__(self, service_b: Annotated[ServiceB, Depends()] = INJECTED[ServiceB]):
        self.service_b = service_b


class CircularServiceA:
    """Service A in circular dependency: A -> B -> A."""

    def __init__(
        self, service_b: Annotated[CircularServiceB, Depends()] = INJECTED[CircularServiceB]
    ):
        self.service_b = service_b


class CircularServiceB:
    """Service B in circular dependency: B -> A -> B."""

    def __init__(
        self, service_a: Annotated[CircularServiceA, Depends()] = INJECTED[CircularServiceA]
    ):
        self.service_a = service_a


class CounterService:
    """Service that tracks instantiation count."""

    instance_count = 0

    def __init__(self):
        CounterService.instance_count += 1
        self.instance_id = CounterService.instance_count

    @classmethod
    def reset(cls):
        cls.instance_count = 0


# Generator dependencies
async def async_generator_factory() -> AsyncIterator[ServiceA]:
    """Async generator factory with cleanup tracking."""
    service = ServiceA("async_gen")
    service.cleanup_called = False  # type: ignore
    try:
        yield service
    finally:
        service.cleanup_called = True  # type: ignore


def sync_generator_factory() -> Iterator[ServiceA]:
    """Sync generator factory with cleanup tracking."""
    service = ServiceA("sync_gen")
    service.cleanup_called = False  # type: ignore
    try:
        yield service
    finally:
        service.cleanup_called = True  # type: ignore


# Union type test classes
class ImplementationX:
    """First union type implementation."""

    def __init__(self):
        self.name = "X"


class ImplementationY:
    """Second union type implementation."""

    def __init__(self):
        self.name = "Y"


# ===========================================================================
# *                    1. Circular Dependency Detection Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_circular_dependency_detected():
    """Test that circular dependencies are detected and raise CircularDependencyError."""
    container = Container()
    container.register(CircularServiceA)
    container.register(CircularServiceB)

    with pytest.raises(CircularDependencyError) as exc_info:
        await container.resolve(CircularServiceA)

    # Verify error contains cycle information
    assert "CircularServiceA" in exc_info.value.cycle
    assert "CircularServiceB" in exc_info.value.cycle
    assert "Circular dependency detected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_circular_dependency_with_three_services():
    """Test circular dependency detection with three services: A -> B -> C -> A."""

    class ServiceX:
        def __init__(self, service_z: Annotated[ServiceZ, Depends()] = INJECTED[ServiceZ]):
            self.service_z = service_z

    class ServiceY:
        def __init__(self, service_x: Annotated[ServiceX, Depends()] = INJECTED[ServiceX]):
            self.service_x = service_x

    class ServiceZ:
        def __init__(self, service_y: Annotated[ServiceY, Depends()] = INJECTED[ServiceY]):
            self.service_y = service_y

    container = Container()
    container.register(ServiceX)
    container.register(ServiceY)
    container.register(ServiceZ)

    with pytest.raises(CircularDependencyError) as exc_info:
        await container.resolve(ServiceX)

    # Verify all three services appear in the cycle
    cycle = exc_info.value.cycle
    assert "ServiceX" in cycle
    assert "ServiceY" in cycle
    assert "ServiceZ" in cycle


@pytest.mark.asyncio
async def test_no_false_positive_circular_detection():
    """Test that valid dependency chains don't trigger false circular detection."""
    container = Container()
    container.register(ServiceA)
    container.register(ServiceB)
    container.register(ServiceC)

    # Should resolve successfully without circular dependency error
    service_c = await container.resolve(ServiceC)
    assert isinstance(service_c, ServiceC)
    assert isinstance(service_c.service_b, ServiceB)
    assert isinstance(service_c.service_b.service_a, ServiceA)


@pytest.mark.asyncio
async def test_circular_dependency_in_override():
    """Test circular dependency detection works with overrides."""

    def circular_override() -> CircularServiceA:
        # This override itself has a circular dependency
        return CircularServiceA()

    container = Container()
    container.register(CircularServiceA)
    container.register(CircularServiceB)
    container.override(CircularServiceA, circular_override)

    with pytest.raises(CircularDependencyError):
        await container.resolve(CircularServiceA)


# ===========================================================================
# *                    2. Generator Dependencies Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_async_generator_with_cleanup():
    """Test async generator dependencies are properly cleaned up via AsyncExitStack."""
    container = Container()

    async with container.lifespan():
        # Register async generator factory
        container.register(ServiceA, async_generator_factory)

        # Resolve should return the yielded value
        service = await container.resolve(ServiceA)
        assert isinstance(service, ServiceA)
        assert service.value == "async_gen"
        assert hasattr(service, "cleanup_called")
        assert service.cleanup_called is False  # Not cleaned up yet

    # After lifespan exits, cleanup should have been called
    assert service.cleanup_called is True


@pytest.mark.asyncio
async def test_sync_generator_with_cleanup():
    """Test sync generator dependencies are wrapped and cleaned up properly."""
    container = Container()

    async with container.lifespan():
        # Register sync generator factory
        container.register(ServiceA, sync_generator_factory)

        # Resolve should return the yielded value
        service = await container.resolve(ServiceA)
        assert isinstance(service, ServiceA)
        assert service.value == "sync_gen"
        assert hasattr(service, "cleanup_called")
        assert service.cleanup_called is False  # Not cleaned up yet

    # After lifespan exits, cleanup should have been called
    assert service.cleanup_called is True


@pytest.mark.asyncio
async def test_multiple_generators_cleanup():
    """Test multiple generator dependencies are all cleaned up properly."""

    async def generator1() -> AsyncIterator[ServiceA]:
        service = ServiceA("gen1")
        service.cleanup_called = False  # type: ignore
        try:
            yield service
        finally:
            service.cleanup_called = True  # type: ignore

    def generator2() -> Iterator[ServiceB]:
        service = ServiceB(ServiceA("gen2_inner"))
        service.cleanup_called = False  # type: ignore
        try:
            yield service
        finally:
            service.cleanup_called = True  # type: ignore

    container = Container()

    async with container.lifespan():
        container.register(ServiceA, generator1)
        container.register(ServiceB, generator2)

        service_a = await container.resolve(ServiceA)
        service_b = await container.resolve(ServiceB)

        assert service_a.cleanup_called is False
        assert service_b.cleanup_called is False  # type: ignore

    # Both should be cleaned up
    assert service_a.cleanup_called is True
    assert service_b.cleanup_called is True  # type: ignore


@pytest.mark.asyncio
async def test_generator_without_lifespan_context():
    """Test generator behavior when used without lifespan context (edge case)."""
    container = Container()
    container.register(ServiceA, async_generator_factory)

    # Without lifespan, generator still works but cleanup is immediate
    service = await container.resolve(ServiceA)
    assert isinstance(service, ServiceA)
    assert service.value == "async_gen"


@pytest.mark.asyncio
async def test_generator_singleton_behavior():
    """Test that generator dependencies respect singleton caching."""
    container = Container()

    async with container.lifespan():
        container.register(ServiceA, async_generator_factory, singleton=True)

        service1 = await container.resolve(ServiceA)
        service2 = await container.resolve(ServiceA)

        # Should be the same instance (singleton)
        assert service1 is service2


# ===========================================================================
# *                    3. Scope Lifecycle Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_singleton_scope_caching():
    """Test singleton scope caches instances at app level."""
    CounterService.reset()
    container = Container()
    container.register(CounterService, singleton=True)

    service1 = await container.resolve(CounterService)
    service2 = await container.resolve(CounterService)
    service3 = await container.resolve(CounterService)

    # All should be the same instance
    assert service1 is service2
    assert service2 is service3
    assert CounterService.instance_count == 1


@pytest.mark.asyncio
async def test_request_scope_caching():
    """Test request scope caches instances per-request."""
    CounterService.reset()

    class RequestScopedService:
        instance_count = 0

        def __init__(self):
            RequestScopedService.instance_count += 1
            self.instance_id = RequestScopedService.instance_count

    container = Container()

    def get_service() -> RequestScopedService:
        return RequestScopedService()

    class Consumer:
        def __init__(
            self,
            service: Annotated[
                RequestScopedService, Depends(get_service, scope="request")
            ] = INJECTED[RequestScopedService],
        ):
            self.service = service

    container.register(RequestScopedService, get_service)
    container.register(Consumer)

    # First request
    consumer1 = await container.resolve(Consumer)
    service1 = await container._resolve_dependency(
        "service",
        None,  # type: ignore
        Depends(get_service, scope="request"),
        RequestScopedService,
        {},
        None,
    )

    # Within same request, should get same instance
    assert consumer1.service.instance_id == service1.instance_id

    # Clear request cache (simulating new request)
    container.clear_request_cache()

    # Second request - should get new instance
    consumer2 = await container.resolve(Consumer)
    assert consumer2.service.instance_id != consumer1.service.instance_id


@pytest.mark.asyncio
async def test_function_scope_no_caching():
    """Test function scope creates new instance on every call."""
    CounterService.reset()

    class FunctionScopedService:
        instance_count = 0

        def __init__(self):
            FunctionScopedService.instance_count += 1
            self.instance_id = FunctionScopedService.instance_count

    def get_service() -> FunctionScopedService:
        return FunctionScopedService()

    container = Container()

    # Use function scope
    service1 = await container._resolve_dependency(
        "service",
        None,  # type: ignore
        Depends(get_service, scope="function"),
        FunctionScopedService,
        {},
        None,
    )
    service2 = await container._resolve_dependency(
        "service",
        None,  # type: ignore
        Depends(get_service, scope="function"),
        FunctionScopedService,
        {},
        None,
    )
    service3 = await container._resolve_dependency(
        "service",
        None,  # type: ignore
        Depends(get_service, scope="function"),
        FunctionScopedService,
        {},
        None,
    )

    # Each call should create a new instance
    assert service1.instance_id == 1
    assert service2.instance_id == 2
    assert service3.instance_id == 3
    assert FunctionScopedService.instance_count == 3


@pytest.mark.asyncio
async def test_use_cache_false_bypasses_singleton():
    """Test that use_cache=False bypasses all caching including singleton."""
    CounterService.reset()

    def get_counter() -> CounterService:
        return CounterService()

    container = Container()
    container.register(CounterService, get_counter, singleton=True)

    # With use_cache=True (default), should use singleton cache
    service1 = await container._resolve_dependency(
        "service",
        None,  # type: ignore
        Depends(get_counter, use_cache=True),
        CounterService,
        {},
        None,
    )
    service2 = await container._resolve_dependency(
        "service",
        None,  # type: ignore
        Depends(get_counter, use_cache=True),
        CounterService,
        {},
        None,
    )

    # Should be same instance
    assert service1 is service2

    # With use_cache=False, should bypass cache
    service3 = await container._resolve_dependency(
        "service",
        None,  # type: ignore
        Depends(get_counter, use_cache=False),
        CounterService,
        {},
        None,
    )
    service4 = await container._resolve_dependency(
        "service",
        None,  # type: ignore
        Depends(get_counter, use_cache=False),
        CounterService,
        {},
        None,
    )

    # Each should be a new instance
    assert service3 is not service1
    assert service4 is not service1
    assert service4 is not service3


@pytest.mark.asyncio
async def test_scope_hierarchy():
    """Test scope hierarchy: singleton > request > function."""
    container = Container()

    class SingletonService:
        count = 0

        def __init__(self):
            SingletonService.count += 1
            self.id = SingletonService.count

    def get_singleton() -> SingletonService:
        return SingletonService()

    # Singleton scope - cached at app level
    s1 = await container._resolve_dependency(
        "s",
        None,
        Depends(get_singleton, scope="singleton"),
        SingletonService,
        {},
        None,  # type: ignore
    )
    s2 = await container._resolve_dependency(
        "s",
        None,
        Depends(get_singleton, scope="singleton"),
        SingletonService,
        {},
        None,  # type: ignore
    )
    assert s1 is s2

    # Request scope - cached per request
    container.clear_request_cache()
    r1 = await container._resolve_dependency(
        "r",
        None,
        Depends(get_singleton, scope="request"),
        SingletonService,
        {},
        None,  # type: ignore
    )
    r2 = await container._resolve_dependency(
        "r",
        None,
        Depends(get_singleton, scope="request"),
        SingletonService,
        {},
        None,  # type: ignore
    )
    assert r1 is r2
    assert r1 is not s1  # Different from singleton

    container.clear_request_cache()
    r3 = await container._resolve_dependency(
        "r",
        None,
        Depends(get_singleton, scope="request"),
        SingletonService,
        {},
        None,  # type: ignore
    )
    assert r3 is not r1  # New request = new instance

    # Function scope - never cached
    f1 = await container._resolve_dependency(
        "f",
        None,
        Depends(get_singleton, scope="function"),
        SingletonService,
        {},
        None,  # type: ignore
    )
    f2 = await container._resolve_dependency(
        "f",
        None,
        Depends(get_singleton, scope="function"),
        SingletonService,
        {},
        None,  # type: ignore
    )
    assert f1 is not f2


# ===========================================================================
# *                    4. Error Aggregation Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_error_aggregation_with_collect_errors():
    """Test that collect_errors=True aggregates multiple dependency errors."""

    class FailingDep1:
        def __init__(self):
            raise ValueError("Dep1 failed")

    class FailingDep2:
        def __init__(self):
            raise RuntimeError("Dep2 failed")

    class MultiDepService:
        def __init__(
            self,
            dep1: Annotated[FailingDep1, Depends()] = INJECTED[FailingDep1],
            dep2: Annotated[FailingDep2, Depends()] = INJECTED[FailingDep2],
        ):
            self.dep1 = dep1
            self.dep2 = dep2

    container = Container()
    container.register(FailingDep1)
    container.register(FailingDep2)

    # With collect_errors=True, should return ResolutionResult with errors
    result = await container._call_with_injection(MultiDepService, None, collect_errors=True)

    assert isinstance(result, ResolutionResult)
    assert len(result.errors) == 2
    assert all(isinstance(e, DependencyInjectionError) for e in result.errors)


@pytest.mark.asyncio
async def test_error_aggregation_partial_success():
    """Test that collect_errors returns both successful values and errors."""

    class SuccessfulDep:
        def __init__(self):
            self.value = "success"

    class FailingDep:
        def __init__(self):
            raise ValueError("Failed")

    class MixedDepService:
        def __init__(
            self,
            good: Annotated[SuccessfulDep, Depends()] = INJECTED[SuccessfulDep],
            bad: Annotated[FailingDep, Depends()] = INJECTED[FailingDep],
        ):
            self.good = good
            self.bad = bad

    container = Container()
    container.register(SuccessfulDep)
    container.register(FailingDep)

    result = await container._call_with_injection(MixedDepService, None, collect_errors=True)

    assert isinstance(result, ResolutionResult)
    # Should have the successful dependency in values
    assert "good" in result.values
    assert isinstance(result.values["good"], SuccessfulDep)
    # Should have error for failing dependency
    assert len(result.errors) == 1
    assert isinstance(result.errors[0], DependencyInjectionError)


@pytest.mark.asyncio
async def test_fail_fast_without_collect_errors():
    """Test that without collect_errors, container fails fast on first error."""

    class FailingDep1:
        def __init__(self):
            raise ValueError("Dep1 failed")

    class FailingDep2:
        def __init__(self):
            raise RuntimeError("Dep2 failed")  # Should never get here

    class MultiDepService:
        def __init__(
            self,
            dep1: Annotated[FailingDep1, Depends()] = INJECTED[FailingDep1],
            dep2: Annotated[FailingDep2, Depends()] = INJECTED[FailingDep2],
        ):
            self.dep1 = dep1
            self.dep2 = dep2

    container = Container()
    container.register(FailingDep1)
    container.register(FailingDep2)

    # Without collect_errors (default), should raise on first error
    with pytest.raises(DependencyInjectionError):
        await container._call_with_injection(MultiDepService, None, collect_errors=False)


@pytest.mark.asyncio
async def test_no_errors_returns_instance_not_result():
    """Test that when collect_errors=True but no errors occur, instance is returned."""

    class SuccessfulService:
        def __init__(self):
            self.value = "success"

    container = Container()
    container.register(SuccessfulService)

    result = await container._call_with_injection(SuccessfulService, None, collect_errors=True)

    # When no errors, should return the actual instance, not ResolutionResult
    assert isinstance(result, SuccessfulService)
    assert result.value == "success"


# ===========================================================================
# *                    5. Union Type Resolution Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_union_type_resolution_first_match():
    """Test Union type resolution tries types in order and returns first match."""
    container = Container()
    container.register(ImplementationX)
    container.register(ImplementationY)

    # Register X first, should resolve to X
    result = await container.resolve(Union[ImplementationX, ImplementationY])
    assert isinstance(result, ImplementationX)
    assert result.name == "X"


@pytest.mark.asyncio
async def test_union_type_pipe_syntax():
    """Test Union resolution works with Python 3.10+ pipe syntax (X | Y)."""
    container = Container()
    container.register(ImplementationX)
    container.register(ImplementationY)

    # Should work with | syntax
    result = await container.resolve(ImplementationX | ImplementationY)
    assert isinstance(result, ImplementationX)


@pytest.mark.asyncio
async def test_union_type_skips_none():
    """Test Union type resolution skips None types."""
    container = Container()
    container.register(ImplementationX)

    # Union[ImplementationX, None] should resolve to ImplementationX
    result = await container.resolve(Union[ImplementationX, None])
    assert isinstance(result, ImplementationX)
    assert result.name == "X"


@pytest.mark.asyncio
async def test_union_type_tries_unregistered():
    """Test Union tries to instantiate unregistered types if registered ones fail."""

    class NotRegistered:
        def __init__(self):
            self.name = "not_registered"

    container = Container()
    # Don't register NotRegistered, but it has a valid __init__

    result = await container.resolve(Union[NotRegistered, ImplementationX])
    assert isinstance(result, NotRegistered)
    assert result.name == "not_registered"


@pytest.mark.asyncio
async def test_union_type_all_fail_raises():
    """Test Union resolution raises if no type can be resolved."""

    class NeedsDependency:
        def __init__(self, dep: ServiceA = INJECTED[ServiceA]):  # ty:ignore[invalid-parameter-default]
            self.dep = dep

    container = Container()
    # Don't register ServiceA, so NeedsDependency can't be instantiated

    with pytest.raises(ValueError) as exc_info:
        await container.resolve(Union[NeedsDependency, None])

    assert "Could not resolve any type from union" in str(exc_info.value)


@pytest.mark.asyncio
async def test_union_with_override():
    """Test Union resolution respects overrides."""
    container = Container()
    container.register(ImplementationX)
    container.register(ImplementationY)

    # Override X with a specific instance
    override_x = ImplementationX()
    override_x.name = "X_override"
    container.override(ImplementationX, override_x)

    result = await container.resolve(Union[ImplementationX, ImplementationY])
    assert result is override_x
    assert result.name == "X_override"


@pytest.mark.asyncio
async def test_union_none_only_raises():
    """Test Union[None] (edge case) raises error."""
    container = Container()

    with pytest.raises(ValueError) as exc_info:
        await container.resolve(Union[None])

    assert "Could not resolve any type from union" in str(exc_info.value)


# ===========================================================================
# *                    6. use_cache Flag Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_use_cache_true_enables_caching():
    """Test use_cache=True enables caching (singleton by default)."""
    CounterService.reset()

    def get_counter() -> CounterService:
        return CounterService()

    container = Container()

    # First call with use_cache=True
    service1 = await container._resolve_dependency(
        "counter",
        None,  # type: ignore
        Depends(get_counter, use_cache=True),
        CounterService,
        {},
        None,
    )

    # Second call with use_cache=True - should get cached instance
    service2 = await container._resolve_dependency(
        "counter",
        None,  # type: ignore
        Depends(get_counter, use_cache=True),
        CounterService,
        {},
        None,
    )

    assert service1 is service2
    assert CounterService.instance_count == 1


@pytest.mark.asyncio
async def test_use_cache_false_disables_caching():
    """Test use_cache=False creates new instance every time."""
    CounterService.reset()

    def get_counter() -> CounterService:
        return CounterService()

    container = Container()

    # Multiple calls with use_cache=False
    service1 = await container._resolve_dependency(
        "counter",
        None,  # type: ignore
        Depends(get_counter, use_cache=False),
        CounterService,
        {},
        None,
    )
    service2 = await container._resolve_dependency(
        "counter",
        None,  # type: ignore
        Depends(get_counter, use_cache=False),
        CounterService,
        {},
        None,
    )
    service3 = await container._resolve_dependency(
        "counter",
        None,  # type: ignore
        Depends(get_counter, use_cache=False),
        CounterService,
        {},
        None,
    )

    # Each should be a different instance
    assert service1 is not service2
    assert service2 is not service3
    assert service1 is not service3
    assert CounterService.instance_count == 3


@pytest.mark.asyncio
async def test_use_cache_false_with_scope_parameter():
    """Test that use_cache=False takes precedence over scope parameter."""
    CounterService.reset()

    def get_counter() -> CounterService:
        return CounterService()

    container = Container()

    # Even with scope="singleton", use_cache=False should disable caching
    service1 = await container._resolve_dependency(
        "counter",
        None,  # type: ignore
        Depends(get_counter, use_cache=False, scope="singleton"),
        CounterService,
        {},
        None,
    )
    service2 = await container._resolve_dependency(
        "counter",
        None,  # type: ignore
        Depends(get_counter, use_cache=False, scope="singleton"),
        CounterService,
        {},
        None,
    )

    # Should still create new instances despite scope="singleton"
    assert service1 is not service2
    assert CounterService.instance_count == 2


@pytest.mark.asyncio
async def test_use_cache_default_behavior():
    """Test that use_cache defaults to True."""
    CounterService.reset()

    def get_counter() -> CounterService:
        return CounterService()

    container = Container()

    # Don't specify use_cache - should default to True
    service1 = await container._resolve_dependency(
        "counter",
        None,  # type: ignore
        Depends(get_counter),  # use_cache defaults to True
        CounterService,
        {},
        None,
    )
    service2 = await container._resolve_dependency(
        "counter",
        None,  # type: ignore
        Depends(get_counter),
        CounterService,
        {},
        None,
    )

    # Should be cached by default
    assert service1 is service2
    assert CounterService.instance_count == 1


@pytest.mark.asyncio
async def test_use_cache_with_generator():
    """Test use_cache flag works correctly with generator dependencies."""

    async def counter_generator() -> AsyncIterator[CounterService]:
        service = CounterService()
        yield service

    container = Container()
    CounterService.reset()

    async with container.lifespan():
        # With caching
        container.register(CounterService, counter_generator, singleton=True)
        s1 = await container._resolve_dependency(
            "c",
            None,
            Depends(counter_generator, use_cache=True),
            CounterService,
            {},
            None,  # type: ignore
        )
        s2 = await container._resolve_dependency(
            "c",
            None,
            Depends(counter_generator, use_cache=True),
            CounterService,
            {},
            None,  # type: ignore
        )
        assert s1 is s2

        # Clear and test without caching
        container.clear()
        CounterService.reset()
        container.register(CounterService, counter_generator)

        s3 = await container._resolve_dependency(
            "c",
            None,
            Depends(counter_generator, use_cache=False),
            CounterService,
            {},
            None,  # type: ignore
        )
        s4 = await container._resolve_dependency(
            "c",
            None,
            Depends(counter_generator, use_cache=False),
            CounterService,
            {},
            None,  # type: ignore
        )
        # Without caching, should get different instances
        assert s3 is not s4


# ===========================================================================
# *                    Edge Cases and Integration Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_circular_in_union_type():
    """Test circular dependency detection works with union types."""
    container = Container()
    container.register(CircularServiceA)
    container.register(CircularServiceB)

    with pytest.raises(CircularDependencyError):
        await container.resolve(Union[CircularServiceA, CircularServiceB])


@pytest.mark.asyncio
async def test_generator_with_error_aggregation():
    """Test generator dependencies work correctly with error aggregation."""

    async def gen_service() -> AsyncIterator[ServiceA]:
        service = ServiceA("gen")
        yield service

    class FailingDep:
        def __init__(self):
            raise ValueError("Failed")

    class MixedService:
        def __init__(
            self,
            good: Annotated[ServiceA, Depends()] = INJECTED[ServiceA],
            bad: Annotated[FailingDep, Depends()] = INJECTED[FailingDep],
        ):
            self.good = good
            self.bad = bad

    container = Container()
    container.register(ServiceA, gen_service)
    container.register(FailingDep)

    async with container.lifespan():
        result = await container._call_with_injection(MixedService, None, collect_errors=True)

        assert isinstance(result, ResolutionResult)
        assert "good" in result.values
        assert len(result.errors) == 1


@pytest.mark.asyncio
async def test_scope_with_union_resolution():
    """Test scope behavior works correctly with union type resolution."""
    CounterService.reset()

    container = Container()

    def get_counter() -> CounterService:
        return CounterService()

    # Register for union resolution
    container.register(CounterService, get_counter)

    # Request scope with union type
    r1 = await container._resolve_dependency(
        "c",
        None,  # type: ignore
        Depends(get_counter, scope="request"),
        Union[CounterService, ServiceA],
        {},
        None,
    )
    r2 = await container._resolve_dependency(
        "c",
        None,  # type: ignore
        Depends(get_counter, scope="request"),
        Union[CounterService, ServiceA],
        {},
        None,
    )

    # Should be cached within request
    assert r1 is r2

    container.clear_request_cache()

    r3 = await container._resolve_dependency(
        "c",
        None,  # type: ignore
        Depends(get_counter, scope="request"),
        Union[CounterService, ServiceA],
        {},
        None,
    )
    # New request should have new instance
    assert r3 is not r1


@pytest.mark.asyncio
async def test_complex_dependency_graph_with_all_features():
    """Integration test using circular detection, scopes, and error handling together."""

    class RootService:
        instance_count = 0

        def __init__(self):
            RootService.instance_count += 1
            self.id = RootService.instance_count

    class CachedService:
        def __init__(
            self, root: Annotated[RootService, Depends(scope="singleton")] = INJECTED[RootService]
        ):
            self.root = root

    class UncachedService:
        def __init__(
            self, root: Annotated[RootService, Depends(use_cache=False)] = INJECTED[RootService]
        ):
            self.root = root

    RootService.instance_count = 0
    container = Container()
    container.register(RootService, singleton=True)
    container.register(CachedService)
    container.register(UncachedService)

    # Cached services should share root
    cached1 = await container.resolve(CachedService)
    cached2 = await container.resolve(CachedService)
    assert cached1.root is cached2.root
    assert RootService.instance_count == 1

    # Uncached should get new root each time
    uncached1 = await container.resolve(UncachedService)
    uncached2 = await container.resolve(UncachedService)
    assert uncached1.root is not uncached2.root
    assert RootService.instance_count == 3  # 1 cached + 2 uncached
