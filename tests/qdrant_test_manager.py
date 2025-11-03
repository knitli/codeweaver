# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Qdrant test instance management for reliable integration testing.

This module provides infrastructure for setting up and managing Qdrant instances
specifically for integration testing, with features for:
- Automatic port detection and availability checking
- Docker auto-start with WSL/Windows support
- Test-specific environment variables (prevent pollution from other instances)
- Isolated test collections with proper cleanup
- Optional authentication support for testing auth scenarios
- Prevention of interference with existing Qdrant instances
"""

import asyncio
import os
import platform
import socket
import subprocess
import time

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from uuid import uuid4

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels


# ===========================================================================
# Docker Utilities
# ===========================================================================


def _is_wsl() -> bool:
    """Detect if running in WSL (Windows Subsystem for Linux).

    Returns:
        True if running in WSL, False otherwise
    """
    try:
        # Check for WSL in /proc/version
        with open("/proc/version", encoding="utf-8") as f:
            return "microsoft" in f.read().lower() or "wsl" in f.read().lower()
    except Exception:
        return False


def _get_docker_command() -> str:
    """Get the appropriate docker command for the current platform.

    Returns:
        Docker command to use ('docker' or 'docker.exe')
    """
    if _is_wsl():
        # In WSL, try docker.exe first (Windows Docker), fall back to docker
        if (
            subprocess.run(["which", "docker.exe"], capture_output=True, check=False).returncode
            == 0
        ):
            return "docker.exe"
    return "docker"


def _is_docker_available() -> bool:
    """Check if Docker is available and running.

    Returns:
        True if Docker is available, False otherwise
    """
    docker_cmd = _get_docker_command()
    try:
        result = subprocess.run([docker_cmd, "info"], capture_output=True, timeout=5, check=False)
    except Exception:
        return False
    else:
        return result.returncode == 0


def _find_qdrant_container(container_name: str) -> str | None:
    """Find a running Qdrant container by name.

    Args:
        container_name: Name of the container to find

    Returns:
        Container ID if found and running, None otherwise
    """
    docker_cmd = _get_docker_command()
    try:
        result = subprocess.run(
            [docker_cmd, "ps", "-q", "-f", f"name={container_name}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _start_qdrant_container(
    *, port: int = 6333, container_name: str = "qdrant-test", image: str = "qdrant/qdrant:latest"
) -> bool:
    """Start a Qdrant Docker container for testing.

    Args:
        port: Host port to bind to (default: 6333)
        container_name: Name for the container (default: qdrant-test)
        image: Docker image to use (default: qdrant/qdrant:latest)

    Returns:
        True if container started successfully, False otherwise
    """
    docker_cmd = _get_docker_command()

    # Check if container already exists (stopped)
    try:
        result = subprocess.run(
            [docker_cmd, "ps", "-a", "-q", "-f", f"name={container_name}"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Container exists, try to start it
            subprocess.run(
                [docker_cmd, "start", container_name], capture_output=True, timeout=10, check=False
            )
            # Wait for startup
            time.sleep(2)
            return _find_qdrant_container(container_name) is not None
    except Exception:
        pass

    # Create new container
    try:
        subprocess.run(
            [docker_cmd, "run", "-d", "--name", container_name, "-p", f"{port}:6333", image],
            capture_output=True,
            timeout=30,
            check=False,
        )
        # Wait for Qdrant to initialize
        time.sleep(3)
        return _find_qdrant_container(container_name) is not None
    except Exception:
        return False


def _stop_qdrant_container(container_name: str) -> bool:
    """Stop a Qdrant Docker container.

    Args:
        container_name: Name of the container to stop

    Returns:
        True if container stopped successfully, False otherwise
    """
    docker_cmd = _get_docker_command()
    try:
        subprocess.run(
            [docker_cmd, "stop", container_name], capture_output=True, timeout=10, check=False
        )
    except Exception:
        return False
    else:
        return True


def _remove_qdrant_container(container_name: str) -> bool:
    """Remove a Qdrant Docker container.

    Args:
        container_name: Name of the container to remove

    Returns:
        True if container removed successfully, False otherwise
    """
    docker_cmd = _get_docker_command()
    try:
        subprocess.run(
            [docker_cmd, "rm", "-f", container_name], capture_output=True, timeout=10, check=False
        )
    except Exception:
        return False
    else:
        return True


# ===========================================================================
# QdrantTestManager
# ===========================================================================


class QdrantTestManager:
    """Manages Qdrant test instances with isolation and cleanup.

    Provides:
    - Test-specific environment variables (prevent pollution from other instances)
    - Docker auto-start with WSL/Windows support
    - Port availability checking (won't interfere with existing instances)
    - Unique collection names per test
    - Automatic cleanup after tests
    - Optional authentication configuration
    - Connection validation

    Test-Specific Environment Variables:
    - QDRANT_TEST_URL: Direct URL override (highest priority)
    - QDRANT_TEST_HOST: Test host (default: localhost)
    - QDRANT_TEST_PORT: Test port override
    - QDRANT_TEST_API_KEY: Test-specific API key
    - QDRANT_TEST_SKIP_DOCKER: Set to '1' or 'true' to disable Docker auto-start
    - QDRANT_TEST_IMAGE: Custom Docker image (default: qdrant/qdrant:latest)
    - QDRANT_TEST_CONTAINER_NAME: Custom container name (default: qdrant-test)
    """

    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        prefer_grpc: bool = False,
        api_key: str | None = None,
        storage_path: Path | None = None,
        timeout: float = 30.0,
        auto_start_docker: bool = True,
    ):
        """Initialize Qdrant test manager.

        Args:
            host: Qdrant host (default: from QDRANT_TEST_HOST or 'localhost')
            port: Qdrant port (default: from QDRANT_TEST_PORT or auto-detect)
            prefer_grpc: Whether to prefer gRPC over HTTP
            api_key: Optional API key (default: from QDRANT_TEST_API_KEY)
            storage_path: Optional storage path for persistent collections
            timeout: Connection timeout in seconds
            auto_start_docker: Whether to auto-start Docker if no instance found
                (can be disabled via QDRANT_TEST_SKIP_DOCKER env var)
        """
        # Read test-specific environment variables (prevent pollution)
        env_url = os.getenv("QDRANT_TEST_URL")
        env_host = os.getenv("QDRANT_TEST_HOST", "localhost")
        env_port = os.getenv("QDRANT_TEST_PORT")
        env_api_key = os.getenv("QDRANT_TEST_API_KEY")
        env_skip_docker = os.getenv("QDRANT_TEST_SKIP_DOCKER", "").lower() in ("1", "true", "yes")

        # Priority: explicit args > env vars > defaults
        self.host = host or env_host
        self.api_key = api_key or env_api_key
        self.prefer_grpc = prefer_grpc
        self.storage_path = storage_path
        self.timeout = timeout
        self.auto_start_docker = auto_start_docker and not env_skip_docker

        # Container settings for Docker auto-start
        self.docker_image = os.getenv("QDRANT_TEST_IMAGE", "qdrant/qdrant:latest")
        self.container_name = os.getenv("QDRANT_TEST_CONTAINER_NAME", "qdrant-test")
        self._docker_started = False

        # Handle URL override
        if env_url:
            # Parse URL to extract host and port
            # Format: http://host:port or https://host:port
            url_parts = env_url.replace("http://", "").replace("https://", "").split(":")
            if len(url_parts) == 2:
                self.host = url_parts[0]
                self.port = int(url_parts[1].split("/")[0])  # Remove any path
            else:
                self.port = (
                    port or (int(env_port) if env_port else None) or self._find_or_start_qdrant()
                )
        else:
            self.port = (
                port or (int(env_port) if env_port else None) or self._find_or_start_qdrant()
            )

        self._client: AsyncQdrantClient | None = None
        self._collections_created: set[str] = set()

    def _find_or_start_qdrant(self) -> int:
        """Find a running Qdrant instance or start one via Docker.

        Returns:
            Port number of the Qdrant instance

        Raises:
            RuntimeError: If no instance found and Docker auto-start disabled or failed
        """
        # First try to find existing instance
        try:
            return self._find_qdrant_instance()
        except RuntimeError:
            pass

        # No instance found, try Docker auto-start if enabled
        if self.auto_start_docker and _is_docker_available():
            # Try to find a free port starting from 6333
            test_port = 6333
            while test_port <= 6400:
                if not self._check_port_in_use(self.host, test_port):
                    # Port is free, try to start container
                    if _start_qdrant_container(
                        port=test_port, container_name=self.container_name, image=self.docker_image
                    ):
                        self._docker_started = True
                        return test_port
                test_port += 1

        # Failed to find or start instance
        platform_info = "WSL" if _is_wsl() else platform.system()
        docker_available = "available" if _is_docker_available() else "NOT available"

        msg = (
            f"No running Qdrant instance found and Docker auto-start failed.\n"
            f"Platform: {platform_info} (Docker {docker_available})\n"
            f"Tried ports: 6333-6400\n\n"
            f"To fix this:\n"
            f"1. Start Qdrant manually: docker run -d -p 6336:6333 qdrant/qdrant:latest\n"
            f"2. Or set QDRANT_TEST_PORT to your running instance port\n"
            f"3. Or install/start Docker for auto-start capability"
        )
        raise RuntimeError(msg)

    @staticmethod
    def _find_qdrant_instance(start: int = 6333, end: int = 6400) -> int:
        """Find a running Qdrant instance in the given port range.

        Scans ports for running Qdrant instances (not free ports).
        Returns the first port that has something listening.
        The actual Qdrant connection check happens in verify_connection().

        Args:
            start: Starting port number (default 6333, standard Qdrant port)
            end: Ending port number (default 6400)

        Returns:
            First port with a service running

        Raises:
            RuntimeError: If no running services found in range
        """
        for port in range(start, end + 1):
            # Check if port is in use (has something listening)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1.0)
                try:
                    result = sock.connect_ex(("localhost", port))
                    if result == 0:
                        # Port has something running - return it
                        # We'll verify it's actually Qdrant in verify_connection()
                        return port
                except Exception:
                    # Connection error, try next port
                    continue

        msg = f"No running services found in port range {start}-{end}"
        raise RuntimeError(msg)

    @staticmethod
    def _check_port_in_use(host: str, port: int) -> bool:
        """Check if a port is in use.

        Args:
            host: Host to check
            port: Port to check

        Returns:
            True if port is in use, False otherwise
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            try:
                result = sock.connect_ex((host, port))
            except Exception:
                return False
            else:
                return result == 0  # Port is in use

    @property
    def url(self) -> str:
        """Get the Qdrant instance URL."""
        return f"http://{self.host}:{self.port}"

    async def _create_client(self) -> AsyncQdrantClient:
        """Create and configure Qdrant client.

        Returns:
            Configured AsyncQdrantClient instance
        """
        client_kwargs = {"url": self.url, "prefer_grpc": self.prefer_grpc, "timeout": self.timeout}

        if self.api_key:
            client_kwargs["api_key"] = self.api_key

        if self.storage_path:
            client_kwargs["path"] = str(self.storage_path)

        return AsyncQdrantClient(**client_kwargs)  # type: ignore

    async def verify_connection(self) -> bool:
        """Verify connection to Qdrant instance.

        Tests if the instance is accessible without authentication.
        If the current port requires auth or isn't Qdrant, returns False.

        Returns:
            True if connection successful, False otherwise
        """
        if not self._check_port_in_use(self.host, self.port):
            return False

        try:
            if self._client is None:
                # Try without API key first to test if unauthenticated access works
                temp_client = AsyncQdrantClient(
                    url=f"http://{self.host}:{self.port}",
                    prefer_grpc=self.prefer_grpc,
                    timeout=2.0,  # Quick timeout for discovery
                )

                # Try to get collections to verify unauthenticated access
                _ = await asyncio.wait_for(temp_client.get_collections(), timeout=2.0)

                # Success! This instance is accessible without auth
                # Now create the real client (with api_key if provided for auth testing)
                await temp_client.close()
                self._client = await self._create_client()
        except Exception:
            # Connection failed - could be auth required, wrong port, or not Qdrant
            return False
        else:
            return True

    async def ensure_client(self) -> AsyncQdrantClient:
        """Ensure client is created and connected.

        Returns:
            Configured AsyncQdrantClient instance

        Raises:
            RuntimeError: If cannot connect to Qdrant
        """
        if self._client is None:
            self._client = await self._create_client()

        if not await self.verify_connection():
            msg = (
                f"Cannot connect to Qdrant at {self.url}. "
                f"Ensure Qdrant is running on port {self.port}. "
                "Start with: docker run -p {port}:6333 qdrant/qdrant:latest"
            )
            raise RuntimeError(msg)

        return self._client

    def create_collection_name(self, prefix: str = "test") -> str:
        """Create a unique collection name for testing.

        Args:
            prefix: Prefix for collection name (default: "test")

        Returns:
            Unique collection name with format: {prefix}-{uuid}
        """
        unique_id = uuid4().hex[:8]
        return f"{prefix}-{unique_id}"

    async def create_collection(
        self,
        collection_name: str,
        *,
        dense_vector_size: int = 768,
        sparse_vector_size: int | None = None,
        dense_vector_name: str = "dense",
        sparse_vector_name: str = "sparse",
        distance: qmodels.Distance = qmodels.Distance.COSINE,
    ) -> str:
        """Create a test collection with specified vector configuration.

        Args:
            collection_name: Name for the collection
            dense_vector_size: Size of dense vectors (default: 768)
            sparse_vector_size: Size of sparse vectors (None = no sparse vectors)
            dense_vector_name: Name for dense vector (default: "dense")
            sparse_vector_name: Name for sparse vector (default: "sparse")
            distance: Distance metric for vectors (default: COSINE)

        Returns:
            Collection name

        Raises:
            RuntimeError: If client not connected
        """
        client = await self.ensure_client()

        # Configure vectors
        vectors_config = {
            dense_vector_name: qmodels.VectorParams(size=dense_vector_size, distance=distance)
        }

        # Add sparse vector if requested
        sparse_vectors_config = None
        if sparse_vector_size is not None:
            sparse_vectors_config = {
                sparse_vector_name: qmodels.SparseVectorParams(index=qmodels.SparseIndexParams())
            }

        # Create collection
        _ = await client.create_collection(
            collection_name=collection_name,
            vectors_config=vectors_config,
            sparse_vectors_config=sparse_vectors_config,
        )

        # Track for cleanup
        self._collections_created.add(collection_name)

        return collection_name

    async def delete_collection(self, collection_name: str) -> None:
        """Delete a collection.

        Args:
            collection_name: Name of collection to delete
        """
        if self._client is None:
            return

        with suppress(Exception):
            _ = await self._client.delete_collection(collection_name=collection_name)
            self._collections_created.discard(collection_name)

    async def cleanup_all_collections(self) -> None:
        """Clean up all collections created by this manager."""
        if self._client is None:
            return

        for collection_name in list(self._collections_created):
            await self.delete_collection(collection_name)

    async def close(self) -> None:
        """Close client connection and cleanup."""
        await self.cleanup_all_collections()

        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass
            finally:
                self._client = None

        # Cleanup Docker container if we started it
        if self._docker_started:
            _stop_qdrant_container(self.container_name)
            _remove_qdrant_container(self.container_name)
            self._docker_started = False

    @asynccontextmanager
    async def collection_context(
        self,
        prefix: str = "test",
        *,
        dense_vector_size: int = 768,
        sparse_vector_size: int | None = None,
    ) -> AsyncIterator[tuple[AsyncQdrantClient, str]]:
        """Context manager for a test collection with automatic cleanup.

        Args:
            prefix: Prefix for collection name
            dense_vector_size: Size of dense vectors
            sparse_vector_size: Size of sparse vectors (None = no sparse)

        Yields:
            Tuple of (client, collection_name)

        Example:
            async with manager.collection_context("mytest") as (client, collection):
                # Use client and collection
                await client.upsert(collection, points=[...])
                # Cleanup automatic on exit
        """
        collection_name = self.create_collection_name(prefix)

        try:
            _ = await self.create_collection(
                collection_name,
                dense_vector_size=dense_vector_size,
                sparse_vector_size=sparse_vector_size,
            )

            client = await self.ensure_client()
            yield client, collection_name

        finally:
            await self.delete_collection(collection_name)


# ===========================================================================
# pytest fixtures
# ===========================================================================


def get_qdrant_test_config(
    *, collection_suffix: str = "", port: int | None = None, api_key: str | None = None
) -> dict:
    """Get test-specific Qdrant configuration.

    This is a convenience function for creating Qdrant config dicts
    compatible with QdrantVectorStoreProvider.

    Args:
        collection_suffix: Optional suffix for collection name
        port: Qdrant port (default: auto-detect)
        api_key: Optional API key for authentication

    Returns:
        Configuration dict for QdrantVectorStoreProvider
    """
    manager = QdrantTestManager(port=port, api_key=api_key)

    config = {
        "url": manager.url,
        "prefer_grpc": False,
        "collection_name": manager.create_collection_name(
            f"codeweaver-test-{collection_suffix}" if collection_suffix else "codeweaver-test"
        ),
    }

    if api_key:
        config["api_key"] = api_key

    return config
