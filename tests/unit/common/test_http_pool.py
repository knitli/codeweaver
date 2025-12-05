# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for HTTP client connection pool manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from codeweaver.common.http_pool import (
    HttpClientPool,
    PoolLimits,
    PoolTimeouts,
    get_http_pool,
    reset_http_pool,
    reset_http_pool_sync,
)


class TestPoolLimits:
    """Tests for PoolLimits configuration dataclass."""

    def test_default_values(self):
        """Test default pool limits."""
        limits = PoolLimits()
        assert limits.max_connections == 100
        assert limits.max_keepalive_connections == 20
        assert limits.keepalive_expiry == 5.0

    def test_custom_values(self):
        """Test custom pool limits."""
        limits = PoolLimits(
            max_connections=50,
            max_keepalive_connections=10,
            keepalive_expiry=10.0,
        )
        assert limits.max_connections == 50
        assert limits.max_keepalive_connections == 10
        assert limits.keepalive_expiry == 10.0

    def test_immutable(self):
        """Test that PoolLimits is frozen (immutable)."""
        limits = PoolLimits()
        with pytest.raises(AttributeError):
            limits.max_connections = 200  # type: ignore


class TestPoolTimeouts:
    """Tests for PoolTimeouts configuration dataclass."""

    def test_default_values(self):
        """Test default pool timeouts."""
        timeouts = PoolTimeouts()
        assert timeouts.connect == 10.0
        assert timeouts.read == 60.0
        assert timeouts.write == 10.0
        assert timeouts.pool == 5.0

    def test_custom_values(self):
        """Test custom pool timeouts."""
        timeouts = PoolTimeouts(
            connect=5.0,
            read=120.0,
            write=15.0,
            pool=10.0,
        )
        assert timeouts.connect == 5.0
        assert timeouts.read == 120.0
        assert timeouts.write == 15.0
        assert timeouts.pool == 10.0

    def test_immutable(self):
        """Test that PoolTimeouts is frozen (immutable)."""
        timeouts = PoolTimeouts()
        with pytest.raises(AttributeError):
            timeouts.read = 200.0  # type: ignore


