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
    client = pool.get_client('voyage', read_timeout=90.0)

    # Cleanup on shutdown
    await pool.close_all()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar

import httpx


logger = logging.getLogger(__name__)


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

    Example:
        pool = HttpClientPool.get_instance()
        client = pool.get_client('voyage', max_connections=50, read_timeout=90.0)
        # Use client for API calls...
        await pool.close_all()  # Cleanup on shutdown
    """

    _instance: ClassVar[HttpClientPool | None] = None

    limits: PoolLimits = field(default_factory=PoolLimits)
    timeouts: PoolTimeouts = field(default_factory=PoolTimeouts)
    _clients: dict[str, httpx.AsyncClient] = field(default_factory=dict, repr=False)

    @classmethod
    def get_instance(
        cls,
        limits: PoolLimits | None = None,
        timeouts: PoolTimeouts | None = None,
    ) -> HttpClientPool:
        """Get or create the singleton HttpClientPool instance.

        Args:
            limits: Optional connection pool limits (only used on first call).
            timeouts: Optional timeout configuration (only used on first call).

        Returns:
            The singleton HttpClientPool instance.
        """
        if cls._instance is None:
            cls._instance = cls(
                limits=limits or PoolLimits(),
                timeouts=timeouts or PoolTimeouts(),
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
        cls._instance = None

    def get_client(self, name: str, **overrides: Any) -> httpx.AsyncClient:
        """Get or create a pooled HTTP client for a specific provider.

        Clients are cached by name and reused for subsequent requests.
        Override parameters allow per-provider customization of limits and timeouts.

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
        if name not in self._clients:
            limits = httpx.Limits(
                max_connections=overrides.get("max_connections", self.limits.max_connections),
                max_keepalive_connections=overrides.get(
                    "max_keepalive_connections",
                    self.limits.max_keepalive_connections,
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

            logger.info(
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
        return name in self._clients

    @property
    def client_names(self) -> list[str]:
        """Get list of all provider names with active clients."""
        return list(self._clients.keys())

    async def close_client(self, name: str) -> bool:
        """Close a specific provider's HTTP client.

        Args:
            name: Provider name whose client to close.

        Returns:
            True if client was closed, False if no client existed.
        """
        if name in self._clients:
            try:
                await self._clients[name].aclose()
                del self._clients[name]
                logger.info("Closed HTTP client pool for %s", name)
                return True
            except Exception:
                logger.exception("Error closing HTTP client pool for %s", name)
                # Still remove from dict to prevent reuse of broken client
                self._clients.pop(name, None)
        return False

    async def close_all(self) -> None:
        """Close all pooled clients (cleanup on shutdown).

        This method should be called during application shutdown to properly
        close all HTTP connections and release resources.
        """
        client_names = list(self._clients.keys())
        for name in client_names:
            try:
                await self._clients[name].aclose()
                logger.debug("Closed HTTP client pool for %s", name)
            except Exception:
                logger.exception("Error closing HTTP client pool for %s", name)
        self._clients.clear()

        if client_names:
            logger.info("Closed %d HTTP client pool(s)", len(client_names))

    async def __aenter__(self) -> HttpClientPool:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit - closes all clients."""
        await self.close_all()


# Module-level singleton accessor
_pool_instance: HttpClientPool | None = None


def get_http_pool() -> HttpClientPool:
    """Get the global HTTP client pool instance.

    This is the recommended way to access the HTTP client pool throughout
    the application. It returns the singleton instance, creating it if needed.

    Returns:
        The singleton HttpClientPool instance.
    """
    global _pool_instance
    if _pool_instance is None:
        _pool_instance = HttpClientPool.get_instance()
    return _pool_instance


def reset_http_pool() -> None:
    """Reset the global HTTP client pool (primarily for testing).

    Warning: This does NOT close existing clients. Call close_all() first
    if you need to clean up resources.
    """
    global _pool_instance
    _pool_instance = None
    HttpClientPool.reset_instance()


__all__ = (
    "HttpClientPool",
    "PoolLimits",
    "PoolTimeouts",
    "get_http_pool",
    "reset_http_pool",
)
