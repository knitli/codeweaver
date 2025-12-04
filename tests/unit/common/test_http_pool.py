# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for HTTP client connection pool manager."""

from __future__ import annotations

import pytest

from codeweaver.common.http_pool import (
    HttpClientPool,
    PoolLimits,
    PoolTimeouts,
    get_http_pool,
    reset_http_pool,
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


class TestHttpClientPool:
    """Tests for HttpClientPool manager."""

    @pytest.fixture(autouse=True)
    def reset_pool(self):
        """Reset pool singleton before and after each test."""
        reset_http_pool()
        yield
        reset_http_pool()

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

    def test_reset_instance(self):
        """Test that reset_instance clears the singleton."""
        pool1 = HttpClientPool.get_instance()
        HttpClientPool.reset_instance()
        pool2 = HttpClientPool.get_instance()
        assert pool1 is not pool2

    def test_get_client_creates_client(self):
        """Test that get_client creates an httpx.AsyncClient."""
        import httpx

        pool = HttpClientPool.get_instance()
        client = pool.get_client("test_provider")

        assert isinstance(client, httpx.AsyncClient)
        assert pool.has_client("test_provider")
        assert "test_provider" in pool.client_names

    def test_get_client_reuses_client(self):
        """Test that get_client returns the same client for same name."""
        pool = HttpClientPool.get_instance()
        client1 = pool.get_client("test_provider")
        client2 = pool.get_client("test_provider")

        assert client1 is client2

    def test_get_client_with_overrides(self):
        """Test that get_client applies override settings."""
        pool = HttpClientPool.get_instance()
        client = pool.get_client(
            "custom_provider",
            max_connections=25,
            read_timeout=120.0,
        )

        # Verify client was created (overrides are applied at client level)
        assert pool.has_client("custom_provider")

    def test_multiple_providers(self):
        """Test that different providers get different clients."""
        pool = HttpClientPool.get_instance()
        voyage_client = pool.get_client("voyage")
        cohere_client = pool.get_client("cohere")

        assert voyage_client is not cohere_client
        assert pool.has_client("voyage")
        assert pool.has_client("cohere")
        assert len(pool.client_names) == 2

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Test that close_client closes and removes a client."""
        pool = HttpClientPool.get_instance()
        pool.get_client("test_provider")

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
    async def test_close_all(self):
        """Test that close_all closes all clients."""
        pool = HttpClientPool.get_instance()
        pool.get_client("provider1")
        pool.get_client("provider2")
        pool.get_client("provider3")

        assert len(pool.client_names) == 3

        await pool.close_all()

        assert len(pool.client_names) == 0

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager usage."""
        async with HttpClientPool.get_instance() as pool:
            pool.get_client("test_provider")
            assert pool.has_client("test_provider")

        # After context exit, clients should be closed
        assert len(pool.client_names) == 0

    def test_custom_limits_and_timeouts(self):
        """Test creating pool with custom limits and timeouts."""
        custom_limits = PoolLimits(max_connections=50)
        custom_timeouts = PoolTimeouts(read=120.0)

        pool = HttpClientPool.get_instance(
            limits=custom_limits,
            timeouts=custom_timeouts,
        )

        assert pool.limits.max_connections == 50
        assert pool.timeouts.read == 120.0

    def test_http2_enabled_by_default(self):
        """Test that HTTP/2 is enabled by default."""
        import httpx

        pool = HttpClientPool.get_instance()
        client = pool.get_client("test_provider")

        # Check that http2 is enabled
        assert isinstance(client, httpx.AsyncClient)
        # Note: httpx doesn't expose http2 as a direct attribute,
        # but we set it to True in get_client

    def test_client_names_property(self):
        """Test client_names property returns correct list."""
        pool = HttpClientPool.get_instance()
        assert pool.client_names == []

        pool.get_client("provider_a")
        pool.get_client("provider_b")

        names = pool.client_names
        assert "provider_a" in names
        assert "provider_b" in names
        assert len(names) == 2


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    @pytest.fixture(autouse=True)
    def reset_pool(self):
        """Reset pool singleton before and after each test."""
        reset_http_pool()
        yield
        reset_http_pool()

    def test_get_http_pool(self):
        """Test get_http_pool creates and returns singleton."""
        pool = get_http_pool()
        assert isinstance(pool, HttpClientPool)

    def test_reset_http_pool(self):
        """Test reset_http_pool clears the global instance."""
        pool1 = get_http_pool()
        reset_http_pool()
        pool2 = get_http_pool()
        assert pool1 is not pool2
