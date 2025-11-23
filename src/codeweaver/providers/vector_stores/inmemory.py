# sourcery skip: no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""In-memory vector store with JSON persistence using Qdrant in-memory mode."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging

from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar, Literal, cast

from codeweaver.common.utils.utils import get_user_config_dir
from codeweaver.config.providers import MemoryConfig
from codeweaver.exceptions import PersistenceError, ProviderError
from codeweaver.providers.provider import Provider
from codeweaver.providers.vector_stores.qdrant_base import QdrantBaseProvider


try:
    from qdrant_client import AsyncQdrantClient
except ImportError as e:
    raise ProviderError(
        "Qdrant client is required for MemoryVectorStoreProvider. Install it with: pip install qdrant-client"
    ) from e

logger = logging.getLogger(__name__)


def _get_project_name() -> str:
    """Get the project name for the persistence store.

    Returns:
        The project name as a string.
    """
    from codeweaver.config.settings import get_settings_map

    settings = get_settings_map()
    return settings.get("project_name") or (
        settings.get("project_path").name
        if isinstance(settings.get("project_path"), Path)
        else "default_project"
    )


class MemoryVectorStoreProvider(QdrantBaseProvider):
    """In-memory vector store with JSON persistence for development/testing.

    Uses Qdrant's in-memory mode (:memory:) with automatic persistence to JSON.
    Suitable for small codebases (<10k chunks) and testing scenarios.
    """

    config: MemoryConfig = MemoryConfig()
    _client: AsyncQdrantClient | None = None

    @property
    def base_url(self) -> str | None:
        """Get the base URL for the memory provider - always :memory:."""
        return ":memory:"

    _provider: ClassVar[Literal[Provider.MEMORY]] = Provider.MEMORY

    async def _init_provider(self) -> None:  # type: ignore
        """Initialize in-memory Qdrant client and restore from disk.

        Raises:
            PersistenceError: Failed to restore from persistence file.
            ValidationError: Persistence file format invalid.
        """
        # Handle persist_path - if it's a file path, use it directly; otherwise treat as directory
        persist_path_config = self.config.get("persist_path", get_user_config_dir())
        persist_path = Path(persist_path_config)
        # If path doesn't end with .json, treat it as a directory and append default filename
        if persist_path.suffix != ".json":
            persist_path = persist_path / f"{_get_project_name()}_vector_store.json"
        auto_persist = self.config.get("auto_persist", True)
        persist_interval = self.config.get("persist_interval", 300)

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

        # Restore from disk if persistence file exists
        if persist_path.exists():
            await self._restore_from_disk()

        # Set up periodic persistence if configured
        if auto_persist:
            periodic_task = asyncio.create_task(self._periodic_persist_task())
            object.__setattr__(self, "_periodic_task", periodic_task)

    async def _build_client(self) -> AsyncQdrantClient:
        """Build the Qdrant Async client in in-memory mode.

        Returns:
            An initialized AsyncQdrantClient.
        """
        return AsyncQdrantClient(location=":memory:", **(self.config.get("client_options", {})))

    async def _persist_to_disk(self) -> None:
        """Persist in-memory state to JSON file.

        Raises:
            PersistenceError: Failed to write persistence file.
        """
        from qdrant_client.http.models import PointStruct, SparseVectorParams, VectorParams

        from codeweaver.providers.vector_stores.metadata import CollectionMetadata

        if not self._ensure_client(self._client):
            raise ProviderError("Qdrant client not initialized")
        try:
            # Get all collections
            collections_response = await self._client.get_collections()
            collections_data = {}

            async with self._collection_metadata_lock:  # type: ignore
                for col in collections_response.collections:
                    # Get collection info
                    col_info = await self._client.get_collection(collection_name=col.name)

                    # Scroll all points
                    points: list[PointStruct] = []
                    offset = None
                    while True:
                        result = await self._client.scroll(
                            collection_name=col.name,
                            limit=100,
                            offset=offset,
                            with_payload=True,
                            with_vectors=True,
                        )
                        if not result[0]:  # No more points
                            break
                        points.extend(result[0])
                        offset = result[1]  # Next offset
                        if offset is None:  # Reached end
                            break
                    # Serialize collection data
                    # Extract dense vector config (vectors is a dict[str, VectorParams])
                    vectors_data = col_info.config.params.vectors  # type: ignore
                    # Try to get dimension from collection first, fall back to model config
                    dense_size = 768  # Default dimension
                    if isinstance(vectors_data, dict) and "dense" in vectors_data:
                        dense_params = vectors_data["dense"]
                        if hasattr(dense_params, "size"):
                            dense_size = dense_params.size
                        else:
                            # Only call resolve_dimensions if we can't get size from collection
                            with contextlib.suppress(ValueError):
                                from codeweaver.providers.vector_stores.utils import (
                                    resolve_dimensions,
                                )

                                dense_size = resolve_dimensions()

                    if raw_metadata := self._collection_metadata.get(col.name):  # type: ignore[unresolved-attribute]
                        metadata = CollectionMetadata.model_validate(raw_metadata)
                    else:
                        metadata = CollectionMetadata(
                            created_at=datetime.now(UTC),
                            provider=str(self._provider),
                            project_name=_get_project_name(),
                            collection_name=col.name,
                            vector_config={"dense": VectorParams(size=dense_size)},
                            sparse_config={"sparse": SparseVectorParams()},
                        )

                    collections_data[col.name] = {
                        "metadata": metadata.model_dump(mode="json"),
                        "vectors_config": {"dense": {"size": dense_size, "distance": "Cosine"}},
                        "sparse_vectors_config": {"sparse": {}},
                        "points": [
                            {"id": str(point.id), "vector": point.vector, "payload": point.payload}
                            for point in points
                        ],
                    }

            # Create persistence data
            persistence_data = {
                "version": "1.0",
                "metadata": {
                    "created_at": datetime.now(UTC).isoformat(),
                    "last_modified": datetime.now(UTC).isoformat(),
                },
                "collections": collections_data,
            }

            # Write to temporary file first (atomic write)
            temp_path = self._persist_path.with_suffix(".tmp")  # type: ignore
            temp_path.parent.mkdir(parents=True, exist_ok=True)  # type: ignore
            temp_path.write_text(json.dumps(persistence_data, indent=2))  # type: ignore

            # Atomic rename
            temp_path.replace(self._persist_path)  # type: ignore

        except Exception as e:
            raise PersistenceError(f"Failed to persist to disk: {e}") from e

    async def _restore_from_disk(self) -> None:
        """Restore in-memory state from JSON file.

        Raises:
            PersistenceError: Failed to read or parse persistence file.
            ValidationError: Persistence file format invalid.
        """
        from pydantic_core import from_json
        from qdrant_client.models import Datatype, Distance, PointStruct, VectorParams

        def _raise_persistence_error(msg: str) -> None:
            raise PersistenceError(msg)

        if not self._ensure_client(self._client):
            raise ProviderError("Qdrant client not initialized")
        try:
            # Read and parse JSON
            data = from_json(cast(Path, self._persist_path).read_bytes())  # type: ignore

            # Validate version
            if data.get("version") != "1.0":
                _raise_persistence_error(f"Unsupported persistence version: {data.get('version')}")

            # Restore each collection
            for collection_name, collection_data in data.get("collections", {}).items():
                # Check if collection already exists
                with contextlib.suppress(Exception):
                    _ = await self._client.get_collection(collection_name=collection_name)
                    # Collection exists, delete it first to ensure clean restore
                    _ = await self._client.delete_collection(collection_name=collection_name)

                # Create collection with vector configuration
                vectors_config = collection_data["vectors_config"]
                dense_config = vectors_config.get("dense", {})

                # Map distance from persisted data
                distance_repr = dense_config.get("distance", "Cosine")
                distance_map = {
                    "Cosine": Distance.COSINE,
                    "Dot": Distance.DOT,
                    "Euclid": Distance.EUCLID,
                    "Euclidean": Distance.EUCLID,
                }
                distance = distance_map.get(distance_repr, Distance.COSINE)

                # Map datatype from persisted data
                datatype_repr = dense_config.get("datatype", "Float32")
                datatype_map = {
                    "Float32": Datatype.FLOAT32,
                    "Float16": Datatype.FLOAT16,
                    "Uint8": Datatype.UINT8,
                }
                datatype = datatype_map.get(datatype_repr, Datatype.FLOAT32)

                await self._client.create_collection(
                    collection_name=collection_name,
                    vectors_config={
                        "dense": VectorParams(
                            size=dense_config.get("size", 768),
                            distance=distance,
                            datatype=datatype,
                            # quantization_config restored if present in future
                        )
                    },
                    sparse_vectors_config={"sparse": {}},  # type: ignore
                )

                # Store collection metadata if it exists (protected by lock)
                if "metadata" in collection_data:
                    async with self._collection_metadata_lock:  # type: ignore
                        self._collection_metadata[collection_name] = collection_data["metadata"]  # type: ignore

                # Restore points in batches
                points_data = collection_data.get("points", [])
                for i in range(0, len(points_data), 100):
                    batch = points_data[i : i + 100]
                    points = [
                        PointStruct(
                            id=point["id"],
                            vector=point["vector"],
                            payload=point["payload"],  # type: ignore
                        )
                        for point in batch
                    ]
                    _ = await self._client.upsert(collection_name=collection_name, points=points)

        except Exception as e:
            raise PersistenceError(f"Failed to restore from disk: {e}") from e

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

    async def _on_shutdown(self) -> None:
        """Cleanup handler for graceful shutdown.

        Performs final persistence and cancels background tasks.
        """
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

    async def handle_persistence(self) -> None:
        """Trigger persistence if auto_persist is enabled.

        Called after upsert and delete operations to persist changes.
        """
        if self._auto_persist:  # type: ignore
            await self._persist_to_disk()


__all__ = ("MemoryVectorStoreProvider",)
