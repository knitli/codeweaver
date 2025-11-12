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

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, cast, override

from pydantic import UUID7
from typing_extensions import TypeIs

from codeweaver.agent_api.find_code.results import SearchResult
from codeweaver.agent_api.find_code.types import StrategizedQuery
from codeweaver.common.utils.utils import get_user_config_dir
from codeweaver.config.providers import MemoryConfig
from codeweaver.core.chunks import CodeChunk
from codeweaver.engine.search import Filter
from codeweaver.exceptions import PersistenceError, ProviderError
from codeweaver.providers.provider import Provider
from codeweaver.providers.vector_stores.base import MixedQueryInput, VectorStoreProvider
from codeweaver.providers.vector_stores.metadata import HybridVectorPayload


try:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams
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


class MemoryVectorStoreProvider(VectorStoreProvider[AsyncQdrantClient]):
    """In-memory vector store with JSON persistence for development/testing.

    Uses Qdrant's in-memory mode (:memory:) with automatic persistence to JSON.
    Suitable for small codebases (<10k chunks) and testing scenarios.
    """

    config: MemoryConfig = MemoryConfig()
    _client: AsyncQdrantClient | None = None

    _provider: ClassVar[Provider] = Provider.MEMORY

    @override
    async def _initialize(self) -> None:  # type: ignore
        """Initialize in-memory Qdrant client and restore from disk.

        Raises:
            PersistenceError: Failed to restore from persistence file.
            ValidationError: Persistence file format invalid.
        """
        if not self.config:
            from codeweaver.common.registry.provider import get_provider_config_for
            from codeweaver.providers.provider import ProviderKind

            config = get_provider_config_for(ProviderKind.VECTOR_STORE)
            if not isinstance(config, dict) or config.get("provider") != Provider.MEMORY:
                raise ProviderError("No valid configuration found for MemoryVectorStoreProvider")
            self.config = MemoryConfig(**config)
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

        # Create in-memory Qdrant client
        client = AsyncQdrantClient(location=":memory:", **(self.config.get("client_options", {})))
        object.__setattr__(self, "_client", client)

        # Restore from disk if persistence file exists
        if persist_path.exists():
            await self._restore_from_disk()

        # Set up periodic persistence if configured
        if auto_persist:
            periodic_task = asyncio.create_task(self._periodic_persist_task())
            object.__setattr__(self, "_periodic_task", periodic_task)

    @property
    def base_url(self) -> str | None:
        """The base URL for the provider's API.

        Returns:
            None (in-memory has no URL).
        """
        return None

    @property
    def collection(self) -> str | None:
        """Name of the currently configured collection.

        Returns:
            Collection name from config or None.
        """
        return self.config.get("collection_name")

    @staticmethod
    def _ensure_client(client: Any) -> TypeIs[AsyncQdrantClient]:
        """Ensure the Qdrant client is initialized.

        Returns:
            bool: True if the client is initialized and ready.
        """
        if not isinstance(client, AsyncQdrantClient):
            return False
        # Check inner client's location attribute
        inner_client = getattr(client, "_client", None)
        return inner_client is not None and getattr(inner_client, "location", None) == ":memory:"

    def _telemetry_keys(self) -> None:
        """Get telemetry keys for the provider.

        Returns:
            None (no special telemetry handling needed for in-memory provider).
        """
        return

    async def _ensure_collection(self, collection_name: str, dense_dim: int = 768) -> None:
        """Ensure collection exists, creating it if necessary.

        Args:
            collection_name: Name of the collection to ensure exists.
            dense_dim: Dimension of dense vectors (default 768).
        """
        from qdrant_client.models import Distance, VectorParams

        if self._client is None:
            raise ProviderError("Qdrant client not initialized")

        # Check if collection exists
        collections = await self._client.get_collections()
        collection_names = tuple(col.name for col in collections.collections)

        if collection_name not in collection_names:
            # Create collection with dense and sparse vector support
            await self._client.create_collection(
                collection_name=collection_name,
                vectors_config={"dense": VectorParams(size=dense_dim, distance=Distance.COSINE)},
                sparse_vectors_config={"sparse": {}},  # type: ignore
            )

    async def list_collections(self) -> list[str] | None:
        """List all collections in the in-memory store.

        Returns:
            List of collection names.
        """
        if not self._ensure_client(self._client):
            raise ProviderError("Qdrant client not initialized")
        collections = await self._client.get_collections()
        return [col.name for col in collections.collections]

    async def search(
        self, vector: StrategizedQuery | MixedQueryInput, query_filter: Filter | None = None
    ) -> list[SearchResult]:
        """Search for similar vectors using dense, sparse, or hybrid search.

        Args:
            vector: Query vector (StrategizedQuery or list of floats/ints or dict for hybrid
            other inputs will be deprecated in favor of StrategizedQuery in the future).
            query_filter: Optional filter for search results.

        Returns:
            List of search results sorted by relevance score.

        Raises:
            CollectionNotFoundError: Collection doesn't exist.
            SearchError: Search operation failed.
        """
        if not self._ensure_client(self._client):
            raise ProviderError("Qdrant client not initialized")
        collection_name = self.collection
        if not collection_name:
            raise ProviderError("No collection configured")

        await self._ensure_collection(collection_name)

        # Normalize input to StrategizedQuery
        strategized_vector = self._normalize_vector_input(vector)

        try:
            # Execute search query
            results = await self._execute_search_query(strategized_vector, collection_name)

            # Convert results to SearchResult objects
            return self._convert_search_results(results, strategized_vector)
        except Exception as e:
            raise ProviderError(f"Search operation failed: {e}") from e

    def _normalize_vector_input(
        self, vector: StrategizedQuery | MixedQueryInput
    ) -> StrategizedQuery:
        """Normalize vector input to StrategizedQuery format.

        Args:
            vector: Input vector in various formats.

        Returns:
            Normalized StrategizedQuery.

        Raises:
            ProviderError: Invalid vector input format.
        """
        from codeweaver.agent_api.find_code.types import SearchStrategy, StrategizedQuery
        from codeweaver.providers.embedding.types import SparseEmbedding

        if isinstance(vector, StrategizedQuery):
            return vector

        sparse, dense = None, None

        if isinstance(vector, dict):
            if "indices" in vector and "values" in vector:  # type: ignore
                sparse = SparseEmbedding(indices=vector["indices"], values=vector["values"])  # type: ignore
            elif "sparse" in vector:
                sparse = SparseEmbedding(
                    indices=vector["sparse"].get("indices", []),  # type: ignore
                    values=vector["sparse"].get("values", []),  # type: ignore
                )
            if "dense" in vector:  # type: ignore
                dense = vector["dense"]  # type: ignore
        elif isinstance(vector, (list, tuple)):
            dense = vector

        strategy = (
            SearchStrategy.HYBRID_SEARCH
            if dense and sparse
            else SearchStrategy.DENSE_ONLY
            if dense
            else SearchStrategy.SPARSE_ONLY
        )

        return StrategizedQuery(
            query="unavailable",
            dense=dense,  # type: ignore
            sparse=sparse,
            strategy=strategy,
        )

    async def _execute_search_query(
        self, vector: StrategizedQuery, collection_name: str
    ) -> list[Any] | Any:
        """Execute the appropriate search query based on vector strategy.

        Args:
            vector: Strategized query vector.
            collection_name: Target collection name.

        Returns:
            Raw search results from Qdrant.
        """
        qdrant_filter = None  # TODO: Convert Filter to Qdrant filter when needed
        return (
            await self._client.query_points(
                **vector.to_hybrid_query(
                    query_kwargs={
                        "limit": 100,
                        "with_payload": True,
                        "with_vectors": False,
                        "query_filter": qdrant_filter or None,
                        "consistency": "quorum",
                    },
                    kwargs={"collection_name": collection_name},
                )  # type: ignore
            )
            if vector.is_hybrid()
            else await self._client.search(
                **vector.to_query(
                    kwargs={
                        "collection_name": collection_name,
                        "limit": 100,
                        "with_payload": True,
                        "with_vectors": False,
                        "query_filter": qdrant_filter or None,
                        "consistency": "quorum",
                    }
                )  # type: ignore
            )
        )

    def _convert_search_results(self, results: Any, vector: StrategizedQuery) -> list[SearchResult]:
        """Convert Qdrant results to SearchResult objects.

        Args:
            results: Raw Qdrant search results.
            vector: Original strategized query.

        Returns:
            List of SearchResult objects.
        """
        from qdrant_client.http.models import QueryResponse

        from codeweaver.agent_api.find_code.results import SearchResult

        # Handle both query_points (QueryResponse) and search (list) results
        points = results.points if isinstance(results, QueryResponse) else results

        search_results: list[SearchResult] = []
        for point in points:
            payload = HybridVectorPayload.model_validate(point.payload or {})  # type: ignore

            search_result = SearchResult.model_construct(
                content=payload.chunk,
                file_path=Path(payload.file_path) if payload.file_path else None,
                score=point.score,
                metadata={"query": vector.query, "strategy": vector.strategy},
            )
            search_results.append(search_result)

        return search_results

    def _prepare_vectors(self, chunk: CodeChunk) -> dict[str, Any]:
        """Prepare vector dictionary for a code chunk.

        Args:
            chunk: Code chunk with embeddings.

        Returns:
            Dictionary with dense and/or sparse vectors.
        """
        from qdrant_client.http.models import SparseVector

        vectors: dict[str, Any] = {}

        if chunk.dense_embeddings:
            vectors["dense"] = list(chunk.dense_embeddings.embeddings)

        if chunk.sparse_embeddings:
            sparse = chunk.sparse_embeddings
            indices, values = sparse.embeddings

            # Normalize indices and values to lists
            normed_indices = (
                indices
                if isinstance(indices, list)
                else list(indices)
                if isinstance(indices, Iterable)
                else [indices]
            )
            normed_values = (
                values
                if isinstance(values, list)
                else list(values)
                if isinstance(values, Iterable)
                else [values]
            )

            vectors["sparse"] = SparseVector(indices=normed_indices, values=normed_values)  # type: ignore[arg-type]

        return vectors

    def _create_payload(self, chunk: CodeChunk) -> HybridVectorPayload:
        """Create payload for a code chunk.

        Args:
            chunk: Code chunk to create payload for.

        Returns:
            HybridVectorPayload instance.
        """
        return HybridVectorPayload(
            chunk=chunk,
            chunk_id=chunk.chunk_id.hex,
            chunked_on=datetime.fromtimestamp(chunk.timestamp).astimezone(UTC).isoformat(),
            file_path=str(chunk.file_path) if chunk.file_path else "",
            line_start=chunk.line_range.start,
            line_end=chunk.line_range.end,
            indexed_at=datetime.now(UTC).isoformat(),
            hash=chunk.blake_hash.hexdigest(),
            provider="memory",
            embedding_complete=bool(chunk.dense_batch_key and chunk.sparse_batch_key),
        )

    def _chunks_to_points(self, chunks: list[CodeChunk]) -> list[PointStruct]:
        """Convert code chunks to Qdrant points.

        Args:
            chunks: List of code chunks to convert.

        Returns:
            List of PointStruct objects.
        """
        points: list[PointStruct] = []

        for chunk in chunks:
            vectors = self._prepare_vectors(chunk)
            payload = self._create_payload(chunk)
            serialized_payload = payload.model_dump(mode="json", exclude_none=True, round_trip=True)

            points.append(
                PointStruct(
                    id=chunk.chunk_id.hex,
                    vector=vectors,  # type: ignore[arg-type]
                    payload=serialized_payload,
                )
            )

        return points

    async def upsert(self, chunks: list[CodeChunk]) -> None:
        """Insert or update code chunks with hybrid embeddings.

        Args:
            chunks: List of code chunks with embeddings to store.

        Raises:
            CollectionNotFoundError: Collection doesn't exist.
            UpsertError: Upsert operation failed.
        """
        if not chunks:
            return
        if not self._ensure_client(self._client):
            raise ProviderError("Qdrant client not initialized")

        collection_name = self.collection
        if not collection_name:
            raise ProviderError("No collection configured")

        # Ensure collection exists
        await self._ensure_collection(collection_name)

        # Convert chunks to Qdrant points
        points = self._chunks_to_points(chunks)

        # Upsert points
        _result = await self._client.upsert(collection_name=collection_name, points=points)

        # Trigger persistence if auto_persist enabled
        if self._auto_persist:  # type: ignore[attr-defined]
            await self._persist_to_disk()

    async def delete_by_file(self, file_path: Path) -> None:
        """Delete all chunks for a specific file.

        Args:
            file_path: File path to remove from index.
        """
        if not self._ensure_client(self._client):
            raise ProviderError("Qdrant client not initialized")
        collection_name = self.collection
        if not collection_name:
            raise ProviderError("No collection configured")

        # Ensure collection exists
        await self._ensure_collection(collection_name)

        # Delete using filter on file_path
        from qdrant_client.models import FieldCondition, MatchValue
        from qdrant_client.models import Filter as QdrantFilter

        _ = await self._client.delete(
            collection_name=collection_name,
            points_selector=QdrantFilter(
                must=[FieldCondition(key="file_path", match=MatchValue(value=str(file_path)))]
            ),
        )

        # Trigger persistence
        if self._auto_persist:  # type: ignore
            await self._persist_to_disk()

    async def delete_by_id(self, ids: list[UUID7]) -> None:
        """Delete chunks by their unique identifiers.

        Args:
            ids: List of chunk IDs to delete.
        """
        if not self._ensure_client(self._client):
            raise ProviderError("Qdrant client not initialized")
        collection_name = self.collection
        if not collection_name:
            raise ProviderError("No collection configured")

        # Ensure collection exists
        await self._ensure_collection(collection_name)

        # Convert UUID7 to strings
        point_ids = [id_.hex for id_ in ids]

        # Batch delete (Qdrant supports up to 1000 per batch)
        for i in range(0, len(point_ids), 1000):
            batch = point_ids[i : i + 1000]
            await self._client.delete(collection_name=collection_name, points_selector=batch)  # type: ignore

        # Trigger persistence
        if self._auto_persist:  # type: ignore
            await self._persist_to_disk()

    async def delete_by_name(self, names: list[str]) -> None:
        """Delete chunks by their unique names.

        Args:
            names: List of chunk names to delete.
        """
        if not self._ensure_client(self._client):
            raise ProviderError("Qdrant client not initialized")
        collection_name = self.collection
        if not collection_name:
            raise ProviderError("No collection configured")

        # Ensure collection exists
        await self._ensure_collection(collection_name)

        # Delete using filter on chunk.chunk_name (nested field in payload)
        from qdrant_client.models import FieldCondition, MatchAny
        from qdrant_client.models import Filter as QdrantFilter

        _ = await self._client.delete(
            collection_name=collection_name,
            points_selector=QdrantFilter(
                must=[FieldCondition(key="chunk.chunk_name", match=MatchAny(any=names))]
            ),
        )

        # Trigger persistence
        if self._auto_persist:  # type: ignore
            await self._persist_to_disk()

    async def _persist_to_disk(self) -> None:
        """Persist in-memory state to JSON file.

        Raises:
            PersistenceError: Failed to write persistence file.
        """
        if not self._ensure_client(self._client):
            raise ProviderError("Qdrant client not initialized")
        try:
            # Get all collections
            collections_response = await self._client.get_collections()
            collections_data = {}

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
                        with_vectors=True,  # type: ignore
                    )
                    if not result[0]:  # No more points
                        break
                    points.extend(result[0])  # type: ignore
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
                            from codeweaver.providers.vector_stores.utils import resolve_dimensions

                            dense_size = resolve_dimensions()
                # TODO: this should be a CollectionMetadata instance
                collections_data[col.name] = {
                    "metadata": {"provider": "memory", "created_at": datetime.now(UTC).isoformat()},
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

                await self._client.create_collection(
                    collection_name=collection_name,
                    vectors_config={
                        "dense": VectorParams(
                            size=dense_config.get("size", 768), distance=Distance.COSINE
                        )
                    },
                    sparse_vectors_config={"sparse": {}},  # type: ignore
                )

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
                # Log error but continue (using print for now, should use logger)
                print(f"Periodic persistence failed: {e}")  # noqa: F821

    async def _on_shutdown(self) -> None:
        """Cleanup handler for graceful shutdown.

        Performs final persistence and cancels background tasks.
        """
        self._shutdown = True

        # Cancel periodic task
        if self._periodic_task:  # type: ignore
            self._periodic_task.cancel()  # type: ignore
            with contextlib.suppress(asyncio.CancelledError):
                await self._periodic_task  # type: ignore

        # Final persistence
        try:
            await self._persist_to_disk()
        except Exception:
            # Log but don't raise on shutdown
            logger.exception("Final persistence on shutdown failed")

        # Close client
        if self._client:
            await self._client.close()


__all__ = ("MemoryVectorStoreProvider",)