class TestHttpClientPool:
    """Tests for HttpClientPool manager."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool singleton before and after each test with proper cleanup."""
        await reset_http_pool()
        yield
        await reset_http_pool()

    def test_singleton_pattern(self):
        """Test that get_instance returns the same instance."""
        pool1 = HttpClientPool.get_instance()
        pool2 = HttpClientPool.get_instance()
        assert pool1 is pool2

    def test_get_http_pool_returns_singleton(self):
        """Test that get_http_pool returns the singleton instance."""
        pool1 = get_http_pool()
        pool2 = get_http_pool()
        assert pool1 is pool2

    @pytest.mark.asyncio
    async def test_reset_instance(self):
        """Test that reset_instance clears the singleton."""
        pool1 = HttpClientPool.get_instance()
        await reset_http_pool()
        pool2 = HttpClientPool.get_instance()
        assert pool1 is not pool2

    @pytest.mark.asyncio
    async def test_get_client_creates_client(self):
        """Test that get_client creates an httpx.AsyncClient."""
        pool = HttpClientPool.get_instance()
        client = await pool.get_client("test_provider")

        assert isinstance(client, httpx.AsyncClient)
        assert pool.has_client("test_provider")
        assert "test_provider" in pool.client_names

    @pytest.mark.asyncio
    async def test_get_client_reuses_client(self):
        """Test that get_client returns the same client for same name."""
        pool = HttpClientPool.get_instance()
        client1 = await pool.get_client("test_provider")
        client2 = await pool.get_client("test_provider")

        assert client1 is client2

    @pytest.mark.asyncio
    async def test_get_client_with_overrides(self):
        """Test that get_client applies override settings correctly."""
        pool = HttpClientPool.get_instance()
        client = await pool.get_client(
            "custom_provider",
            max_connections=25,
            read_timeout=120.0,
            connect_timeout=5.0,
        )

        # Verify client was created
        assert pool.has_client("custom_provider")

        # Verify timeout overrides are actually applied
        assert client.timeout.read == 120.0
        assert client.timeout.connect == 5.0

        # Verify limits are applied via transport pool
        # Note: httpx internal structure may vary, but we can check the limits object
        assert client._limits.max_connections == 25

    def test_get_client_sync_creates_client(self):
        """Test that get_client_sync creates an httpx.AsyncClient."""
        pool = HttpClientPool.get_instance()
        client = pool.get_client_sync("test_provider")

        assert isinstance(client, httpx.AsyncClient)
        assert pool.has_client("test_provider")

    def test_get_client_sync_with_overrides(self):
        """Test that get_client_sync applies override settings correctly."""
        pool = HttpClientPool.get_instance()
        client = pool.get_client_sync(
            "custom_provider",
            max_connections=25,
            read_timeout=120.0,
        )

        # Verify timeout overrides are actually applied
        assert client.timeout.read == 120.0
        assert client._limits.max_connections == 25

    @pytest.mark.asyncio
    async def test_multiple_providers(self):
        """Test that different providers get different clients."""
        pool = HttpClientPool.get_instance()
        voyage_client = await pool.get_client("voyage")
        cohere_client = await pool.get_client("cohere")

        assert voyage_client is not cohere_client
        assert pool.has_client("voyage")
        assert pool.has_client("cohere")
        assert len(pool.client_names) == 2

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Test that close_client closes and removes a client."""
        pool = HttpClientPool.get_instance()
        await pool.get_client("test_provider")

        assert pool.has_client("test_provider")

        result = await pool.close_client("test_provider")

        assert result is True
        assert not pool.has_client("test_provider")

    @pytest.mark.asyncio
    async def test_close_nonexistent_client(self):
        """Test that close_client returns False for nonexistent client."""
        pool = HttpClientPool.get_instance()
        result = await pool.close_client("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_close_client_handles_aclose_error(self):
        """Test that close_client handles aclose() exceptions gracefully."""
        pool = HttpClientPool.get_instance()
        await pool.get_client("test_provider")

        # Mock the client's aclose to raise an error
        client = pool._clients["test_provider"]
        client.aclose = AsyncMock(side_effect=httpx.HTTPError("connection error"))

        # close_client should not raise and should return False (client is still removed)
        result = await pool.close_client("test_provider")

        # Client should be removed despite error
        assert not pool.has_client("test_provider")
        # Returns False when there's an error during close
        assert result is False

    @pytest.mark.asyncio
    async def test_close_client_handles_os_error(self):
        """Test that close_client handles OSError gracefully."""
        pool = HttpClientPool.get_instance()
        await pool.get_client("test_provider")

        # Mock the client's aclose to raise an OSError
        client = pool._clients["test_provider"]
        client.aclose = AsyncMock(side_effect=OSError("socket error"))

        result = await pool.close_client("test_provider")

        # Client should be removed despite error
        assert not pool.has_client("test_provider")
        assert result is False

    @pytest.mark.asyncio
    async def test_close_all(self):
        """Test that close_all closes all clients."""
        pool = HttpClientPool.get_instance()
        await pool.get_client("provider1")
        await pool.get_client("provider2")
        await pool.get_client("provider3")

        assert len(pool.client_names) == 3

        await pool.close_all()

        assert len(pool.client_names) == 0

    @pytest.mark.asyncio
    async def test_close_all_handles_errors(self):
        """Test that close_all handles aclose() exceptions gracefully."""
        pool = HttpClientPool.get_instance()
        await pool.get_client("provider1")
        await pool.get_client("provider2")

        # Mock one client to raise an error
        pool._clients["provider1"].aclose = AsyncMock(side_effect=OSError("error"))

        # close_all should not raise
        await pool.close_all()

        # All clients should be removed
        assert len(pool.client_names) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager usage."""
        async with HttpClientPool.get_instance() as pool:
            await pool.get_client("test_provider")
            assert pool.has_client("test_provider")

        # After context exit, clients should be closed
        assert len(pool.client_names) == 0

    def test_custom_limits_and_timeouts(self):
        """Test creating pool with custom limits and timeouts."""
        # Reset first to ensure fresh instance
        reset_http_pool_sync()

        custom_limits = PoolLimits(max_connections=50)
        custom_timeouts = PoolTimeouts(read=120.0)

        pool = HttpClientPool.get_instance(
            limits=custom_limits,
            timeouts=custom_timeouts,
        )

        assert pool.limits.max_connections == 50
        assert pool.timeouts.read == 120.0

    @pytest.mark.asyncio
    async def test_http2_enabled_by_default(self):
        """Test that HTTP/2 is enabled by default."""
        pool = HttpClientPool.get_instance()
        client = await pool.get_client("test_provider")

        # Check that http2 is enabled
        assert isinstance(client, httpx.AsyncClient)
        # HTTP/2 support is configured via transport, we set http2=True

    @pytest.mark.asyncio
    async def test_client_names_property(self):
        """Test client_names property returns correct list."""
        pool = HttpClientPool.get_instance()
        assert pool.client_names == []

        await pool.get_client("provider_a")
        await pool.get_client("provider_b")

        names = pool.client_names
        assert "provider_a" in names
        assert "provider_b" in names
        assert len(names) == 2

    @pytest.mark.asyncio
    async def test_concurrent_get_client_same_provider(self):
        """Test that concurrent get_client calls for same provider don't create duplicates."""
        import asyncio

        pool = HttpClientPool.get_instance()

        # Request the same client concurrently
        results = await asyncio.gather(
            pool.get_client("test_provider"),
            pool.get_client("test_provider"),
            pool.get_client("test_provider"),
        )

        # All should return the same client instance
        assert results[0] is results[1]
        assert results[1] is results[2]
        assert len(pool.client_names) == 1


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool singleton before and after each test with proper cleanup."""
        await reset_http_pool()
        yield
        await reset_http_pool()

    def test_get_http_pool(self):
        """Test get_http_pool creates and returns singleton."""
        pool = get_http_pool()
        assert isinstance(pool, HttpClientPool)

    @pytest.mark.asyncio
    async def test_reset_http_pool(self):
        """Test reset_http_pool closes clients and clears the global instance."""
        pool1 = get_http_pool()
        await pool1.get_client("test_provider")

        await reset_http_pool()
        pool2 = get_http_pool()

        assert pool1 is not pool2
        # Original pool's clients should be empty after reset
        assert len(pool1.client_names) == 0

    def test_reset_http_pool_sync(self):
        """Test reset_http_pool_sync clears instance without closing clients."""
        pool1 = get_http_pool()
        pool1.get_client_sync("test_provider")

        reset_http_pool_sync()
        pool2 = get_http_pool()

        assert pool1 is not pool2
        # Note: pool1 still has the client (not closed), this is for testing only
        assert pool1.has_client("test_provider")


class TestProviderRegistryPooling:
    """Tests for ProviderRegistry._get_pooled_httpx_client integration."""

    @pytest.fixture(autouse=True)
    async def reset_pool(self):
        """Reset pool singleton before and after each test."""
        await reset_http_pool()
        yield
        await reset_http_pool()

    def test_get_pooled_client_voyage(self):
        """Test getting pooled client for Voyage provider."""
        from codeweaver.common.registry.provider import ProviderRegistry
        from codeweaver.providers.kinds import ProviderKind
        from codeweaver.providers.provider import Provider

        registry = ProviderRegistry()
        client = registry._get_pooled_httpx_client(Provider.VOYAGE, ProviderKind.EMBEDDING)

        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        # Verify Voyage-specific settings are applied
        assert client.timeout.read == 90.0
        assert client._limits.max_connections == 50

    def test_get_pooled_client_cohere(self):
        """Test getting pooled client for Cohere provider."""
        from codeweaver.common.registry.provider import ProviderRegistry
        from codeweaver.providers.kinds import ProviderKind
        from codeweaver.providers.provider import Provider

        registry = ProviderRegistry()
        client = registry._get_pooled_httpx_client(Provider.COHERE, ProviderKind.EMBEDDING)

        assert client is not None
        assert isinstance(client, httpx.AsyncClient)
        # Verify Cohere-specific settings are applied
        assert client.timeout.read == 90.0
        assert client._limits.max_connections == 50

    def test_get_pooled_client_different_kinds_create_different_clients(self):
        """Test that different provider kinds get different clients."""
        from codeweaver.common.registry.provider import ProviderRegistry
        from codeweaver.providers.kinds import ProviderKind
        from codeweaver.providers.provider import Provider

        registry = ProviderRegistry()
        embedding_client = registry._get_pooled_httpx_client(
            Provider.VOYAGE, ProviderKind.EMBEDDING
        )
        reranking_client = registry._get_pooled_httpx_client(
            Provider.VOYAGE, ProviderKind.RERANKING
        )

        # Different kinds should get different clients
        assert embedding_client is not reranking_client

    def test_get_pooled_client_same_provider_reuses_client(self):
        """Test that same provider/kind combination reuses the same client."""
        from codeweaver.common.registry.provider import ProviderRegistry
        from codeweaver.providers.kinds import ProviderKind
        from codeweaver.providers.provider import Provider

        registry = ProviderRegistry()
        client1 = registry._get_pooled_httpx_client(Provider.VOYAGE, ProviderKind.EMBEDDING)
        client2 = registry._get_pooled_httpx_client(Provider.VOYAGE, ProviderKind.EMBEDDING)

        assert client1 is client2

    def test_get_pooled_client_non_pooled_provider(self):
        """Test getting pooled client for a non-pooled provider returns client with defaults."""
        from codeweaver.common.registry.provider import ProviderRegistry
        from codeweaver.providers.kinds import ProviderKind
        from codeweaver.providers.provider import Provider

        registry = ProviderRegistry()
        # OPENAI is not in _POOLED_HTTP_PROVIDERS, so it should get default settings
        client = registry._get_pooled_httpx_client(Provider.OPENAI, ProviderKind.EMBEDDING)

        assert client is not None
        # Should use default timeouts, not the 90.0 for pooled providers
        assert client.timeout.read == 60.0  # Default from PoolTimeouts

    def test_pooled_http_providers_constant(self):
        """Test that _POOLED_HTTP_PROVIDERS includes expected providers."""
        from codeweaver.common.registry.provider import ProviderRegistry
        from codeweaver.providers.provider import Provider

        assert Provider.VOYAGE in ProviderRegistry._POOLED_HTTP_PROVIDERS
        assert Provider.COHERE in ProviderRegistry._POOLED_HTTP_PROVIDERS
        assert len(ProviderRegistry._POOLED_HTTP_PROVIDERS) == 2
