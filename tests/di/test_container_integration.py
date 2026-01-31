# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration tests for Container with @dependency_provider auto-discovery.

Tests the complete integration between:
- @dependency_provider decorator registration
- Container auto-discovery (_load_providers)
- Dependency resolution and scoping
- Container lifecycle management
"""

from __future__ import annotations

import asyncio

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING

import pytest

from codeweaver.core import Container, Depends, dependency_provider


if TYPE_CHECKING:
    from typing import Annotated


# Test services
class DatabaseConnection:
    """Mock database connection."""

    def __init__(self, url: str = "sqlite:///:memory:") -> None:
        self.url = url
        self.connected = False

    async def connect(self):
        self.connected = True

    async def disconnect(self):
        self.connected = False


class CacheService:
    """Mock cache service."""

    def __init__(self, ttl: int = 300) -> None:
        self.ttl = ttl
        self.data: dict[str, str] = {}


class UserService:
    """Service that depends on other services."""

    def __init__(self, db: DatabaseConnection, cache: CacheService) -> None:
        self.db = db
        self.cache = cache


@pytest.fixture
def clean_registry():
    """Clean the provider registry before and after each test."""
    from codeweaver.core.di import utils

    # Store original state - deep copy to preserve the list structure
    original_providers = {k: v.copy() for k, v in utils._providers.items()}
    
    # Clear registry for test isolation
    utils._providers.clear()

    yield

    # Restore original state
    utils._providers.clear()
    utils._providers.update(original_providers)


# ==============================================================================
# Basic Auto-Discovery Tests
# ==============================================================================


async def test_container_auto_discovers_providers_on_first_resolve(clean_registry):
    """Test that Container loads providers from registry on first resolve."""

    @dependency_provider(DatabaseConnection, scope="singleton")
    def create_db() -> DatabaseConnection:
        return DatabaseConnection(url="test://db")

    container = Container()

    # Before first resolve, providers should not be loaded
    assert not container._providers_loaded

    # First resolve should trigger auto-discovery
    db = await container.resolve(DatabaseConnection)
    assert container._providers_loaded

    # Verify instance is correct
    assert isinstance(db, DatabaseConnection)
    assert db.url == "test://db"


async def test_container_loads_providers_only_once(clean_registry):
    """Test that _load_providers is idempotent."""

    @dependency_provider(DatabaseConnection, scope="singleton")
    def create_db() -> DatabaseConnection:
        return DatabaseConnection()

    container = Container()

    # Manually call _load_providers multiple times
    container._load_providers()
    container._load_providers()
    container._load_providers()

    # Should only load once
    assert container._providers_loaded

    # Should still work correctly
    db = await container.resolve(DatabaseConnection)
    assert isinstance(db, DatabaseConnection)


async def test_multiple_containers_each_load_providers_independently(clean_registry):
    """Test that each Container instance loads providers independently."""

    call_count = 0

    @dependency_provider(DatabaseConnection, scope="singleton")
    def create_db() -> DatabaseConnection:
        nonlocal call_count
        call_count += 1
        return DatabaseConnection()

    container1 = Container()
    container2 = Container()

    # Both containers should load providers
    db1 = await container1.resolve(DatabaseConnection)
    db2 = await container2.resolve(DatabaseConnection)

    assert container1._providers_loaded
    assert container2._providers_loaded

    # Instances should be different (different container singletons)
    assert db1 is not db2
    assert call_count == 2


# ==============================================================================
# Scope Integration Tests
# ==============================================================================


async def test_singleton_scope_respected_by_container(clean_registry):
    """Test that singleton scope creates only one instance per container."""

    call_count = 0

    @dependency_provider(DatabaseConnection, scope="singleton")
    def create_db() -> DatabaseConnection:
        nonlocal call_count
        call_count += 1
        return DatabaseConnection()

    container = Container()

    # Resolve multiple times
    db1 = await container.resolve(DatabaseConnection)
    db2 = await container.resolve(DatabaseConnection)
    db3 = await container.resolve(DatabaseConnection)

    # Should be the same instance
    assert db1 is db2 is db3
    assert call_count == 1


async def test_request_scope_uses_request_cache(clean_registry):
    """Test that request scope uses per-request caching."""

    call_count = 0

    @dependency_provider(CacheService, scope="request")
    def create_cache() -> CacheService:
        nonlocal call_count
        call_count += 1
        return CacheService()

    container = Container()

    # First request
    cache1a = await container.resolve(CacheService)
    cache1b = await container.resolve(CacheService)
    assert cache1a is cache1b
    assert call_count == 1

    # Clear request cache
    container.clear_request_cache()

    # Second request - should create new instance
    cache2 = await container.resolve(CacheService)
    assert cache2 is not cache1a
    assert call_count == 2


async def test_function_scope_creates_new_instance_every_time(clean_registry):
    """Test that function scope creates new instance on every resolve."""

    call_count = 0

    @dependency_provider(CacheService, scope="function")
    def create_cache() -> CacheService:
        nonlocal call_count
        call_count += 1
        return CacheService(ttl=call_count)

    container = Container()

    # Resolve multiple times
    cache1 = await container.resolve(CacheService)
    cache2 = await container.resolve(CacheService)
    cache3 = await container.resolve(CacheService)

    # Should be different instances
    assert cache1 is not cache2
    assert cache2 is not cache3
    assert call_count == 3

    # Each should have different ttl
    assert cache1.ttl == 1
    assert cache2.ttl == 2
    assert cache3.ttl == 3


# ==============================================================================
# Generator Support Tests
# ==============================================================================


async def test_async_generator_provider_with_cleanup(clean_registry):
    """Test that async generator providers work with cleanup."""

    setup_called = False
    cleanup_called = False

    @dependency_provider(DatabaseConnection, scope="singleton")
    async def create_db_with_cleanup() -> AsyncIterator[DatabaseConnection]:
        nonlocal setup_called, cleanup_called
        # Setup
        setup_called = True
        db = DatabaseConnection()
        await db.connect()
        try:
            yield db
        finally:
            # Cleanup
            cleanup_called = True
            await db.disconnect()

    container = Container()

    # Use within lifespan context
    async with container.lifespan():
        db = await container.resolve(DatabaseConnection)
        assert isinstance(db, DatabaseConnection)
        assert db.connected
        assert setup_called
        assert not cleanup_called  # Not yet cleaned up

    # After lifespan, cleanup should have been called
    assert cleanup_called


async def test_sync_generator_provider_with_cleanup(clean_registry):
    """Test that sync generator providers work with cleanup."""

    cleanup_called = False

    @dependency_provider(CacheService, scope="singleton")
    def create_cache_with_cleanup() -> Iterator[CacheService]:
        nonlocal cleanup_called
        # Setup
        cache = CacheService()
        cache.data["initialized"] = "true"
        try:
            yield cache
        finally:
            # Cleanup
            cleanup_called = True
            cache.data.clear()

    container = Container()

    async with container.lifespan():
        cache = await container.resolve(CacheService)
        assert isinstance(cache, CacheService)
        assert cache.data["initialized"] == "true"
        assert not cleanup_called

    # After lifespan, cleanup should have been called
    assert cleanup_called


# ==============================================================================
# Dependency Injection with Auto-Discovery
# ==============================================================================


async def test_dependency_injection_with_auto_discovered_providers(clean_registry):
    """Test that Container injects auto-discovered providers as dependencies."""

    @dependency_provider(DatabaseConnection, scope="singleton")
    def create_db() -> DatabaseConnection:
        return DatabaseConnection(url="auto://discovered")

    @dependency_provider(CacheService, scope="singleton")
    def create_cache() -> CacheService:
        return CacheService(ttl=600)

    @dependency_provider(UserService, scope="singleton")
    def create_user_service(
        db: Annotated[DatabaseConnection, Depends()], cache: Annotated[CacheService, Depends()]
    ) -> UserService:
        return UserService(db=db, cache=cache)

    container = Container()

    # Resolve UserService - should auto-inject dependencies
    user_service = await container.resolve(UserService)
    assert isinstance(user_service, UserService)
    assert isinstance(user_service.db, DatabaseConnection)
    assert isinstance(user_service.cache, CacheService)
    assert user_service.db.url == "auto://discovered"
    assert user_service.cache.ttl == 600


async def test_complex_dependency_graph_with_auto_discovery(clean_registry):
    """Test complex dependency graphs with auto-discovered providers."""

    class ConfigService:
        def __init__(self, env: str = "test") -> None:
            self.env = env

    class LoggingService:
        def __init__(self, config: ConfigService) -> None:
            self.config = config

    class ApiService:
        def __init__(
            self, db: DatabaseConnection, cache: CacheService, logger: LoggingService
        ) -> None:
            self.db = db
            self.cache = cache
            self.logger = logger

    @dependency_provider(ConfigService, scope="singleton")
    def create_config() -> ConfigService:
        return ConfigService(env="production")

    @dependency_provider(LoggingService, scope="singleton")
    def create_logger(config: Annotated[ConfigService, Depends()]) -> LoggingService:
        return LoggingService(config=config)

    @dependency_provider(DatabaseConnection, scope="singleton")
    def create_db() -> DatabaseConnection:
        return DatabaseConnection()

    @dependency_provider(CacheService, scope="singleton")
    def create_cache() -> CacheService:
        return CacheService()

    @dependency_provider(ApiService, scope="singleton")
    def create_api(
        db: Annotated[DatabaseConnection, Depends()],
        cache: Annotated[CacheService, Depends()],
        logger: Annotated[LoggingService, Depends()],
    ) -> ApiService:
        return ApiService(db=db, cache=cache, logger=logger)

    container = Container()

    # Resolve ApiService - should resolve entire dependency tree
    api = await container.resolve(ApiService)
    assert isinstance(api, ApiService)
    assert isinstance(api.db, DatabaseConnection)
    assert isinstance(api.cache, CacheService)
    assert isinstance(api.logger, LoggingService)
    assert isinstance(api.logger.config, ConfigService)
    assert api.logger.config.env == "production"


# ==============================================================================
# Class Self-Registration Tests
# ==============================================================================


async def test_class_self_registration_integration(clean_registry):
    """Test that class self-registration works with Container."""

    @dependency_provider(scope="singleton")
    class AutoRegisteredService:
        def __init__(self) -> None:
            self.value = 42

    container = Container()
    instance = await container.resolve(AutoRegisteredService)

    assert isinstance(instance, AutoRegisteredService)
    assert instance.value == 42


async def test_class_self_registration_with_dependencies(clean_registry):
    """Test class self-registration with dependency injection."""

    @dependency_provider(scope="singleton")
    class ConfigService:
        def __init__(self) -> None:
            self.setting = "enabled"

    @dependency_provider(scope="singleton")
    class ServiceWithDependency:
        def __init__(self, config: Annotated[ConfigService, Depends()]) -> None:
            self.config = config

    container = Container()
    service = await container.resolve(ServiceWithDependency)

    assert isinstance(service, ServiceWithDependency)
    assert isinstance(service.config, ConfigService)
    assert service.config.setting == "enabled"


# ==============================================================================
# Container Lifecycle Tests
# ==============================================================================


def test_container_clear_resets_provider_loading_flag(clean_registry):
    """Test that Container.clear() resets the provider loading flag."""

    @dependency_provider(DatabaseConnection, scope="singleton")
    def create_db() -> DatabaseConnection:
        return DatabaseConnection()

    container = Container()

    # Trigger provider loading
    container._load_providers()
    assert container._providers_loaded

    # Clear should reset the flag
    container.clear()
    assert not container._providers_loaded


async def test_container_clear_allows_reload_of_providers(clean_registry):
    """Test that clearing container allows providers to be reloaded."""

    @dependency_provider(DatabaseConnection, scope="singleton")
    def create_db() -> DatabaseConnection:
        return DatabaseConnection(url="first")

    container = Container()

    # First load
    db1 = await container.resolve(DatabaseConnection)
    assert db1.url == "first"

    # Clear and re-register
    container.clear()

    @dependency_provider(DatabaseConnection, scope="singleton")
    def create_db_new() -> DatabaseConnection:
        return DatabaseConnection(url="second")

    # Second load should use new provider
    db2 = await container.resolve(DatabaseConnection)
    assert db2.url == "second"


async def test_container_clear_request_cache_only_clears_request_scope(clean_registry):
    """Test that clear_request_cache only affects request-scoped dependencies."""

    @dependency_provider(DatabaseConnection, scope="singleton")
    def create_db() -> DatabaseConnection:
        return DatabaseConnection()

    @dependency_provider(CacheService, scope="request")
    def create_cache() -> CacheService:
        return CacheService()

    container = Container()

    # Resolve both
    db1 = await container.resolve(DatabaseConnection)
    cache1 = await container.resolve(CacheService)

    # Clear request cache
    container.clear_request_cache()

    # Singleton should be same instance
    db2 = await container.resolve(DatabaseConnection)
    assert db1 is db2

    # Request-scoped should be new instance
    cache2 = await container.resolve(CacheService)
    assert cache1 is not cache2


# ==============================================================================
# Overrides and Auto-Discovery Interaction
# ==============================================================================


async def test_overrides_take_precedence_over_auto_discovered_providers(clean_registry):
    """Test that manual overrides take precedence over auto-discovered providers."""

    @dependency_provider(DatabaseConnection, scope="singleton")
    def create_db() -> DatabaseConnection:
        return DatabaseConnection(url="auto://discovered")

    container = Container()

    # Set override
    override_db = DatabaseConnection(url="override://db")
    container.override(DatabaseConnection, override_db)

    # Should use override, not auto-discovered provider
    db = await container.resolve(DatabaseConnection)
    assert db is override_db
    assert db.url == "override://db"


async def test_clear_overrides_allows_auto_discovered_providers(clean_registry):
    """Test that clearing overrides allows auto-discovered providers to work."""

    @dependency_provider(DatabaseConnection, scope="singleton")
    def create_db() -> DatabaseConnection:
        return DatabaseConnection(url="auto://discovered")

    container = Container()

    # Set override
    container.override(DatabaseConnection, DatabaseConnection(url="override://db"))

    # Clear overrides
    container.clear_overrides()

    # Should use auto-discovered provider now
    db = await container.resolve(DatabaseConnection)
    assert db.url == "auto://discovered"


# ==============================================================================
# Error Handling Tests
# ==============================================================================


async def test_container_handles_missing_provider_gracefully(clean_registry):
    """Test that Container handles missing providers with clear error."""

    class UnregisteredService:
        pass

    container = Container()

    # Should attempt to instantiate directly if no provider
    # This is the fallback behavior
    service = await container.resolve(UnregisteredService)
    assert isinstance(service, UnregisteredService)


async def test_container_with_no_providers_registered(clean_registry):
    """Test Container behavior when no providers are registered."""
    container = Container()

    # Loading providers should not fail when registry is empty
    container._load_providers()
    assert container._providers_loaded

    # Should still work for types without providers
    class SimpleService:
        pass

    service = await container.resolve(SimpleService)
    assert isinstance(service, SimpleService)


# ==============================================================================
# Concurrent Access Tests
# ==============================================================================


async def test_concurrent_provider_loading_is_safe(clean_registry):
    """Test that concurrent access to container is safe during provider loading."""

    @dependency_provider(DatabaseConnection, scope="singleton")
    def create_db() -> DatabaseConnection:
        return DatabaseConnection()

    container = Container()

    # Resolve concurrently from multiple tasks
    async def resolve_db():
        return await container.resolve(DatabaseConnection)

    results = await asyncio.gather(*[resolve_db() for _ in range(10)])

    # All should succeed and return the same singleton
    assert len(results) == 10
    assert all(isinstance(r, DatabaseConnection) for r in results)
    # All should be the same instance (singleton)
    assert all(r is results[0] for r in results)


# ==============================================================================
# Real-World Integration Scenarios
# ==============================================================================


async def test_full_application_bootstrap_scenario(clean_registry):
    """Test realistic application bootstrap scenario with multiple services."""

    # Define services
    class Config:
        def __init__(self) -> None:
            self.db_url = "postgresql://localhost/app"
            self.cache_ttl = 3600

    class Database:
        def __init__(self, config: Config) -> None:
            self.url = config.db_url

    class Cache:
        def __init__(self, config: Config) -> None:
            self.ttl = config.cache_ttl

    class Repository:
        def __init__(self, db: Database) -> None:
            self.db = db

    class Application:
        def __init__(self, config: Config, db: Database, cache: Cache, repo: Repository) -> None:
            self.config = config
            self.db = db
            self.cache = cache
            self.repo = repo

    # Register providers
    @dependency_provider(Config, scope="singleton")
    def create_config() -> Config:
        return Config()

    @dependency_provider(Database, scope="singleton")
    def create_db(config: Annotated[Config, Depends()]) -> Database:
        return Database(config=config)

    @dependency_provider(Cache, scope="singleton")
    def create_cache(config: Annotated[Config, Depends()]) -> Cache:
        return Cache(config=config)

    @dependency_provider(Repository, scope="singleton")
    def create_repo(db: Annotated[Database, Depends()]) -> Repository:
        return Repository(db=db)

    @dependency_provider(Application, scope="singleton")
    def create_app(
        config: Annotated[Config, Depends()],
        db: Annotated[Database, Depends()],
        cache: Annotated[Cache, Depends()],
        repo: Annotated[Repository, Depends()],
    ) -> Application:
        return Application(config=config, db=db, cache=cache, repo=repo)

    # Bootstrap application
    container = Container()
    app = await container.resolve(Application)

    # Verify entire dependency tree
    assert isinstance(app, Application)
    assert isinstance(app.config, Config)
    assert isinstance(app.db, Database)
    assert isinstance(app.cache, Cache)
    assert isinstance(app.repo, Repository)
    assert app.db.url == "postgresql://localhost/app"
    assert app.cache.ttl == 3600

    # Verify singletons are shared
    config = await container.resolve(Config)
    assert config is app.config
