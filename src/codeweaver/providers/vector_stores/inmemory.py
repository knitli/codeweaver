# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""In-memory vector store with JSON persistence using Qdrant in-memory mode."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import UUID4

from codeweaver.config.providers import MemoryConfig
from codeweaver.core.chunks import CodeChunk, SearchResult
from codeweaver.core.spans import Span
from codeweaver.engine.filter import Filter
from codeweaver.exceptions import PersistenceError, ProviderError
from codeweaver.providers.provider import Provider
from codeweaver.providers.vector_stores.base import VectorStoreProvider

try:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams
except ImportError as e:
    raise ProviderError(
        "Qdrant client is required for MemoryVectorStore. Install it with: pip install qdrant-client"
    ) from e


class MemoryVectorStore(VectorStoreProvider[AsyncQdrantClient]):
    """In-memory vector store with JSON persistence for development/testing.

    Uses Qdrant's in-memory mode (:memory:) with automatic persistence to JSON.
    Suitable for small codebases (<10k chunks) and testing scenarios.
    """

    config: MemoryConfig
    _provider: Provider = Provider.MEMORY
    _client: AsyncQdrantClient | None = None

    async def _initialize(self) -> None:
        """Initialize in-memory Qdrant client and restore from disk.

        Raises:
            PersistenceError: Failed to restore from persistence file.
            ValidationError: Persistence file format invalid.
        """
        # Initialize persistence settings
        persist_path = Path(self.config.get("persist_path", ".codeweaver/vector_store.json"))
        auto_persist = self.config.get("auto_persist", True)
        persist_interval = self.config.get("persist_interval", 300)

        # Store as private attributes
        object.__setattr__(self, "_persist_path", persist_path)
        object.__setattr__(self, "_auto_persist", auto_persist)
        object.__setattr__(self, "_persist_interval", persist_interval)
        object.__setattr__(self, "_periodic_task", None)
        object.__setattr__(self, "_shutdown", False)

        # Create in-memory Qdrant client
        self._client = AsyncQdrantClient(location=":memory:")

        # Restore from disk if persistence file exists
        if persist_path.exists():
            await self._restore_from_disk()

        # Set up periodic persistence if configured
        if auto_persist and persist_interval is not None:
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

    def _telemetry_keys(self) -> dict[str, str] | None:
        """Get telemetry keys for the provider.

        Returns:
            None (no special telemetry handling needed for in-memory provider).
        """
        return None

    async def _ensure_collection(self, collection_name: str, dense_dim: int = 768) -> None:
        """Ensure collection exists, creating it if necessary.

        Args:
            collection_name: Name of the collection to ensure exists.
            dense_dim: Dimension of dense vectors (default 768).
        """
        from qdrant_client.models import Distance, VectorParams

        # Check if collection exists
        collections = await self._client.get_collections()
        collection_names = [col.name for col in collections.collections]

        if collection_name not in collection_names:
            # Create collection with dense and sparse vector support
            await self._client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": VectorParams(size=dense_dim, distance=Distance.COSINE)
                },
                sparse_vectors_config={"sparse": {}},  # type: ignore
            )

    async def list_collections(self) -> list[str] | None:
        """List all collections in the in-memory store.

        Returns:
            List of collection names.
        """
        collections = await self._client.get_collections()
        return [col.name for col in collections.collections]

    async def search(
        self,
        vector: list[float] | dict[str, list[float] | Any],
        query_filter: Filter | None = None,
    ) -> list[SearchResult]:
        """Search for similar vectors using dense, sparse, or hybrid search.

        Args:
            vector: Query vector (list for dense-only or dict for hybrid).
            query_filter: Optional filter for search results.

        Returns:
            List of search results sorted by relevance score.

        Raises:
            CollectionNotFoundError: Collection doesn't exist.
            SearchError: Search operation failed.
        """
        collection_name = self.collection
        if not collection_name:
            raise ProviderError("No collection configured")

        # Ensure collection exists
        await self._ensure_collection(collection_name)

        # Prepare query vector(s) for Qdrant
        # Handle both dense-only (list[float]) and hybrid (dict) queries
        if isinstance(vector, list):
            # Dense-only search
            query_vector = "dense"
            query_value = vector
        else:
            # Hybrid or sparse-only search
            # Prefer dense if available, otherwise use sparse
            if vector.get("dense"):
                query_vector = "dense"
                query_value = vector["dense"]
            elif vector.get("sparse"):
                query_vector = "sparse"
                query_value = vector["sparse"]
            else:
                raise ProviderError("No valid vector provided (expected 'dense' or 'sparse' key in dict)")

        try:
            # Perform search using Qdrant's query_points for hybrid support
            from qdrant_client.models import QueryRequest

            # Build Qdrant filter from our Filter if provided
            qdrant_filter = None
            if query_filter:
                # TODO: Implement filter translation when Filter type is defined
                # For now, pass None to search all points
                pass

            # For sparse vectors, need to convert dict to SparseVector model
            if query_vector == "sparse" and isinstance(query_value, dict):
                from qdrant_client.models import SparseVector
                query_value = SparseVector(
                    indices=query_value.get("indices", []),
                    values=query_value.get("values", []),
                )

            # Search with vector
            results = await self._client.query_points(
                collection_name=collection_name,
                query=query_value,
                using=query_vector,
                limit=100,  # Maximum results per query
                with_payload=True,
                with_vectors=False,  # Don't return vectors in results
                query_filter=qdrant_filter,
            )

            # Convert Qdrant results to SearchResult objects
            search_results: list[SearchResult] = []
            for point in results.points:
                # Extract payload data
                payload = point.payload or {}

                # Reconstruct CodeChunk from payload using model_construct
                from uuid import UUID

                chunk = CodeChunk.model_construct(
                    chunk_id=UUID(payload["chunk_id"]) if payload.get("chunk_id") else None,
                    chunk_name=payload.get("chunk_name"),
                    file_path=Path(payload["file_path"]) if payload.get("file_path") else None,
                    language=payload.get("language"),
                    content=payload.get("content", ""),
                    line_range=Span(
                        start=payload.get("line_start", 1),
                        end=payload.get("line_end", 1),
                    ),
                )

                # Create SearchResult from point payload using model_construct to avoid AstThing issues
                search_result = SearchResult.model_construct(
                    content=chunk,
                    file_path=Path(payload["file_path"]) if payload.get("file_path") else None,
                    score=point.score if point.score is not None else 0.0,
                    metadata=None,  # TODO: Extract metadata from payload if needed
                )
                search_results.append(search_result)

            return search_results

        except Exception as e:
            raise ProviderError(f"Search operation failed: {e}") from e

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

        collection_name = self.collection
        if not collection_name:
            raise ProviderError("No collection configured")

        # Ensure collection exists (infer dimension from first chunk)
        if chunks:
            first_embedding = chunks[0].embeddings
            dense_dim = len(first_embedding.get("dense", [])) if first_embedding else 768
            await self._ensure_collection(collection_name, dense_dim)

        # Convert chunks to Qdrant points
        points = []
        for chunk in chunks:
            # Prepare vectors dict for named vectors
            vectors: dict[str, list[float]] = {}
            if chunk.embeddings.get("dense"):
                vectors["dense"] = chunk.embeddings["dense"]
            if chunk.embeddings.get("sparse"):
                # Qdrant sparse vector format
                sparse = chunk.embeddings["sparse"]
                vectors["sparse"] = sparse  # type: ignore

            # Prepare payload with chunk metadata
            payload = {
                "chunk_id": str(chunk.chunk_id),
                "chunk_name": chunk.chunk_name,
                "file_path": str(chunk.file_path),
                "language": chunk.language.value,
                "content": chunk.content,
                "line_start": chunk.line_start,
                "line_end": chunk.line_end,
                "indexed_at": datetime.now(UTC).isoformat(),
                "provider_name": "memory",
                "embedding_complete": bool(
                    chunk.embeddings.get("dense") and chunk.embeddings.get("sparse")
                ),
            }

            points.append(
                PointStruct(
                    id=str(chunk.chunk_id),
                    vector=vectors,  # type: ignore
                    payload=payload,
                )
            )

        # Upsert points
        await self._client.upsert(collection_name=collection_name, points=points)

        # Trigger persistence if auto_persist enabled
        if self._auto_persist:
            await self._persist_to_disk()

    async def delete_by_file(self, file_path: Path) -> None:
        """Delete all chunks for a specific file.

        Args:
            file_path: File path to remove from index.
        """
        collection_name = self.collection
        if not collection_name:
            raise ProviderError("No collection configured")

        # Ensure collection exists
        await self._ensure_collection(collection_name)

        # Delete using filter on file_path
        from qdrant_client.models import FieldCondition, Filter as QdrantFilter, MatchValue

        await self._client.delete(
            collection_name=collection_name,
            points_selector=QdrantFilter(
                must=[FieldCondition(key="file_path", match=MatchValue(value=str(file_path)))]
            ),
        )

        # Trigger persistence
        if self._auto_persist:
            await self._persist_to_disk()

    async def delete_by_id(self, ids: list[UUID4]) -> None:
        """Delete chunks by their unique identifiers.

        Args:
            ids: List of chunk IDs to delete.
        """
        collection_name = self.collection
        if not collection_name:
            raise ProviderError("No collection configured")

        # Ensure collection exists
        await self._ensure_collection(collection_name)

        # Convert UUID4 to strings
        point_ids = [str(id_) for id_ in ids]

        # Batch delete (Qdrant supports up to 1000 per batch)
        for i in range(0, len(point_ids), 1000):
            batch = point_ids[i : i + 1000]
            await self._client.delete(collection_name=collection_name, points_selector=batch)  # type: ignore

        # Trigger persistence
        if self._auto_persist:
            await self._persist_to_disk()

    async def delete_by_name(self, names: list[str]) -> None:
        """Delete chunks by their unique names.

        Args:
            names: List of chunk names to delete.
        """
        collection_name = self.collection
        if not collection_name:
            raise ProviderError("No collection configured")

        # Ensure collection exists
        await self._ensure_collection(collection_name)

        # Delete using filter on chunk_name
        from qdrant_client.models import FieldCondition, Filter as QdrantFilter, MatchAny

        await self._client.delete(
            collection_name=collection_name,
            points_selector=QdrantFilter(
                must=[FieldCondition(key="chunk_name", match=MatchAny(any=names))]
            ),
        )

        # Trigger persistence
        if self._auto_persist:
            await self._persist_to_disk()

    async def _persist_to_disk(self) -> None:
        """Persist in-memory state to JSON file.

        Raises:
            PersistenceError: Failed to write persistence file.
        """
        try:
            # Get all collections
            collections_response = await self._client.get_collections()
            collections_data = {}

            for col in collections_response.collections:
                # Get collection info
                col_info = await self._client.get_collection(collection_name=col.name)

                # Scroll all points
                points = []
                offset = None
                while True:
                    result = await self._client.scroll(
                        collection_name=col.name, limit=100, offset=offset, with_payload=True, with_vectors=True  # type: ignore
                    )
                    if not result[0]:  # No more points
                        break
                    points.extend(result[0])
                    offset = result[1]  # Next offset
                    if offset is None:  # Reached end
                        break

                # Serialize collection data
                # Extract dense vector config (vectors is a dict[str, VectorParams])
                vectors_dict = col_info.config.params.vectors  # type: ignore
                dense_size = 768  # default
                if isinstance(vectors_dict, dict) and "dense" in vectors_dict:
                    dense_params = vectors_dict["dense"]
                    dense_size = dense_params.size if hasattr(dense_params, "size") else 768

                collections_data[col.name] = {
                    "metadata": {
                        "provider": "memory",
                        "created_at": datetime.now(UTC).isoformat(),
                    },
                    "vectors_config": {
                        "dense": {
                            "size": dense_size,
                            "distance": "Cosine",
                        }
                    },
                    "sparse_vectors_config": {"sparse": {}},
                    "points": [
                        {
                            "id": str(point.id),
                            "vector": point.vector,
                            "payload": point.payload,
                        }
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
            temp_path = self._persist_path.with_suffix(".tmp")
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_text(json.dumps(persistence_data, indent=2))

            # Atomic rename
            temp_path.replace(self._persist_path)

        except Exception as e:
            raise PersistenceError(f"Failed to persist to disk: {e}") from e

    async def _restore_from_disk(self) -> None:
        """Restore in-memory state from JSON file.

        Raises:
            PersistenceError: Failed to read or parse persistence file.
            ValidationError: Persistence file format invalid.
        """
        try:
            # Read and parse JSON
            data = json.loads(self._persist_path.read_text())

            # Validate version
            if data.get("version") != "1.0":
                raise PersistenceError(f"Unsupported persistence version: {data.get('version')}")

            # Restore each collection
            for collection_name, collection_data in data.get("collections", {}).items():
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
                            id=point["id"], vector=point["vector"], payload=point["payload"]  # type: ignore
                        )
                        for point in batch
                    ]
                    await self._client.upsert(collection_name=collection_name, points=points)

        except Exception as e:
            raise PersistenceError(f"Failed to restore from disk: {e}") from e

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
                # Log error but continue (using print for now, should use logger)
                print(f"Periodic persistence failed: {e}")  # noqa: F821

    async def _on_shutdown(self) -> None:
        """Cleanup handler for graceful shutdown.

        Performs final persistence and cancels background tasks.
        """
        self._shutdown = True

        # Cancel periodic task
        if self._periodic_task:
            self._periodic_task.cancel()
            try:
                await self._periodic_task
            except asyncio.CancelledError:
                pass

        # Final persistence
        try:
            await self._persist_to_disk()
        except Exception:
            # Log but don't raise on shutdown
            print(f"Final persistence failed: {e}")  # noqa: F821

        # Close client
        if self._client:
            await self._client.close()


__all__ = ("MemoryVectorStore",)
