# sourcery skip: no-complex-if-expressions
# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Defines a base class for the Qdrant and In Memory Qdrant vector stores to reduce code duplication."""

from __future__ import annotations

import logging

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent
from typing import Any, ClassVar, Literal, NoReturn, cast

from pydantic import UUID7
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    CollectionInfo,
    Document,
    PointStruct,
    QueryResponse,
    SparseVector,
    SparseVectorParams,
    UpdateResult,
    VectorParams,
)

from codeweaver.core import (
    INJECTED,
    CodeChunk,
    Provider,
    ProviderError,
    ResolvedProjectNameDep,
    SearchResult,
    SearchStrategy,
    StrategizedQuery,
)
from codeweaver.core import SparseEmbedding as CodeWeaverSparseEmbedding
from codeweaver.core.exceptions import ConfigurationError
from codeweaver.providers.config import QdrantVectorStoreProviderSettings
from codeweaver.providers.types import EmbeddingCapabilityGroup
from codeweaver.providers.vector_stores.base import MixedQueryInput, VectorStoreProvider
from codeweaver.providers.vector_stores.metadata import CollectionMetadata, HybridVectorPayload
from codeweaver.providers.vector_stores.search import Filter


logger = logging.getLogger(__name__)


def _project_name(name: ResolvedProjectNameDep = INJECTED) -> str:
    """Return the resolved project name."""
    return name


