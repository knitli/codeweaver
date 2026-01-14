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
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from codeweaver.core import INJECTED, PersistenceError, Provider, ProviderError, get_user_config_dir
from codeweaver.providers.vector_stores.qdrant_base import QdrantBaseProvider


if TYPE_CHECKING:
    from codeweaver.core import CodeChunk, SearchResult, StrategizedQuery
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
    """In-memory vector store with JSON persistence for development/testing.

    Uses Qdrant's in-memory mode (:memory:) with automatic persistence to JSON.
    Suitable for small codebases (<10k chunks) and testing scenarios.
    """

    _provider: ClassVar[Literal[Provider.MEMORY]] = Provider.MEMORY
    config: MemoryDep = INJECTED
    _client: AsyncQdrantClient | None = None
    _shared_client: ClassVar[AsyncQdrantClient | None] = None

    def model_post_init(self, __context: Any, /) -> None:
        """Capture config values before they get overwritten during initialization."""
        # Store persist_path, auto_persist, and persist_interval from original config
        # These will be used in _init_provider after base class overwrites self.config
        for attr in ("persist_path", "auto_persist", "persist_interval"):
            value = getattr(self.config.in_memory_config, attr, None)
            object.__setattr__(self, f"_initial_{attr}", value)
        super().model_post_init(__context)

    @property
    def base_url(self) -> str | None:
        """Get the base URL for the memory provider - always :memory:."""
        return ":memory:"

    async def _init_provider(self) -> None:  # type: ignore
        """Initialize in-memory Qdrant client and restore from disk.

        Raises:
            PersistenceError: Failed to restore from persistence file.
            ValidationError: Persistence file format invalid.
        """
        from codeweaver.core import is_test_environment

        # Use the values captured in model_post_init before self.config was overwritten
        persist_path_config = getattr(self, "_initial_persist_path", get_user_config_dir())
        persist_path = Path(persist_path_config)

        # Determine persistence directory
        if persist_path.suffix == ".json":
            # If user pointed to a json file, use the path without extension as directory
            persist_path = persist_path.with_suffix("")
        elif not persist_path.suffix:
            # If path is a directory (or intended to be), append default directory name
            persist_path = persist_path / f"{_get_project_name()}_vector_store"

        # Logic for auto_persist:
        # 1. If explicitly provided in config, use that value.
        # 2. If not provided, disable in test mode, enable otherwise.
        auto_persist_raw = getattr(self, "_initial_auto_persist", None)
        if auto_persist_raw is not None:
            auto_persist = bool(auto_persist_raw)
        else:
            auto_persist = not is_test_environment()

        persist_interval = getattr(self, "_initial_persist_interval", None)
        if persist_interval is None:
            persist_interval = 300

        # Store as private attributes
        object.__setattr__(self, "_persist_path", persist_path)
        object.__setattr__(self, "_auto_persist", auto_persist)
        object.__setattr__(self, "_persist_interval", persist_interval)
        object.__setattr__(self, "_periodic_task", None)
        object.__setattr__(self, "_shutdown", False)
        object.__setattr__(self, "_collection_metadata", {})
        object.__setattr__(self, "_collection_metadata_lock", asyncio.Lock())

        # Create in-memory Qdrant client
        client = await self._build_client()
        object.__setattr__(self, "_client", client)

        import sys

        logger.debug(
            "MemoryVectorStoreProvider._init_provider instance %s with client %s and collection %s",
            id(self),
            id(client),
            self._collection,
        )
        sys.stdout.flush()

        # Ensure collection exists
        if self._collection:
            await self._ensure_collection(self._collection)
            logger.debug(
                "MemoryVectorStoreProvider ensured collection %s in client %s",
                self._collection,
                id(client),
            )
            sys.stdout.flush()
        # Restore from disk if persistence file exists (and not in test mode)
        if not is_test_environment() and persist_path.exists():
            await self._restore_from_disk()

        # Set up periodic persistence if configured
        if auto_persist:
            periodic_task = asyncio.create_task(self._periodic_persist_task())
            object.__setattr__(self, "_periodic_task", periodic_task)

    async def _build_client(self) -> AsyncQdrantClient:
        """Build the Qdrant Async client.

        In test mode, returns a class-level shared client to ensure data is shared
        between different provider instances.

        Returns:
            An initialized AsyncQdrantClient.
        """
        from codeweaver.core import is_test_environment

        if is_test_environment():
            import sys

            if MemoryVectorStoreProvider._shared_client is None:
                MemoryVectorStoreProvider._shared_client = AsyncQdrantClient(
                    location=":memory:", **(self.config.get("client_options", {}))
                )
                logger.debug(
                    "MemoryVectorStoreProvider created NEW _shared_client %s",
                    id(MemoryVectorStoreProvider._shared_client),
                )
            else:
                logger.debug(
                    "MemoryVectorStoreProvider using EXISTING _shared_client %s",
                    id(MemoryVectorStoreProvider._shared_client),
                )
            sys.stdout.flush()
            return MemoryVectorStoreProvider._shared_client

        return AsyncQdrantClient(location=":memory:", **(self.config.get("client_options", {})))

    async def _persist_to_disk(self) -> None:
        """Persist in-memory state to Qdrant storage directory.

        Raises:
            PersistenceError: Failed to write persistence file.
        """
        if not self._ensure_client(self._client):
            raise ProviderError("Qdrant client not initialized")

        # Atomic persistence via temporary directory
        temp_path = self._persist_path.with_suffix(".tmp")
        if temp_path.exists():
            import shutil

            shutil.rmtree(temp_path)

        try:
            # Initialize persistent client at temp path
            # We use AsyncQdrantClient with path to create local storage
            dest_client = AsyncQdrantClient(path=str(temp_path))

            # Migrate data
            await self.migrate_to(dest_client)

            # Close dest client to release locks
            await dest_client.close()

            # Atomic replace
            if self._persist_path.exists():
                import shutil

                if self._persist_path.is_dir():
                    shutil.rmtree(self._persist_path)
                else:
                    self._persist_path.unlink()

            temp_path.rename(self._persist_path)

        except Exception as e:
            if temp_path.exists():
                import shutil

                shutil.rmtree(temp_path)
            raise PersistenceError(f"Failed to persist to disk: {e}") from e

    async def _restore_from_disk(self) -> None:
        """Restore in-memory state from Qdrant storage directory.

        Raises:
            PersistenceError: Failed to restore from disk.
        """
        if not self._persist_path.exists():
            return

        # Check if it's a directory (new format)
        if self._persist_path.is_dir():
            try:
                source_client = AsyncQdrantClient(path=str(self._persist_path))
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
                await asyncio.sleep(self._persist_interval or 300)  # type: ignore
                if not self._shutdown:
                    await self._persist_to_disk()
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue to avoid data loss
                logger.warning("Periodic persistence failed", exc_info=True)

    async def close(self) -> None:
        """Close Qdrant client and stop background tasks."""
        if not self._client:
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
        if self._periodic_task:  # ty: ignore[unresolved-attribute]
            self._periodic_task.cancel()  # ty: ignore[unresolved-attribute]
            with contextlib.suppress(asyncio.CancelledError):
                await self._periodic_task  # ty: ignore[unresolved-attribute]

        # Final persistence
        try:
            await self._persist_to_disk()
        except Exception:
            # Log but don't raise on shutdown
            logger.warning("Final persistence on shutdown failed", exc_info=True)

        # Close client
        if self._client:
            await self._client.close()

    async def upsert(self, chunks: list[CodeChunk], *, for_backup: bool = False) -> None:
        """Insert or update code chunks with hybrid embeddings."""
        logger.debug(
            "MemoryVectorStoreProvider.upsert instance %s to collection: %s with %d chunks",
            id(self),
            self._collection,
            len(chunks),
        )
        await super().upsert(chunks, for_backup=for_backup)

        # Verify count
        if self._client and self._collection:
            info = await self._client.get_collection(self._collection)
            logger.debug(
                "Collection %s now has %d points in client %s",
                self._collection,
                info.points_count,
                id(self._client),
            )

    async def search(
        self, vector: StrategizedQuery | MixedQueryInput, query_filter: Filter | None = None
    ) -> list[SearchResult]:
        """Search for similar vectors."""
        import sys

        if not self._client:
            await self._initialize()

        if self._client and self._collection:
            info = await self._client.get_collection(self._collection)
            logger.debug(
                "MemoryVectorStoreProvider.search instance %s in collection: %s (points: %d)",
                id(self),
                self._collection,
                info.points_count,
            )
        else:
            logger.debug(
                "MemoryVectorStoreProvider.search instance %s in collection: %s (client or collection missing)",
                id(self),
                self._collection,
            )
        sys.stdout.flush()
        return await super().search(vector, query_filter=query_filter)

    async def handle_persistence(self) -> None:
        """Trigger persistence if auto_persist is enabled.

        Called after upsert and delete operations to persist changes.
        """
        if self._auto_persist:  # type: ignore
            await self._persist_to_disk()


__all__ = ("MemoryVectorStoreProvider",)
