# sourcery skip: no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""In-memory vector store with JSON persistence using Qdrant in-memory mode."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Literal

from anyio import Path as AsyncPath

from codeweaver.core import (
    CodeChunk,
    PersistenceError,
    Provider,
    ProviderError,
    SearchResult,
    StrategizedQuery,
)
from codeweaver.providers import MemoryVectorStoreProviderSettings
from codeweaver.providers.vector_stores.qdrant_base import QdrantBaseProvider


if TYPE_CHECKING:
    from codeweaver.providers.vector_stores.base import MixedQueryInput
    from codeweaver.providers.vector_stores.search import Filter

try:
    from qdrant_client import AsyncQdrantClient
except ImportError as e:
    raise ProviderError(
        "Qdrant client is required for MemoryVectorStoreProvider. Install it with: pip install qdrant-client"
    ) from e

logger = logging.getLogger(__name__)


class MemoryVectorStoreProvider(QdrantBaseProvider):
    """In-memory vector store with persistence for development/testing and local backup.

    Uses Qdrant's in-memory mode (:memory:) with automatic persistence to disk.
    Suitable for small codebases (<10k chunks) and testing scenarios.
    """

    _provider: ClassVar[Literal[Provider.MEMORY]] = Provider.MEMORY
    config: MemoryVectorStoreProviderSettings

    @property
    def base_url(self) -> str | None:
        """Get the base URL for the memory provider - always :memory:."""
        return ":memory:"

    async def _init_provider(self) -> None:
        """Initialize in-memory Qdrant client and restore from disk.

        Raises:
            PersistenceError: Failed to restore from persistence file.
            ValidationError: Persistence file format invalid.
        """
        from codeweaver.core import is_test_environment

        # Logic for auto_persist:
        # 1. If explicitly provided in config, use that value.
        # 2. If not provided, disable in test mode, enable otherwise.
        auto_persist = self.config.in_memory_config.get("auto_persist")
        if auto_persist is None:
            auto_persist = not is_test_environment()

        persist_interval = self.config.in_memory_config.get("persist_interval")
        if persist_interval is None:
            persist_interval = 300

        # Store as private attributes
        object.__setattr__(self, "_persist_path", self.config.in_memory_config.get("persist_path"))
        object.__setattr__(self, "_auto_persist", auto_persist)
        object.__setattr__(self, "_persist_interval", persist_interval)
        object.__setattr__(self, "_periodic_task", None)
        object.__setattr__(self, "_shutdown", False)
        object.__setattr__(self, "_collection_metadata", {})
        object.__setattr__(self, "_collection_metadata_lock", asyncio.Lock())

        import sys

        logger.debug(
            "MemoryVectorStoreProvider._init_provider instance %s with client %s and collection %s",
            id(self),
            id(self.client),
            self.collection_name,
        )
        sys.stdout.flush()

        # Ensure collection exists
        if self.collection_name:
            await self._ensure_collection(self.collection_name)
            logger.debug(
                "MemoryVectorStoreProvider ensured collection %s in client %s",
                self.collection_name,
                id(self.client),
            )
            sys.stdout.flush()
        # Restore from disk if persistence file exists (and not in test mode)
        if not is_test_environment() and await AsyncPath(str(self.persist_path)).exists():
            await self._restore_from_disk()

        # Set up periodic persistence if configured
        if auto_persist:
            periodic_task = asyncio.create_task(self._periodic_persist_task())
            object.__setattr__(self, "_periodic_task", periodic_task)

    @property
    def persist_path(self) -> Path:
        """Get the persistence path for the in-memory store, if set."""
        path = self.config.in_memory_config["persist_path"]
        return path if isinstance(path, Path) else Path(path)

    @property
    def auto_persist(self) -> bool:
        """Get whether auto-persistence is enabled."""
        return self._auto_persist

    async def _persist_to_disk(self) -> None:
        """Persist in-memory state to Qdrant storage directory.

        Raises:
            PersistenceError: Failed to write persistence file.
        """
        # Atomic persistence via temporary directory
        persist_path = AsyncPath(str(self.persist_path))
        temp_path = persist_path.with_suffix(".tmp")
        if temp_path.exists():
            import shutil

            await asyncio.to_thread(shutil.rmtree, str(temp_path))

        try:
            # Initialize persistent client at temp path
            # We use AsyncQdrantClient with path to create local storage
            dest_client = AsyncQdrantClient(path=str(temp_path))

            # Migrate data
            await self.migrate_to(dest_client)

            # Close dest client to release locks
            await dest_client.close()

            # Atomic replace
            if await temp_path.exists():
                import shutil

                if await temp_path.is_dir():
                    await asyncio.to_thread(shutil.rmtree, str(self.persist_path))
                else:
                    await persist_path.unlink()

            await temp_path.rename(str(self.persist_path))
        except Exception as e:
            if await temp_path.exists():
                import shutil
            await asyncio.to_thread(shutil.rmtree, str(temp_path))
            raise PersistenceError(f"Failed to persist to disk: {e}") from e

    async def _restore_from_disk(self) -> None:
        """Restore in-memory state from Qdrant storage directory.

        Raises:
            PersistenceError: Failed to restore from disk.
        """
        persist_path = AsyncPath(str(self.persist_path))
        if not await persist_path.exists():
            return

        # Check if it's a directory
        if await persist_path.is_dir():
            try:
                source_client = AsyncQdrantClient(path=str(self.persist_path))
                await self.migrate_from(source_client)
                await source_client.close()
            except Exception as e:
                raise PersistenceError(f"Failed to restore from disk: {e}") from e
        else:
            logger.warning("Persistence path exists but is not a directory. Skipping restore.")

    async def _periodic_persist_task(self) -> None:
        """Background task for periodic persistence.

        Logs errors but continues running to avoid data loss.
        """
        while not self._shutdown:
            try:
                await asyncio.sleep(self._persist_interval or 300)
                if not self._shutdown:
                    await self._persist_to_disk()
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue to avoid data loss
                logger.warning("Periodic persistence failed", exc_info=True)

    async def close(self) -> None:
        """Close Qdrant client and stop background tasks."""
        if not self.client:
            return

        # check if we are in a test environment
        from codeweaver.core import is_test_environment

        if is_test_environment():
            # In tests, we don't close the shared client as it's used by multiple tests
            return

        # Shutdown sequence
        self._shutdown = True

        # Cancel periodic task
        # ty can't identify the attribute because it's set with object.__setattr__
        if self._periodic_task:
            self._periodic_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._periodic_task

        # Final persistence
        try:
            await self._persist_to_disk()
        except Exception:
            # Log but don't raise on shutdown
            logger.warning("Final persistence on shutdown failed", exc_info=True)

        # Close client
        if self.client:
            await self.client.close()

    async def upsert(self, chunks: list[CodeChunk]) -> None:
        """Insert or update code chunks with hybrid embeddings."""
        logger.debug(
            "MemoryVectorStoreProvider.upsert instance %s to collection: %s with %d chunks",
            id(self),
            self.collection_name,
            len(chunks),
        )
        await super().upsert(chunks)

        # Verify count
        if self.client and self.collection_name:
            info = await self.client.get_collection(self.collection_name)
            logger.debug(
                "Collection %s now has %d points in client %s",
                self.collection_name,
                info.points_count,
                id(self.client),
            )

    async def search(
        self, vector: StrategizedQuery | MixedQueryInput, query_filter: Filter | None = None
    ) -> list[SearchResult]:
        """Search for similar vectors."""
        import sys

        if not self.client:
            await self._initialize()

        if self.client and self.collection_name:
            info = await self.client.get_collection(self.collection_name)
            logger.debug(
                "MemoryVectorStoreProvider.search instance %s in collection: %s (points: %d)",
                id(self),
                self.collection_name,
                info.points_count,
            )
        else:
            logger.debug(
                "MemoryVectorStoreProvider.search instance %s in collection: %s (client or collection missing)",
                id(self),
                self.collection_name,
            )
        sys.stdout.flush()
        return await super().search(vector, query_filter=query_filter)

    async def handle_persistence(self) -> None:
        """Trigger persistence if auto_persist is enabled.

        Called after upsert and delete operations to persist changes.
        """
        if self.auto_persist:
            await self._persist_to_disk()


__all__ = ("MemoryVectorStoreProvider",)
