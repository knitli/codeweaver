# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: no-complex-if-expressions
"""Defines a base class for the Qdrant and In Memory Qdrant vector stores to reduce code duplication."""

import logging

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent
from typing import Any, Literal, NoReturn

from fastembed.sparse.sparse_embedding_base import SparseEmbedding
from pydantic import UUID7
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import (
    BinaryQuantization,
    Datatype,
    Distance,
    PointStruct,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)
from qdrant_client.http.models.models import CollectionInfo
from typing_extensions import TypeIs

from codeweaver.agent_api.find_code.results import SearchResult
from codeweaver.agent_api.find_code.types import StrategizedQuery
from codeweaver.config.providers import VectorStoreProviderSettings
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.types import DictView
from codeweaver.engine.search import Filter
from codeweaver.exceptions import ProviderError
from codeweaver.providers.provider import Provider
from codeweaver.providers.vector_stores.base import MixedQueryInput, VectorStoreProvider
from codeweaver.providers.vector_stores.metadata import CollectionMetadata, HybridVectorPayload


logger = logging.getLogger(__name__)


class QdrantBaseProvider(VectorStoreProvider[AsyncQdrantClient], ABC):
    """Base class for Qdrant and In Memory Qdrant vector stores with shared functionality."""

    _base_url: str | None = None
    _collection: str | None = None
    _auto_persist: bool | None = None  # only for memory provider
    _client: AsyncQdrantClient | None = None  # Placeholder for Qdrant client instance
    _provider: Literal[Provider.QDRANT, Provider.MEMORY]

    @property
    def base_url(self) -> str | None:
        """Get the base URL for the Qdrant instance."""
        return self._base_url

    @property
    def collection(self) -> str | None:
        """Get the collection name for the Qdrant instance."""
        return self._collection

    def _telemetry_keys(self) -> None:
        return None

    def _fetch_config(self) -> DictView[VectorStoreProviderSettings]:
        from codeweaver.common.registry.provider import get_provider_config_for

        return get_provider_config_for("vector_store")

    async def _metadata(self) -> CollectionMetadata | None:
        """Get the collection metadata."""
        collection = await self.get_collection(collection_name=self._collection)  # type: ignore
        if (
            collection
            and collection.config
            and hasattr(collection.config, "metadata")
            and collection.config.metadata
        ):
            return CollectionMetadata.model_validate(collection.config.metadata)  # type: ignore
        return None

    async def collection_info(self) -> CollectionMetadata | None:
        """Get the collection metadata."""
        return await self._metadata()

    @staticmethod
    def _ensure_client(client: Any) -> TypeIs[AsyncQdrantClient]:
        """Ensure the Qdrant client is initialized and ready.

        Args:
            client: The client instance to check.

        Returns:
            True if the client is initialized and ready.
        """
        return client is not None and isinstance(client, AsyncQdrantClient)

    def _generate_metadata(self) -> CollectionMetadata:
        """Generate collection metadata from current provider configuration.

        Returns:
            CollectionMetadata configured according to provider settings.
        """
        from codeweaver.common.utils.git import get_project_path
        from codeweaver.config.settings import get_settings_map

        settings_map = get_settings_map()
        project_name = (
            settings_map.get("project_name")
            if isinstance(settings_map.get("project_name"), str)
            else get_project_path().name
        )
        distance = (
            Distance.COSINE
            if self.distance_metric == "cosine"
            else Distance.DOT
            if self.distance_metric == "dot"
            else Distance.EUCLID
        )
        datatype = (
            Datatype.FLOAT32
            if self.dense_dtype == "float32"
            else Datatype.FLOAT16
            if self.dense_dtype == "float16"
            else Datatype.UINT8
        )
        quantization_config = BinaryQuantization() if self.dense_dtype == "binary" else None
        if self.dense_dtype in ("binary", "int8"):
            datatype = Datatype.UINT8
        return CollectionMetadata.model_validate({
            "provider": self._provider.variable,
            "created_at": datetime.now(UTC),
            "project_name": project_name,
            "vector_config": {
                "dense": VectorParams(
                    size=self.dense_dimension or 768,
                    distance=distance,
                    quantization_config=quantization_config,
                    datatype=datatype,
                )
            },
            "sparse_config": {
                "sparse": SparseVectorParams(index=SparseIndexParams(datatype=Datatype.FLOAT16))
            },
            "collection_name": self.config.get("collection_name")
            or self._default_collection_name(),
            "dense_model": self.dense_model,
            "sparse_model": self.sparse_model,
        })

    def _default_collection_name(self) -> str:
        """Generate a default collection name based on the provider settings."""
        from codeweaver.common.utils.git import get_project_path
        from codeweaver.config.settings import get_settings_map
        from codeweaver.core.stores import get_blake_hash
        from codeweaver.core.types.sentinel import Unset

        settings_map = get_settings_map()
        project_path = get_project_path()
        project_name = (
            project_path.name
            if isinstance(settings_map.get("project_name"), Unset)
            else settings_map.get("project_name")
        )
        return f"{project_name}_{get_blake_hash(str(project_path).encode('utf-8'))[:8]}"

    async def _initialize(self) -> None:
        """Initialize the Qdrant provider with configurations."""
        # Use explicitly provided config if available, otherwise fetch from registry
        if self.config is not None:
            # Config was provided (e.g., in tests) - use it directly
            qdrant_config = self.config
        else:
            # No config provided - fetch from global registry (production path)
            config = self._fetch_config()
            qdrant_config = config["provider_settings"]
        collection_name = qdrant_config.get("collection_name") or self._default_collection_name()
        base_url = qdrant_config.get("url") if self._provider == Provider.QDRANT else ":memory:"
        object.__setattr__(self, "_collection", collection_name)
        object.__setattr__(self, "_base_url", base_url)

        client = await self._build_client()
        object.__setattr__(self, "_client", client)

        await self._init_provider()

    @abstractmethod
    async def _init_provider(self) -> None:
        """Initialize the provider with necessary configurations."""

    @abstractmethod
    async def _build_client(self) -> AsyncQdrantClient:
        """Build and return the Qdrant client instance."""

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
        try:
            collections = await self._client.get_collections()
            return [col.name for col in collections.collections]
        except Exception as e:
            logger.exception("Failed to list collections from Qdrant")
            raise ProviderError(f"Failed to list collections: {e}") from e

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

        await self._ensure_collection(
            collection_name=self._collection or self._default_collection_name()
        )
        collection_name = self.collection
        if not collection_name:
            raise ProviderError("No collection configured")

        # Normalize input to StrategizedQuery
        strategized_vector = self._normalize_vector_input(vector)

        try:
            # Execute search query
            results = await self._execute_search_query(strategized_vector, collection_name)

            # Convert results to SearchResult objects
            return self._convert_search_results(results, strategized_vector)
        except Exception as e:
            raise ProviderError(f"Search operation failed: {e}") from e

    async def _ensure_collection(self, collection_name: str, dense_dim: int | None = None) -> None:
        """Ensure collection exists, creating it if necessary.

        Args:
            collection_name: Name of the collection to ensure exists.
            dense_dim: Dimension of dense vectors (deprecated - config is source of truth).
        """
        if not self._client:
            raise ProviderError("Qdrant client is not initialized")
        collections = await self._client.get_collections()
        collection_names = [col.name for col in collections.collections]
        if collection_name not in collection_names:
            # Create new collection from config
            _ = await self._client.create_collection(**self._generate_metadata().to_collection())
        else:
            # Validate existing collection matches current config
            await self._validate_collection_config(collection_name)

    async def _validate_collection_config(self, collection_name: str) -> None:
        """Validate that existing collection configuration matches current provider settings.

        Checks for dimension mismatches (critical) and configuration drift (warnings).

        Args:
            collection_name: Name of the collection to validate.

        Raises:
            DimensionMismatchError: Collection dimension doesn't match configured dimension.
        """

        def _raise_dimension_error() -> NoReturn:
            from codeweaver.exceptions import DimensionMismatchError

            raise DimensionMismatchError(
                dedent(f"""\
                Collection '{collection_name}' has {actual_dense.size}-dimensional vectors but current configuration specifies {expected_dense.size} dimensions.

                This typically happens when:

                    • The embedding model changed (e.g., switched providers or model versions)
                    • The embedding configuration changed
                    • The collection was created with different settings
                """),
                details={
                    "collection": collection_name,
                    "actual_dimension": actual_dense.size,
                    "expected_dimension": expected_dense.size,
                    "resolution_command": "cw index --clear",
                },
                suggestions=[
                    "  1. Rebuild the collection: cw index --clear",
                    "  2. Or revert to the embedding model and settings that created this collection",
                ],
            )

        try:
            collection_info = await self._client.get_collection(collection_name)
            expected_metadata = self._generate_metadata()

            # Get actual vector config from collection
            actual_vectors = collection_info.config.params.vectors
            if isinstance(actual_vectors, dict) and "dense" in actual_vectors:
                actual_dense = actual_vectors["dense"]
                expected_dense = expected_metadata.vector_config["dense"]

                # Check dimension mismatch (CRITICAL)
                if actual_dense.size != expected_dense.size:
                    _raise_dimension_error()
                # Check distance metric (WARNING)
                if actual_dense.distance != expected_dense.distance:
                    logger.warning(
                        "Collection '%s' uses %s distance metric "
                        "but current configuration specifies %s. "
                        "Search results may differ from expectations. "
                        "Consider rebuilding: cw index --clear",
                        collection_name,
                        actual_dense.distance.value,
                        expected_dense.distance.value,
                    )

                # Check datatype (WARNING)
                if (
                    hasattr(actual_dense, "datatype")
                    and hasattr(expected_dense, "datatype")
                    and actual_dense.datatype != expected_dense.datatype
                ):
                    logger.warning(
                        "Collection '%s' datatype mismatch: "
                        "%s (actual) vs %s (expected). "
                        "This may affect storage efficiency and precision.",
                        collection_name,
                        actual_dense.datatype.value,
                        expected_dense.datatype.value,
                    )

        except Exception as e:
            # Don't fail on validation errors - just log them
            logger.debug(
                "Could not validate collection config for '%s'", collection_name, exc_info=e
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
        qdrant_filter = None

        # Hybrid search uses query_points with FusionQuery
        if vector.is_hybrid():
            response = await self._client.query_points(
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
            # query_points returns QueryResponse with .points attribute
            return response.points if hasattr(response, "points") else response

        # Sparse-only search uses query_points with SparseVector
        if vector.has_sparse() and not vector.has_dense():
            response = await self._client.query_points(
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
            # query_points returns QueryResponse with .points attribute
            return response.points if hasattr(response, "points") else response

        # Dense-only search uses search API (returns list directly)
        return await self._client.search(
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
            if "indices" in vector and "values" in vector:
                sparse = SparseEmbedding(
                    indices=vector["indices"],  # ty: ignore[invalid-argument-type]
                    values=[float(x) if isinstance(x, int) else x for x in vector["values"]],  # ty:ignore[invalid-argument-type]
                )
            elif "sparse" in vector:
                sparse = SparseEmbedding(
                    indices=vector["sparse"].get("indices", []),  # type: ignore
                    values=[
                        float(x) if isinstance(x, int) else x
                        for x in vector["sparse"].get("values", [])
                        if vector["sparse"].get("values", [])
                    ],  # type: ignore
                )
            if "dense" in vector:
                dense = [
                    float(x) if isinstance(x, int) else x
                    for x in vector["dense"]
                    if vector["dense"]
                ]
        elif isinstance(vector, list | tuple):
            dense = [float(x) if isinstance(x, int) else x for x in vector]

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

        if chunk.sparse_embeddings and isinstance(chunk.sparse_embeddings, SparseEmbedding):
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
            hash=chunk.blake_hash,
            provider="memory",
            embedding_complete=bool(chunk.dense_batch_key and chunk.sparse_batch_key),
        )

    async def delete_collection(self, collection_name: str | None = None) -> bool:
        """Delete a vector store collection.

        Args:
            collection_name: Name of collection to delete. If None, uses configured collection.

        Returns:
            bool: True if collection was deleted, False if it didn't exist.

        Raises:
            ProviderError: If client is not initialized or operation fails.
        """
        if not self._client:
            raise ProviderError("Qdrant client is not initialized")

        target_collection = collection_name or self.collection
        if not target_collection:
            raise ProviderError("No collection specified for deletion")

        try:
            collections = await self._client.get_collections()
            collection_names = [col.name for col in collections.collections]

            if target_collection not in collection_names:
                logger.info("Collection '%s' does not exist, nothing to delete", target_collection)
                return False

            await self._client.delete_collection(collection_name=target_collection)
            logger.info("Successfully deleted collection '%s'", target_collection)

        except Exception as e:
            raise ProviderError(
                f"Failed to delete collection '{target_collection}': {e}",
                details={"collection": target_collection, "error": str(e)},
            ) from e
        else:
            return True

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

        await self.handle_persistence()

    async def handle_persistence(self) -> None:
        """This is no-op, but implemented by the memory provider to trigger persistence."""

    async def get_collection(self, collection_name: str) -> CollectionInfo:
        """Get collection details.

        Args:
            collection_name: Name of the collection to retrieve.

        Returns:
            Collection information as CollectionInfo from Qdrant.

        Raises:
            ProviderError: If client is not initialized or operation fails.
        """
        if not self._ensure_client(self._client):
            raise ProviderError("Qdrant client not initialized")
        try:
            return await self._client.get_collection(collection_name=collection_name)
        except Exception as e:
            raise ProviderError(
                f"Failed to get collection '{collection_name}': {e}",
                details={"collection": collection_name, "error": str(e)},
            ) from e

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

        await self.handle_persistence()

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
        await self.handle_persistence()

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

        await self.handle_persistence()


__all__ = ("QdrantBaseProvider",)
