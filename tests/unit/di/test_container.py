# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0


import pytest

from codeweaver.di import Container, Depends


class MockService:
    def __init__(self, value: str = "default"):
        self.value = value


async def mock_factory() -> MockService:
    return MockService("factory")


class NestedService:
    def __init__(self, service: MockService = Depends(mock_factory)):  # ty:ignore[invalid-parameter-default]
        self.service = service


@pytest.mark.asyncio
async def test_container_basic_resolution():
    container = Container()
    container.register(MockService, mock_factory)

    service = await container.resolve(MockService)
    assert isinstance(service, MockService)
    assert service.value == "factory"


@pytest.mark.asyncio
async def test_container_singleton_behavior():
    container = Container()
    container.register(MockService, mock_factory, singleton=True)

    service1 = await container.resolve(MockService)
    service2 = await container.resolve(MockService)

    assert service1 is service2


@pytest.mark.asyncio
async def test_container_nested_resolution():
    container = Container()
    container.register(MockService, mock_factory)
    container.register(NestedService)

    nested = await container.resolve(NestedService)
    assert isinstance(nested, NestedService)
    assert nested.service.value == "factory"


@pytest.mark.asyncio
async def test_container_override():
    container = Container()
    container.register(MockService, mock_factory)

    mock_instance = MockService("override")
    container.override(MockService, mock_instance)

    service = await container.resolve(MockService)
    assert service.value == "override"
    assert service is mock_instance


@pytest.mark.asyncio
async def test_container_lifespan():
    container = Container()
    startup_called = False
    shutdown_called = False

    async def startup():
        nonlocal startup_called
        startup_called = True

    async def shutdown():
        nonlocal shutdown_called
        shutdown_called = True

    container.add_startup_hook(startup)
    container.add_shutdown_hook(shutdown)

    async with container.lifespan():
        assert startup_called
        assert not shutdown_called

    assert shutdown_called


@pytest.mark.asyncio
async def test_container_type_hint_resolution():
    container = Container()

    class ServiceA:
        pass

    class ServiceB:
        def __init__(self, a: ServiceA = Depends()):  # ty:ignore[invalid-parameter-default]  # noqa: B008
            self.a = a

    container.register(ServiceA)
    container.register(ServiceB)

    b = await container.resolve(ServiceB)
    assert isinstance(b.a, ServiceA)