class QdrantBaseProvider(VectorStoreProvider[AsyncQdrantClient], ABC):
    """Base class for Qdrant and In Memory Qdrant vector stores with shared functionality."""

    client: AsyncQdrantClient
    caps: EmbeddingCapabilityGroup
    config: QdrantVectorStoreProviderSettings
    _provider: ClassVar[Literal[Provider.QDRANT, Provider.MEMORY]]

    @property
    def base_url(self) -> str | None:
        """Get the base URL for the Qdrant instance."""
        return str(self.config.client_options.url)

    @property
    def collection_name(self) -> str:
        """Get the collection name for the Qdrant instance."""
        # we ensure it's set when the config initializes
        return cast(str, self.config.collection.collection_name)

    def _telemetry_keys(self) -> None:
        return None

    async def _metadata(self) -> CollectionMetadata | None:
        """Get the collection metadata."""
        collection = await self.get_collection(collection_name=self.collection_name)
        if (
            collection
            and collection.config
            and hasattr(collection.config, "metadata")
            and collection.config.metadata
        ):
            return CollectionMetadata.model_validate(collection.config.metadata)
        return None

    async def collection_info(self) -> CollectionMetadata | None:
        """Get the collection metadata."""
        return await self._metadata()

    def _create_metadata_from_config(self) -> CollectionMetadata:
        """Create CollectionMetadata from config.collection (source of truth).

        This is used both for creating new collections and validating existing ones.
        Config.collection should already have dimension/datatype resolved via apply_resolved_config().

        Returns:
            CollectionMetadata configured from provider settings.
        """
        return CollectionMetadata.model_construct({
            "provider": type(self)._provider.variable,
            "created_at": datetime.now(UTC),
            "project_name": _project_name(),
            "collection_name": self.collection_name,
            "dense_model": self.embedding_capabilities.dense_model,
            "sparse_model": self.embedding_capabilities.sparse_model,
            # TODO: Add backup model property here once added
            "backup_enabled": self.config.as_backup,
        })

    async def _initialize(self) -> None:
        """Initialize the Qdrant provider with configurations."""
        await self._init_provider()

    @abstractmethod
    async def _init_provider(self) -> None:
        """Initialize the provider with necessary configurations."""

    async def list_collections(self) -> list[str] | None:
        """List all collections in the Qdrant instance.

        Returns:
            List of collection names.

        Raises:
            ConnectionError: Failed to connect to Qdrant server.
            ProviderError: Qdrant operation failed.
        """
        if not self.client:
            raise ProviderError("Qdrant client is not initialized")
        try:
            collections = await self.client.get_collections()
        except Exception as e:
            logger.warning("Failed to list collections from Qdrant")
            raise ProviderError(f"Failed to list collections: {e}") from e
        else:
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
        await self._ensure_collection(collection_name=self.collection_name)
        collection_name = self.collection_name
        strategized_vector = self._normalize_vector_input(vector)
        try:
            results = await self._execute_search_query(strategized_vector, collection_name)
        except Exception as e:
            raise ProviderError(f"Search operation failed: {e}") from e
        else:
            return self._convert_search_results(results, strategized_vector)

    async def _ensure_collection(self, collection_name: str, dense_dim: int | None = None) -> None:
        """Ensure collection exists, creating it if necessary.

        Args:
            collection_name: Name of the collection to ensure exists.
            dense_dim: Dimension of dense vectors (deprecated - config is source of truth).
        """
        if collection_name in self._known_collections:
            return
        if not self.client:
            raise ProviderError("Qdrant client is not initialized")
        try:
            if await self.client.collection_exists(collection_name):
                self._known_collections.add(collection_name)
                # Validate existing collection matches current config
                await self._validate_collection_config(collection_name)
                return

            # Create new collection from config.collection (source of truth)
            metadata = self._create_metadata_from_config()
            await self.client.create_collection(**{
                await self.config.get_collection_config(metadata=metadata)
            })
            self._known_collections.add(collection_name)
        except UnexpectedResponse as e:
            raise ProviderError(
                "The vector store provider encountered an error when trying to check if the collection existed, or when trying to create it."
            ) from e
        else:
            return

    async def _validate_collection_config(self, collection_name: str) -> None:
        """Validate that existing collection configuration matches current provider settings.

        Checks for dimension mismatches (critical) and configuration drift (warnings).

        Args:
            collection_name: Name of the collection to validate.

        Raises:
            DimensionMismatchError: Collection dimension doesn't match configured dimension.
        """

        def _raise_dimension_error() -> NoReturn:
            from codeweaver.core import DimensionMismatchError

            raise DimensionMismatchError(
                dedent(
                    f"                Collection '{collection_name}' has {actual_dense.size}-dimensional vectors but current configuration specifies {expected_dense.size} dimensions.\n\n                This typically happens when:\n\n                    • The embedding model changed (e.g., switched providers or model versions)\n                    • The embedding configuration changed\n                    • The collection was created with different settings\n                "
                ),
                details={
                    "collection": collection_name,
                    "actual_dimension": actual_dense.size,
                    "expected_dimension": expected_dense.size,
                    "resolution_command": "cw index --force --clear",
                },
                suggestions=[
                    "  1. Rebuild the collection: cw index --force --clear",
                    "  2. Or revert to the embedding model and settings that created this collection",
                ],
            )

        def _raise_configuration_error(
            message: str, suggestions: list[str] | None = None
        ) -> NoReturn:
            raise ConfigurationError(message, suggestions=suggestions)

        try:
            collection_info = await self.client.get_collection(collection_name)
            if collection_name != self.config.collection.collection_name:
                _raise_configuration_error(
                    f"Collection name '{collection_name}' does not match the configured collection name '{self.config.collection.collection_name}'"
                )
            store_config = collection_info.config
            store_params = store_config.params
            actual_dense = store_params.vectors.get("dense")
            expected_dense = (await self.config.collection.params()).vectors.get("dense")
            # We flatten the vector configs to make sure ours matches the existing collection's config
            # This is the quick route -- there are some config changes that aren't problems
            flattened_params = cast(dict[str, Any], store_params.vectors) | cast(
                dict[str, Any], store_params.sparse_vectors
            )
            our_flattened_params = cast(
                dict[str, Any], (await self.config.collection.params()).vectors
            ) | cast(dict[str, Any], (await self.config.collection.params()).sparse_vectors)
            # if all vector configs are the same then we can skip further validation
            if all(item for item in flattened_params.items() if item in our_flattened_params):
                return
            problems = tuple(
                item for item in flattened_params.items() if item not in our_flattened_params
            )
            for key, value in problems:
                logger.debug(
                    "Vector config mismatch for collection '%s': %s in collection %s vs %s in current config",
                    key,
                    value,
                    collection_name,
                    our_flattened_params.get(key),
                )
                if not (ours := our_flattened_params.get(key)):
                    # a missing vector is not necessarily a problem, but we log a warning
                    logger.warning(
                        "Vector config for key '%s' in collection '%s' is missing in current config",
                        key,
                        collection_name,
                    )
                    # we can add the missing vector to our config if needed
                    if isinstance(value, VectorParams):
                        self.config.collection.vectors_config[key] = value  # ty:ignore[invalid-assignment]
                    else:
                        self.config.collection.sparse_vectors_config[key] = value  # ty:ignore[invalid-assignment]
                        continue
                elif isinstance(value, VectorParams) and all(
                    (k, v)
                    for k, v in value.model_dump().items()
                    if k in ("size", "datatype") and v == getattr(ours, k, None)
                ):
                    # these are the important keys that need to match up
                    # since they do match, we can skip further validation
                    continue
                elif isinstance(value, VectorParams):
                    if getattr(value, "size", None) != getattr(ours, "size", None):
                        _raise_dimension_error()
                    if getattr(value, "datatype", None) != getattr(ours, "datatype", None):
                        _raise_configuration_error(
                            f"Collection '{collection_name}' has a vector config for key '{key}' with datatype '{value.datatype}' that does not match the current config datatype '{ours.datatype}'",
                            suggestions=[
                                "You need to update your vector config's datatype to match the existing collection's config",
                                "You may also force a reindex of the collection to apply the new config with `cw index --force --clear`",
                                "Finally, you can preserve your collection and index with new settings by setting a new collection name in your config.",
                            ],
                        )
                elif isinstance(value, SparseVectorParams) and (
                    ours := self.config.collection.sparse_vectors_config.get(key)
                ):
                    if ours.datatype == value.datatype:
                        continue
                    _raise_configuration_error(
                        f"Collection '{collection_name}' has a sparse vector config for key '{key}' with datatype '{value.datatype}' that does not match the current config datatype '{ours.datatype}'",
                        suggestions=[
                            "You need to update your sparse vector config's datatype to match the existing collection's config",
                            "You may also force a reindex of the collection to apply the new config with `cw index --force --clear`",
                            "Finally, you can preserve your collection and index with new settings by setting a new collection name in your config.",
                        ],
                    )
                    continue
                if isinstance(value, SparseVectorParams) and not (
                    ours := self.config.collection.sparse_vectors_config.get(key)
                ):
                    # The collection is the source of truth here; if the configs match with different keys, we use the collection's key
                    if value in self.config.collection.sparse_vectors_config.values():
                        cast(dict, self.config.collection.sparse_vectors_config)[key] = cast(
                            dict, self.config.collection.sparse_vectors_config
                        ).pop(
                            next(
                                k
                                for k, v in self.config.collection.sparse_vectors_config.items()
                                if value == v
                            )
                        )
                    self.config.collection.sparse_vectors_config[key] = value  # ty:ignore[invalid-assignment]
                    continue
        except Exception as e:
            logger.debug(
                "Could not validate collection config for '%s'", collection_name, exc_info=e
            )

    async def create_payload_index(
        self,
        collection_name: str,
        field_name: str,
        field_schema: Literal[
            "keyword", "integer", "float", "geo", "text", "datetime", "bool", "uuid"
        ],
    ) -> UpdateResult:
        """Create a payload index on the specified field.

        Args:
            collection_name: Name of the collection.
            field_name: Name of the payload field to index.
            key_type: field value's data or schema type (what kind of data will be indexed)

        Raises:
            ProviderError: Qdrant operation failed.

        Returns:
            UpdateResult: Response from Qdrant after creating the index.
        """
        await self._ensure_collection(collection_name=collection_name)
        try:
            return await self.client.create_payload_index(
                collection_name=collection_name, field_name=field_name, field_schema=field_schema
            )
        except Exception as e:
            logger.warning(
                "Failed to create payload index on '%s' in collection '%s'",
                field_name,
                collection_name,
                extra={"error": str(e)},
            )
            raise ProviderError(f"Failed to create payload index on '{field_name}': {e}") from e

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
        args = {
            "limit": 100,
            "with_payload": True,
            "query_filter": qdrant_filter or None,
            "with_vectors": False,
        }
        if vector.is_hybrid():
            query_params = vector.to_hybrid_query(
                query_options=args, kwargs={"collection_name": collection_name}
            )
            import logging

            logger = logging.getLogger(__name__)
            logger.info("Hybrid query dict keys: %s", query_params.keys())
            logger.info("Query type: %s", type(query_params.get("query")))
            prefetch = query_params.get("prefetch", [])
            prefetch_len = len(prefetch) if isinstance(prefetch, list) else 0
            logger.info("Prefetch length: %s", prefetch_len)
            if isinstance(prefetch, list) and prefetch:
                for i, p in enumerate(prefetch):
                    logger.info(
                        "Prefetch[%d]: query type=%s, using=%s",
                        i,
                        type(p.query),
                        getattr(p, "using", None),
                    )
            response = await self.client.query_points(**query_params)
        else:
            response = await self.client.query_points(
                **vector.to_query(kwargs=args | {"collection_name": collection_name})
            )
        return response.points if hasattr(response, "points") else response

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
        from codeweaver.core import SparseEmbedding, StrategizedQuery

        if isinstance(vector, StrategizedQuery):
            return vector
        sparse, dense = (None, None)
        if isinstance(vector, dict):
            if "indices" in vector and "values" in vector:
                sparse = SparseEmbedding(
                    indices=vector["indices"],
                    values=[float(x) if isinstance(x, int) else x for x in vector["values"]],
                )
            elif "sparse" in vector:
                sparse = SparseEmbedding(
                    indices=vector["sparse"].get("indices", []),
                    values=[
                        float(x) if isinstance(x, int) else x
                        for x in vector["sparse"].get("values", [])
                    ],
                )
            if "dense" in vector:
                dense = [float(x) if isinstance(x, int) else x for x in vector["dense"]]
        elif isinstance(vector, list | tuple):
            dense = [float(x) if isinstance(x, int) else x for x in vector]
        strategy = (
            SearchStrategy.HYBRID_SEARCH
            if dense and sparse
            else SearchStrategy.DENSE_ONLY
            if dense
            else SearchStrategy.SPARSE_ONLY
        )
        return StrategizedQuery(query="unavailable", dense=dense, sparse=sparse, strategy=strategy)

    def _convert_search_results(self, results: Any, vector: StrategizedQuery) -> list[SearchResult]:
        """Convert Qdrant results to SearchResult objects.

        Args:
            results: Raw Qdrant search results.
            vector: Original strategized query.

        Returns:
            List of SearchResult objects.
        """
        from codeweaver.core import SearchResult

        points = results.points if isinstance(results, QueryResponse) else results
        search_results: list[SearchResult] = []
        for point in points:
            payload = HybridVectorPayload.model_validate(point.payload or {})
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

        from codeweaver.core import EmbeddingBatchInfo

        vectors: dict[str, Any] = {}
        if chunk.dense_embeddings:
            dense_info = chunk.dense_embeddings
            if isinstance(dense_info, EmbeddingBatchInfo):
                vectors["dense"] = list(dense_info.embeddings)
            else:
                vectors["dense"] = list(dense_info)
        if sparse_info := chunk.sparse_embeddings:
            if isinstance(sparse_info, EmbeddingBatchInfo):
                sparse_emb = sparse_info.embeddings
                if isinstance(sparse_emb, CodeWeaverSparseEmbedding):
                    self._prepare_sparse_vector_data(sparse_emb, SparseVector, vectors)
            elif isinstance(sparse_info, CodeWeaverSparseEmbedding):
                self._prepare_sparse_vector_data(sparse_info, SparseVector, vectors)
        if not sparse_info:
            vectors["sparse"] = Document(text=chunk.content, model="qdrant/bm25")
        return vectors

    def _prepare_sparse_vector_data(
        self,
        sparse_embedding: CodeWeaverSparseEmbedding,
        sparse_vector: SparseVector,
        vectors: dict[str, Any],
    ):
        indices = sparse_embedding.indices
        values = sparse_embedding.values
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
        vectors["sparse"] = sparse_vector.model_validate({
            "indices": normed_indices,
            "values": normed_values,
        })

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
            provider=self._provider.variable,
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
        if not self.client:
            raise ProviderError("Qdrant client is not initialized")
        target_collection = collection_name or self.collection_name
        if not target_collection:
            raise ProviderError("No collection specified for deletion")
        try:
            collections = await self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            if target_collection not in collection_names:
                logger.info("Collection '%s' does not exist, nothing to delete", target_collection)
                return False
            await self.client.delete_collection(collection_name=target_collection)
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
        collection_name = self.collection_name
        if not collection_name:
            raise ProviderError("No collection configured")
        await self._ensure_collection(collection_name)
        from qdrant_client.models import FieldCondition, MatchValue
        from qdrant_client.models import Filter as QdrantFilter

        _ = await self.client.delete(
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
        try:
            await self._ensure_collection(collection_name=collection_name)
        except Exception as e:
            raise ProviderError(
                f"Failed to get collection '{collection_name}': {e}",
                details={"collection": collection_name, "error": str(e)},
            ) from e
        else:
            return await self.client.get_collection(collection_name=collection_name)

    async def delete_by_id(self, ids: list[UUID7]) -> None:
        """Delete chunks by their unique identifiers.

        Args:
            ids: List of chunk IDs to delete.
        """
        collection_name = self.collection_name
        if not collection_name:
            raise ProviderError("No collection configured")
        await self._ensure_collection(collection_name)
        point_ids = [id_.hex for id_ in ids]
        for i in range(0, len(point_ids), 1000):
            batch = point_ids[i : i + 1000]
            await self.client.delete(collection_name=collection_name, points_selector=batch)
        await self.handle_persistence()

    async def delete_by_name(self, names: list[str]) -> None:
        """Delete chunks by their unique names.

        Args:
            names: List of chunk names to delete.
        """
        collection_name = self.collection_name
        if not collection_name:
            raise ProviderError("No collection configured")
        await self._ensure_collection(collection_name)
        from qdrant_client.models import FieldCondition, MatchAny
        from qdrant_client.models import Filter as QdrantFilter

        _ = await self.client.delete(
            collection_name=collection_name,
            points_selector=QdrantFilter(
                must=[FieldCondition(key="chunk.chunk_name", match=MatchAny(any=names))]
            ),
        )
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
                PointStruct(id=chunk.chunk_id.hex, vector=vectors, payload=serialized_payload)
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
        await self._ensure_collection(collection_name=self.collection_name)
        collection_name = self.collection_name
        if not collection_name:
            raise ProviderError("No collection configured")
        points = self._chunks_to_points(chunks)
        _result = await self.client.upsert(collection_name=collection_name, points=points)
        await self.handle_persistence()

    async def migrate_to(
        self,
        dest_client: AsyncQdrantClient,
        collection_names: list[str] | None = None,
        batch_size: int = 100,
    ) -> None:
        """Migrate data from this provider's client to a destination client.

        Args:
            dest_client: Destination Qdrant client.
            collection_names: Specific collections to migrate (default: all).
            batch_size: Batch size for scrolling and upserting.

        Raises:
            ProviderError: If client is not initialized.
        """
        if not self.client:
            raise ProviderError("Qdrant client not initialized")
        await self._migrate_data(self.client, dest_client, collection_names, batch_size)

    async def migrate_from(
        self,
        source_client: AsyncQdrantClient,
        collection_names: list[str] | None = None,
        batch_size: int = 100,
    ) -> None:
        """Migrate data from a source client to this provider's client.

        Args:
            source_client: Source Qdrant client.
            collection_names: Specific collections to migrate (default: all).
            batch_size: Batch size for scrolling and upserting.

        Raises:
            ProviderError: If client is not initialized.
        """
        if not self.client:
            raise ProviderError("Qdrant client not initialized")
        await self._migrate_data(source_client, self.client, collection_names, batch_size)

    @staticmethod
    async def _migrate_data(  # noqa: C901
        source_client: AsyncQdrantClient,
        dest_client: AsyncQdrantClient,
        collection_names: list[str] | None = None,
        batch_size: int = 100,
    ) -> None:
        """Migrate data between two Qdrant clients."""
        try:
            collections_resp = await source_client.get_collections()
        except Exception:
            # Source might be empty or invalid
            logger.warning("Failed to get collections from source client during migration")
            return

        source_collections = [c.name for c in collections_resp.collections]
        target_collections = collection_names or source_collections

        for col_name in target_collections:
            if col_name not in source_collections:
                continue

            # Get collection info to recreate config
            try:
                col_info = await source_client.get_collection(col_name)
            except Exception as e:
                logger.warning("Failed to get info for collection %s: %s", col_name, e)
                continue

            # Check if exists in dest
            try:
                await dest_client.get_collection(col_name)
            except Exception:
                # Recreate collection
                if col_info.config and col_info.config.params:
                    vectors_config = col_info.config.params.vectors
                    sparse_vectors_config = col_info.config.params.sparse_vectors

                    try:
                        await dest_client.create_collection(
                            collection_name=col_name,
                            vectors_config=vectors_config,
                            sparse_vectors_config=sparse_vectors_config,
                        )
                    except Exception:
                        logger.exception("Failed to create collection %s in destination", col_name)
                        continue
                else:
                    logger.warning("Skipping collection %s: Missing configuration", col_name)
                    continue

            # Scroll and upsert
            offset = None
            while True:
                try:
                    points, next_offset = await source_client.scroll(
                        collection_name=col_name,
                        limit=batch_size,
                        offset=offset,
                        with_payload=True,
                        with_vectors=True,
                    )

                    if points:
                        await dest_client.upsert(collection_name=col_name, points=points)

                    offset = next_offset
                    if offset is None:
                        break
                except Exception:
                    logger.exception("Error migrating points for collection %s", col_name)
                    break


__all__ = ("QdrantBaseProvider",)
