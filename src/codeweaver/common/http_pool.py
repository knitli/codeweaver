# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""HTTP client connection pool manager for CodeWeaver providers.

This module provides centralized HTTP client pooling for providers that use httpx,
including Voyage AI, Cohere, and other HTTP-based API providers. Connection pooling
reduces overhead from repeated TCP handshakes and TLS negotiations, improving
performance and reliability during high-load operations like indexing.

Usage:
    from codeweaver.common.http_pool import HttpClientPool, get_http_pool

    # Get singleton instance
    pool = get_http_pool()

    # Get a pooled client for a specific provider
    client = await pool.get_client('voyage', read_timeout=90.0)

    # Cleanup on shutdown
    await pool.close_all()

Thread Safety:
    - Singleton initialization: Thread-safe via double-checked locking (threading.Lock)
    - Async client creation (get_client): Coroutine-safe via asyncio.Lock
    - Sync client creation (get_client_sync): Thread-safe via threading.Lock
    - WARNING: Synchronous and asynchronous methods should NOT be mixed. The locking strategy does not protect against concurrent access from both threads and coroutines. Only use sync methods in a purely threaded context, and async methods in a purely async context.
    - All methods can be called concurrently within their respective contexts (sync or async) without creating duplicate clients.
"""

from __future__ import annotations

import asyncio
import logging
import threading

from dataclasses import dataclass, field
from typing import Any, ClassVar, Self

import httpx


logger = logging.getLogger(__name__)

# Module-level lock for thread-safe singleton initialization
_instance_lock = threading.Lock()


@dataclass(frozen=True)
class PoolLimits:
    """HTTP connection pool limits configuration.

    Attributes:
        max_connections: Maximum total connections across all hosts.
        max_keepalive_connections: Maximum persistent connections to keep alive.
        keepalive_expiry: Seconds to keep idle connections alive.
    """

    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: float = 5.0


@dataclass(frozen=True)
class PoolTimeouts:
    """HTTP timeout configuration for pooled clients.

    Attributes:
        connect: Connection establishment timeout in seconds.
        read: Read timeout in seconds (longer for embedding/vector operations).
        write: Write timeout in seconds.
        pool: Pool acquire timeout in seconds.
    """

    connect: float = 10.0
    read: float = 60.0  # Longer for embedding/vector operations
    write: float = 10.0
    pool: float = 5.0


@dataclass
class HttpClientPool:
    """Singleton HTTP client pool manager for provider connections.

    Manages a collection of httpx.AsyncClient instances, one per provider,
    with configurable connection limits and timeouts. Clients are created
    lazily on first request and reused for subsequent requests.

    The pool supports HTTP/2 by default for better multiplexing on modern APIs.

    Thread Safety:
        Client creation is protected by an asyncio.Lock to prevent race conditions
        when multiple coroutines request the same client simultaneously.

    Example:
        pool = HttpClientPool.get_instance()
        client = await pool.get_client('voyage', max_connections=50, read_timeout=90.0)
        # Use client for API calls...
        await pool.close_all()  # Cleanup on shutdown
    """

    _instance: ClassVar[HttpClientPool | None] = None

    limits: PoolLimits = field(default_factory=PoolLimits)
    timeouts: PoolTimeouts = field(default_factory=PoolTimeouts)
    _clients: dict[str, httpx.AsyncClient] = field(default_factory=dict, repr=False)
    # Note: _async_lock is created lazily to avoid event loop binding issues.
    # asyncio.Lock is bound to the event loop it's created in, so we create it
    # on first use in get_client() to ensure it's bound to the correct loop.
    _async_lock: asyncio.Lock | None = field(default=None, repr=False)
    _sync_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def get_instance(
        cls, limits: PoolLimits | None = None, timeouts: PoolTimeouts | None = None
    ) -> HttpClientPool:
        """Get or create the singleton HttpClientPool instance.

        This method is thread-safe via double-checked locking pattern.

        Args:
            limits: Optional connection pool limits (only used on first call).
            timeouts: Optional timeout configuration (only used on first call).

        Returns:
            The singleton HttpClientPool instance.
        """
        # Fast path: instance already exists
        if cls._instance is not None:
            return cls._instance

        # Slow path: acquire lock and double-check
        with _instance_lock:
            if cls._instance is None:
                cls._instance = cls(
                    limits=limits or PoolLimits(), timeouts=timeouts or PoolTimeouts()
                )
                logger.debug(
                    "Created HttpClientPool singleton with limits=%s, timeouts=%s",
                    cls._instance.limits,
                    cls._instance.timeouts,
                )
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (primarily for testing)."""
        with _instance_lock:
            cls._instance = None

    async def get_client(self, name: str, **overrides: Any) -> httpx.AsyncClient:
        """Get or create a pooled HTTP client for a specific provider.

        Clients are cached by name and reused for subsequent requests.
        Override parameters allow per-provider customization of limits and timeouts.

        This method is coroutine-safe: concurrent calls for the same provider
        will not create duplicate clients.

        Note:
            Clients are cached by name only, not by override parameters. If the same
            provider name is requested multiple times with different overrides, the
            client created on the first call will be returned for all subsequent calls.
            This is intentional for connection pooling - each provider should use
            consistent settings. The ProviderRegistry ensures consistent overrides
            per provider type.

        Args:
            name: Provider name (e.g., 'voyage', 'cohere', 'qdrant').
            **overrides: Override default limits/timeouts for this client:
                - max_connections: int
                - max_keepalive_connections: int
                - keepalive_expiry: float
                - connect_timeout: float
                - read_timeout: float
                - write_timeout: float
                - pool_timeout: float
                - http2: bool (default True)

        Returns:
            Configured httpx.AsyncClient with connection pooling.
        """
        # Fast path: return existing client without lock
        # Use try-except to handle race condition where client could be removed
        # between check and return
        try:
            return self._clients[name]
        except KeyError:
            pass  # Continue to locked creation

        # Lazily create asyncio.Lock on first use to avoid event loop binding issues.
        # asyncio.Lock must be created in the same event loop where it will be used.
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()

        # Slow path: acquire lock for client creation
        async with self._async_lock:
            # Double-check after acquiring lock
            if name in self._clients:
                return self._clients[name]

            limits = httpx.Limits(
                max_connections=overrides.get("max_connections", self.limits.max_connections),
                max_keepalive_connections=overrides.get(
                    "max_keepalive_connections", self.limits.max_keepalive_connections
                ),
                keepalive_expiry=overrides.get("keepalive_expiry", self.limits.keepalive_expiry),
            )

            timeout = httpx.Timeout(
                connect=overrides.get("connect_timeout", self.timeouts.connect),
                read=overrides.get("read_timeout", self.timeouts.read),
                write=overrides.get("write_timeout", self.timeouts.write),
                pool=overrides.get("pool_timeout", self.timeouts.pool),
            )

            self._clients[name] = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
                http2=overrides.get("http2", True),  # Enable HTTP/2 for better multiplexing
            )

            logger.debug(
                "Created HTTP client pool for %s: max_conn=%d, keepalive=%d, read_timeout=%.1fs",
                name,
                limits.max_connections,
                limits.max_keepalive_connections,
                timeout.read,
            )

        return self._clients[name]

    def get_client_sync(self, name: str, **overrides: Any) -> httpx.AsyncClient:
        """Synchronous version of get_client for non-async contexts.

        This method is thread-safe via double-checked locking pattern.
        It can be called concurrently from multiple threads during provider
        initialization without creating duplicate clients.

        Note:
            Clients are cached by name only, not by override parameters. If the same
            provider name is requested multiple times with different overrides, the
            client created on the first call will be returned for all subsequent calls.
            This is intentional for connection pooling - each provider should use
            consistent settings.

        Warning:
            Synchronous and asynchronous methods should NOT be mixed. The locking
            strategy does not protect against concurrent access from both threads
            and coroutines. Only use sync methods in a purely threaded context,
            and async methods in a purely async context.

        Args:
            name: Provider name (e.g., 'voyage', 'cohere', 'qdrant').
            **overrides: Override default limits/timeouts for this client.

        Returns:
            Configured httpx.AsyncClient with connection pooling.
        """
        # Fast path: client already exists
        # Use try-except to handle race condition where client could be removed
        # between check and return
        try:
            return self._clients[name]
        except KeyError:
            pass  # Continue to locked creation

        # Slow path: acquire lock and double-check
        with self._sync_lock:
            if name not in self._clients:
                limits = httpx.Limits(
                    max_connections=overrides.get("max_connections", self.limits.max_connections),
                    max_keepalive_connections=overrides.get(
                        "max_keepalive_connections", self.limits.max_keepalive_connections
                    ),
                    keepalive_expiry=overrides.get(
                        "keepalive_expiry", self.limits.keepalive_expiry
                    ),
                )

                timeout = httpx.Timeout(
                    connect=overrides.get("connect_timeout", self.timeouts.connect),
                    read=overrides.get("read_timeout", self.timeouts.read),
                    write=overrides.get("write_timeout", self.timeouts.write),
                    pool=overrides.get("pool_timeout", self.timeouts.pool),
                )

                self._clients[name] = httpx.AsyncClient(
                    limits=limits, timeout=timeout, http2=overrides.get("http2", True)
                )

                logger.debug(
                    "Created HTTP client pool for %s: max_conn=%d, keepalive=%d, read_timeout=%.1fs",
                    name,
                    limits.max_connections,
                    limits.max_keepalive_connections,
                    timeout.read,
                )

        return self._clients[name]

    def has_client(self, name: str) -> bool:
        """Check if a client exists for the given provider name.

        Args:
            name: Provider name to check.

        Returns:
            True if a client exists for this provider.
        """
        with self._sync_lock:
            return name in self._clients

    @property
    def client_names(self) -> list[str]:
        """Get list of all provider names with active clients."""
        with self._sync_lock:
            return list(self._clients.keys())

    async def close_client(self, name: str) -> bool:
        """Close a specific provider's HTTP client.

        Args:
            name: Provider name whose client to close.

        Returns:
            True if client was closed, False if no client existed.
        """
        # Ensure async lock exists
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()

        async with self._async_lock:
            if name in self._clients:
                client = self._clients.pop(name)
                try:
                    await client.aclose()
                    logger.debug("Closed HTTP client pool for %s", name)
                except (httpx.HTTPError, OSError) as e:
                    logger.warning("Error closing HTTP client pool for %s: %s", name, e)
                    # Client already removed from dict above
                else:
                    return True
            return False

    async def close_all(self) -> None:
        """Close all pooled clients (cleanup on shutdown).

        This method should be called during application shutdown to properly
        close all HTTP connections and release resources.
        """
        # Ensure async lock exists
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()

        async with self._async_lock:
            client_names = list(self._clients.keys())
            for name in client_names:
                client = self._clients.pop(name, None)
                if client is None:
                    continue
                try:
                    await client.aclose()
                    logger.debug("Closed HTTP client pool for %s", name)
                except (httpx.HTTPError, OSError) as e:
                    logger.warning("Error closing HTTP client pool for %s: %s", name, e)

            if client_names:
                logger.debug("Closed %d HTTP client pool(s)", len(client_names))

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Async context manager exit - closes all clients."""
        await self.close_all()


def get_http_pool() -> HttpClientPool:
    """Get the global HTTP client pool instance.

    This is the recommended way to access the HTTP client pool throughout
    the application. It returns the singleton instance, creating it if needed.

    Returns:
        The singleton HttpClientPool instance.
    """
    return HttpClientPool.get_instance()


async def reset_http_pool() -> None:
    """Reset the global HTTP client pool (primarily for testing).

    This async function properly closes all existing clients before resetting
    the singleton instance to prevent resource leaks.
    """
    instance = HttpClientPool._instance
    if instance is not None:
        await instance.close_all()
    HttpClientPool.reset_instance()


def reset_http_pool_sync() -> None:
    """Synchronous reset for testing fixtures (no cleanup).

    Warning: This does NOT close existing clients. Use reset_http_pool()
    if you need to clean up resources properly.
    """
    HttpClientPool.reset_instance()


__all__ = (
    "HttpClientPool",
    "PoolLimits",
    "PoolTimeouts",
    "get_http_pool",
    "reset_http_pool",
    "reset_http_pool_sync",
)
