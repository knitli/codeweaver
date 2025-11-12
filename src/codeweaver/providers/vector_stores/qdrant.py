# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Qdrant provider for vector and hybrid search/store."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import UUID4
from typing_extensions import TypeIs

from codeweaver.config.providers import QdrantConfig
from codeweaver.core.chunks import CodeChunk
from codeweaver.engine.search import Filter
from codeweaver.exceptions import ProviderError
from codeweaver.providers.provider import Provider
from codeweaver.providers.vector_stores.base import VectorStoreProvider


if TYPE_CHECKING:
    from codeweaver.agent_api.find_code.results import SearchResult
    from codeweaver.agent_api.find_code.types import StrategizedQuery
    from codeweaver.providers.vector_stores.base import MixedQueryInput


QdrantClient = None
try:
    from qdrant_client import AsyncQdrantClient
except ImportError as e:
    raise ProviderError(
        "Qdrant client is required for QdrantVectorStoreProvider. Install it with: pip install qdrant-client"
    ) from e


class QdrantVectorStoreProvider(VectorStoreProvider[AsyncQdrantClient]):
    """Qdrant vector store provider supporting local and remote deployments.

    Supports hybrid search with dense and sparse embeddings via named vectors.
    """

    _client: AsyncQdrantClient | None = None
    config: QdrantConfig = QdrantConfig()
    _metadata: dict[str, Any] | None = None
    _provider: Provider = Provider.QDRANT  # type: ignore

    @staticmethod
    def _ensure_client(client: Any) -> TypeIs[AsyncQdrantClient]:
        """Ensure the Qdrant client is initialized and ready.

        Args:
            client: The client instance to check.

        Returns:
            True if the client is initialized and ready.
        """
        return client is not None and isinstance(client, AsyncQdrantClient)

    @property
    def base_url(self) -> str | None:
        """The base URL for the Qdrant server.

        Returns:
            Qdrant server URL or None if using default localhost.
        """
        return self.config.get("url")

    @property
    def collection(self) -> str | None:
        """Name of the currently configured collection.

        Returns:
            Collection name from config or None.
        """
        return self.config.get("collection_name")

    def _telemetry_keys(self) -> None:
        return None

    async def _initialize(self) -> None:
        """Initialize Qdrant client and ensure collection exists.

        Raises:
            ConnectionError: Failed to connect to Qdrant server.
            ProviderError: Client initialization failed.
        """
        url = self.config.get("url", "http://localhost:6333")
        api_key = self.config.get("api_key")
        prefer_grpc = self.config.get("prefer_grpc", False)
        grpc_port = self.config.get("grpc_port", 6334)

        self._client = AsyncQdrantClient(
            url=url,
            api_key=str(api_key) if api_key else None,
            prefer_grpc=prefer_grpc,
            grpc_port=grpc_port,
        )
        if collection_name := self.collection:
            await self._ensure_collection(collection_name)

    async def _ensure_collection(self, collection_name: str, dense_dim: int = 768) -> None:
        """Ensure collection exists, creating it if necessary.

        Args:
            collection_name: Name of the collection to ensure exists.
            dense_dim: Dimension of dense vectors (default 768).
        """
        from qdrant_client.models import Distance, VectorParams

        if not self._client:
            raise ProviderError("Qdrant client is not initialized")
        collections = await self._client.get_collections()
        collection_names = [col.name for col in collections.collections]
        if collection_name not in collection_names:
            _ = await self._client.create_collection(
                collection_name=collection_name,
                vectors_config={"dense": VectorParams(size=dense_dim, distance=Distance.COSINE)},
                sparse_vectors_config={"sparse": {}},
            )

    async def list_collections(self) -> list[str] | None:
        """List all collections in the Qdrant instance.

        Returns:
            List of collection names.

        Raises:
            ConnectionError: Failed to connect to Qdrant server.
            ProviderError: Qdrant operation failed.
        """
        if not self._client:
            raise ProviderError("Qdrant client is not initialized")
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
        from qdrant_client.http.models import SparseVector

        from codeweaver.agent_api.find_code.results import SearchResult
        from codeweaver.agent_api.find_code.types import SearchStrategy, StrategizedQuery
        from codeweaver.providers.embedding.types import SparseEmbedding

        if not self._ensure_client(self._client):
            raise ProviderError("Qdrant client not initialized")
        collection_name = self.collection
        if not collection_name:
            raise ProviderError("No collection configured")

        # Ensure collection exists
        await self._ensure_collection(collection_name)
        sparse, dense = None, None
        if not hasattr(vector, "sparse") or not hasattr(vector, "dense"):
            if isinstance(vector, dict) and "indices" in vector and "values" in vector:
                sparse = SparseEmbedding(indices=vector["indices"], values=vector["values"])
            elif isinstance(vector, dict) and "sparse" in vector:
                sparse_data = vector["sparse"]
                # Handle SparseVector model objects
                if isinstance(sparse_data, SparseVector):
                    sparse = SparseEmbedding(indices=sparse_data.indices, values=sparse_data.values)
                elif isinstance(sparse_data, dict):
                    sparse = SparseEmbedding(
                        indices=sparse_data.get("indices", []), values=sparse_data.get("values", [])
                    )
                else:
                    # Assume it's a SparseEmbedding already
                    sparse = sparse_data  # type: ignore
            elif isinstance(vector, dict) and "dense" in vector:
                dense = vector["dense"]
                # Also check for sparse in the same dict
                if "sparse" in vector:
                    sparse_data = vector["sparse"]
                    # Handle SparseVector model objects
                    if isinstance(sparse_data, SparseVector):
                        sparse = SparseEmbedding(
                            indices=sparse_data.indices, values=sparse_data.values
                        )
                    elif isinstance(sparse_data, dict):
                        sparse = SparseEmbedding(
                            indices=sparse_data.get("indices", []),
                            values=sparse_data.get("values", []),
                        )
                    else:
                        # Assume it's a SparseEmbedding already
                        sparse = sparse_data  # type: ignore
            elif isinstance(vector, (list, tuple)):
                sparse = None
                dense = vector
            vector = StrategizedQuery(
                query="unavailable",
                dense=dense,
                sparse=sparse,
                strategy=SearchStrategy.HYBRID_SEARCH
                if dense and sparse
                else SearchStrategy.DENSE_ONLY
                if dense
                else SearchStrategy.SPARSE_ONLY,
            )
        if not isinstance(vector, StrategizedQuery):
            raise ProviderError("Invalid vector input for search")

        try:
            # Perform search using Qdrant's query_points for hybrid support

            # Build Qdrant filter from our Filter if provided
            qdrant_filter = None
            if vector.is_hybrid():
                results = await self._client.query_points(
                    **vector.to_hybrid_query(
                        query_kwargs={
                            "limit": 100,
                            "with_payload": True,
                            "with_vectors": False,
                            "query_filter": qdrant_filter or None,
                        },
                        kwargs={"collection_name": collection_name},
                    )  # type: ignore
                )  # type: ignore
            else:
                results = await self._client.search(
                    **vector.to_query(
                        kwargs={
                            "collection_name": collection_name,
                            "limit": 100,
                            "with_payload": True,
                            "with_vectors": False,
                            "query_filter": qdrant_filter or None,
                        }
                    )  # type: ignore
                )
            from codeweaver.providers.vector_stores.metadata import HybridVectorPayload

            search_results: list[SearchResult] = []
            # search() returns a list directly, query_points() returns object with .points
            points: Any = results.points if hasattr(results, "points") else results
            for point in points:  # ty: ignore[not-iterable]
                payload = HybridVectorPayload.model_validate(point.payload)
                search_result = SearchResult.model_construct(
                    content=payload.chunk,
                    file_path=Path(payload.file_path) if payload.file_path else None,
                    score=point.score or 0.0,
                    metadata={"query": vector.query, "strategy": vector.strategy},
                )
                search_results.append(search_result)
        except Exception as e:
            raise ProviderError(f"Search operation failed: {e}") from e
        else:
            return search_results

    async def upsert(self, chunks: list[CodeChunk]) -> None:
        """Insert or update code chunks with hybrid embeddings.

        Args:
            chunks: List of code chunks with embeddings to store.

        Raises:
            CollectionNotFoundError: Collection doesn't exist.
            DimensionMismatchError: Embedding dimension mismatch.
            UpsertError: Upsert operation failed.
        """
        from datetime import UTC, datetime

        from qdrant_client.http.models import PointStruct

        from codeweaver.providers.embedding.types import SparseEmbedding
        from codeweaver.providers.vector_stores.metadata import HybridVectorPayload

        if not chunks:
            return
        # Ensure client is initialized (lazy initialization if needed)
        if not self._ensure_client(self._client):
            await self._initialize()
            if not self._ensure_client(self._client):
                raise ProviderError("Qdrant client not initialized")

        collection_name = self.collection
        if not collection_name:
            raise ProviderError("No collection configured")

        # Ensure collection exists
        await self._ensure_collection(collection_name)
        points: list[PointStruct] = []
        for chunk in chunks:
            # Prepare vectors dict for named vectors
            vectors: dict[str, Any] = {}

            # Try to get embeddings from proper embedding batch info
            if chunk.dense_embeddings:
                vectors["dense"] = list(chunk.dense_embeddings.embeddings)
            elif hasattr(chunk, "__dict__") and "embeddings" in chunk.__dict__:
                # Fallback for test chunks created with model_construct(embeddings={...})
                emb_dict = chunk.__dict__["embeddings"]
                if isinstance(emb_dict, dict) and "dense" in emb_dict:
                    vectors["dense"] = list(emb_dict["dense"])

            if chunk.sparse_embeddings:
                # Qdrant sparse vector format requires indices and values
                # sparse_embeddings.embeddings is a SparseEmbedding NamedTuple with .indices and .values
                sparse = chunk.sparse_embeddings
                if isinstance(sparse.embeddings, SparseEmbedding):
                    # SparseEmbedding NamedTuple: access indices and values as fields
                    from qdrant_client.http.models import SparseVector

                    vectors["sparse"] = SparseVector(
                        indices=list(sparse.embeddings.indices),
                        values=list(sparse.embeddings.values),
                    )
                else:
                    # Old format: flat list (for backward compatibility during migration)
                    vectors["sparse"] = list(sparse.embeddings)
            elif hasattr(chunk, "__dict__") and "embeddings" in chunk.__dict__:
                # Fallback for test chunks created with model_construct(embeddings={...})
                emb_dict = chunk.__dict__["embeddings"]
                if isinstance(emb_dict, dict) and "sparse" in emb_dict:
                    sparse_data = emb_dict["sparse"]
                    from qdrant_client.http.models import SparseVector

                    if isinstance(sparse_data, dict):
                        vectors["sparse"] = SparseVector(
                            indices=list(sparse_data.get("indices", [])),
                            values=list(sparse_data.get("values", [])),
                        )

            payload = HybridVectorPayload(
                chunk=chunk,
                chunk_id=chunk.chunk_id.hex,
                chunked_on=datetime.fromtimestamp(chunk.timestamp).astimezone(UTC).isoformat(),
                file_path=str(chunk.file_path) if chunk.file_path else "",
                line_start=chunk.line_range.start,
                line_end=chunk.line_range.end,
                indexed_at=datetime.now(UTC).isoformat(),
                hash=str(chunk.blake_hash),
                provider="memory",
                embedding_complete=bool(chunk.dense_batch_key and chunk.sparse_batch_key),
            )
            serialized_payload = payload.model_dump(exclude_none=True, round_trip=True)

            points.append(
                PointStruct(
                    id=chunk.chunk_id.hex,
                    vector=vectors,  # type: ignore
                    payload=serialized_payload,
                )
            )

        # Upsert points
        _result = await self._client.upsert(collection_name=collection_name, points=points)

    async def delete_by_file(self, file_path: Path) -> None:
        """Delete all chunks for a specific file.

        Args:
            file_path: File path to remove from index.

        Raises:
            CollectionNotFoundError: Collection doesn't exist.
            DeleteError: Delete operation failed.
        """
        if not self._client:
            raise ProviderError("Qdrant client is not initialized")
        collection_name = self.collection
        if not collection_name:
            raise ProviderError("No collection configured")
        await self._ensure_collection(collection_name)
        from qdrant_client.models import FieldCondition, MatchValue
        from qdrant_client.models import Filter as QdrantFilter

        _ = await self._client.delete(
            collection_name=collection_name,
            points_selector=QdrantFilter(
                must=[FieldCondition(key="file_path", match=MatchValue(value=str(file_path)))]
            ),
        )

    async def delete_by_id(self, ids: list[UUID4]) -> None:
        """Delete chunks by their unique identifiers.

        Args:
            ids: List of chunk IDs to delete.

        Raises:
            CollectionNotFoundError: Collection doesn't exist.
            DeleteError: Delete operation failed.
        """
        if not self._client:
            raise ProviderError("Qdrant client is not initialized")
        collection_name = self.collection
        if not collection_name:
            raise ProviderError("No collection configured")
        await self._ensure_collection(collection_name)
        point_ids = [str(id_) for id_ in ids]
        for i in range(0, len(point_ids), 1000):
            batch = point_ids[i : i + 1000]
            _ = await self._client.delete(collection_name=collection_name, points_selector=batch)

    async def delete_by_name(self, names: list[str]) -> None:
        """Delete chunks by their unique names.

        Args:
            names: List of chunk names to delete.

        Raises:
            CollectionNotFoundError: Collection doesn't exist.
            DeleteError: Delete operation failed.
        """
        if not self._client:
            raise ProviderError("Qdrant client is not initialized")
        collection_name = self.collection
        if not collection_name:
            raise ProviderError("No collection configured")
        await self._ensure_collection(collection_name)
        from qdrant_client.models import FieldCondition, MatchAny
        from qdrant_client.models import Filter as QdrantFilter

        _ = await self._client.delete(
            collection_name=collection_name,
            points_selector=QdrantFilter(
                must=[FieldCondition(key="chunk.chunk_name", match=MatchAny(any=names))]
            ),
        )


__all__ = ("QdrantVectorStoreProvider",)
