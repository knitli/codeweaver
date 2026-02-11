# sourcery skip: lambdas-should-be-short, no-complex-if-expressions
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
from typing import TYPE_CHECKING, Any, ClassVar, Literal, NoReturn, cast

from pydantic import UUID7
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import (
    CollectionInfo,
    Document,
    PointStruct,
    QueryResponse,
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
from codeweaver.core.constants import DEFAULT_VECTOR_STORE_MAX_RESULTS
from codeweaver.core.exceptions import ConfigurationError
from codeweaver.providers.config import QdrantVectorStoreProviderSettings
from codeweaver.providers.embedding.capabilities import EmbeddingModelCapabilities
from codeweaver.providers.types import EmbeddingCapabilityGroup
from codeweaver.providers.vector_stores.base import MixedQueryInput, VectorStoreProvider
from codeweaver.providers.vector_stores.metadata import CollectionMetadata, HybridVectorPayload
from codeweaver.providers.vector_stores.search import Filter


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from codeweaver.providers.embedding.registry import EmbeddingRegistry
    from codeweaver.providers.vector_stores.qdrant_service import QdrantVectorStoreService


def _project_name(name: ResolvedProjectNameDep = INJECTED) -> str:
    """Return the resolved project name."""
    return name


class QdrantBaseProvider(VectorStoreProvider[AsyncQdrantClient], ABC):
    """Base class for Qdrant and In Memory Qdrant vector stores with shared functionality."""

    client: AsyncQdrantClient
    caps: EmbeddingCapabilityGroup
    config: QdrantVectorStoreProviderSettings
    _provider: ClassVar[Literal[Provider.QDRANT, Provider.MEMORY]]
    _service: QdrantVectorStoreService | None = None

    @property
    def service(self) -> QdrantVectorStoreService:
        """Get the QdrantVectorStoreService for this provider.

        Lazy-initialized on first access. Uses existing config and caps.
        For failover settings, attempts to resolve from DI container.

        Returns:
            QdrantVectorStoreService instance
        """
        if self._service is None:
            from codeweaver.providers.vector_stores.qdrant_service import QdrantVectorStoreService

            # Note: Failover settings require async DI resolution
            # Since we're in a sync property, we can't use container.resolve()
            # The service will handle None failover settings gracefully
            failover_settings = None
            failover_detector = None

            self._service = QdrantVectorStoreService(
                settings=self.config,
                embedding_group=self.caps,
                failover_settings=failover_settings,
                failover_detector=failover_detector,
            )

        return self._service

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
        # Get model family if available from dense capability
        model_family_id = None
        if (
            self.caps.dense
            and self.caps.dense.capability
            and hasattr(self.caps.dense.capability, "model_family")
            and self.caps.dense.capability.model_family
        ):
            model_family_id = cast(
                EmbeddingModelCapabilities, self.caps.dense.capability
            ).model_family.family_id

        # Query model detection: Check if we're using asymmetric embedding
        # by inspecting the config type (config_type discriminator)
        query_model = None
        if (
            self.caps.dense
            and self.caps.dense.config
            and hasattr(self.caps.dense.config, "config_type")
            and self.caps.dense.config.config_type == "asymmetric"
        ):
            # This is an asymmetric config - the config should be AsymmetricEmbeddingProviderSettings
            # Import here to avoid circular dependency
            from codeweaver.providers.config.provider_kinds import (
                AsymmetricEmbeddingProviderSettings,
            )

            if isinstance(self.caps.dense.config, AsymmetricEmbeddingProviderSettings):
                query_model = str(self.caps.dense.config.query_provider.model_name)

        return CollectionMetadata.model_construct({
            "provider": type(self)._provider.variable,
            "created_at": datetime.now(UTC),
            "project_name": _project_name(),
            "collection_name": self.collection_name,
            "dense_model": self.embedding_capabilities.dense_model,
            "dense_model_family": model_family_id,
            "query_model": query_model,
            "sparse_model": self.embedding_capabilities.sparse_model,
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

    async def _validate_existing_collection(self, collection_name: str) -> None:
        """Validate metadata and configuration of an existing collection."""
        self._known_collections.add(collection_name)

        # Validate collection metadata (model family compatibility)
        existing_metadata = await self._metadata()
        if existing_metadata:
            # Create metadata from current config
            current_metadata = self._create_metadata_from_config()
            # Validate compatibility (includes family validation)
            current_metadata.validate_compatibility(existing_metadata)

        # Validate vector configs
        await self._validate_collection_config(collection_name)

    async def _create_collection(self, collection_name: str) -> None:
        """Create a new collection from the configured collection settings."""
        # Create new collection from config.collection (source of truth)
        metadata = self._create_metadata_from_config()

        # Use service to get collection config (handles WalConfig merging, etc.)
        collection_config = await self.service.get_collection_config(metadata=metadata)

        # Convert CollectionConfig to create_collection parameters
        configuration_params = collection_config.model_dump(exclude_none=True)
        params = configuration_params.pop("params", None)

        create_params = {}
        if params:
            create_params["vectors_config"] = params.get("vectors")
            create_params["sparse_vectors_config"] = params.get("sparse_vectors")
            create_params["shard_number"] = params.get("shard_number")
            create_params["replication_factor"] = params.get("replication_factor")
            create_params["write_consistency_factor"] = params.get("write_consistency_factor")
            create_params["on_disk_payload"] = params.get("on_disk_payload")

        # Map optimizer_config → optimizers_config (plural)
        if "optimizer_config" in configuration_params:
            create_params["optimizers_config"] = configuration_params.pop("optimizer_config")

        # Add remaining configs
        for key in ["hnsw_config", "wal_config", "quantization_config"]:
            if key in configuration_params:
                create_params[key] = configuration_params[key]

        await self.client.create_collection(
            collection_name=collection_name,
            **{k: v for k, v in create_params.items() if v is not None},
        )
        self._known_collections.add(collection_name)

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
                await self._validate_existing_collection(collection_name)
            else:
                await self._create_collection(collection_name)
        except UnexpectedResponse as e:
            raise ProviderError(
                "The vector store provider encountered an error when trying to check if the collection existed, or when trying to create it."
            ) from e

    def _raise_dimension_error(
        self,
        collection_name: str,
        actual_dense: VectorParams | None,
        expected_dense: VectorParams | None,
    ) -> NoReturn:
        """Raise dimension mismatch error with detailed diagnostics."""
        from codeweaver.core import DimensionMismatchError

        actual_dim = actual_dense.size if actual_dense else "unknown"
        expected_dim = expected_dense.size if expected_dense else "unknown"

        raise DimensionMismatchError(
            dedent(
                f"                Collection '{collection_name}' has {actual_dim}-dimensional vectors but current configuration specifies {expected_dim} dimensions.\n\n                This typically happens when:\n\n                    • The embedding model changed (e.g., switched providers or model versions)\n                    • The embedding configuration changed\n                    • The collection was created with different settings\n                "
            ),
            details={
                "collection": collection_name,
                "actual_dimension": actual_dim if actual_dense else None,
                "expected_dimension": expected_dim if expected_dense else None,
                "resolution_command": "cw index --force --clear",
            },
            suggestions=[
                "  1. Rebuild the collection: cw index --force --clear",
                "  2. Or revert to the embedding model and settings that created this collection",
            ],
        )

    def _validate_collection_name(self, collection_name: str) -> None:
        """Validate collection name matches configuration."""
        if collection_name != self.config.collection.collection_name:
            raise ConfigurationError(
                f"Collection name '{collection_name}' does not match the configured collection name '{self.config.collection.collection_name}'"
            )

    def _handle_missing_vector(
        self, key: str, value: VectorParams | SparseVectorParams, collection_name: str
    ) -> None:
        """Handle missing vector configuration by adding to current config."""
        logger.warning(
            "Vector config for key '%s' in collection '%s' is missing in current config",
            key,
            collection_name,
        )
        if isinstance(value, VectorParams):
            self.config.collection.vectors_config[key] = value
        else:
            self.config.collection.sparse_vectors_config[key] = value

    def _validate_dense_vector(
        self,
        key: str,
        value: VectorParams,
        ours: VectorParams,
        collection_name: str,
        actual_dense: VectorParams | None,
        expected_dense: VectorParams | None,
    ) -> None:
        """Validate dense vector parameters match configuration."""
        # Check if critical parameters match
        if all(
            (k, v)
            for k, v in value.model_dump().items()
            if k in ("size", "datatype") and v == getattr(ours, k, None)
        ):
            return

        # Validate size matches
        if getattr(value, "size", None) != getattr(ours, "size", None):
            self._raise_dimension_error(collection_name, actual_dense, expected_dense)

        # Validate datatype matches
        if getattr(value, "datatype", None) != getattr(ours, "datatype", None):
            raise ConfigurationError(
                f"Collection '{collection_name}' has a vector config for key '{key}' with datatype '{value.datatype}' that does not match the current config datatype '{ours.datatype}'",
                suggestions=[
                    "You need to update your vector config's datatype to match the existing collection's config",
                    "You may also force a reindex of the collection to apply the new config with `cw index --force --clear`",
                    "Finally, you can preserve your collection and index with new settings by setting a new collection name in your config.",
                ],
            )

    def _validate_sparse_vector(
        self, key: str, value: SparseVectorParams, collection_name: str
    ) -> None:
        """Validate sparse vector parameters match configuration."""
        ours = self.config.collection.sparse_vectors_config.get(key)

        if not ours:
            # Handle missing sparse vector by syncing with collection
            if value in self.config.collection.sparse_vectors_config.values():
                old_key = next(
                    k for k, v in self.config.collection.sparse_vectors_config.items() if value == v
                )
                cast(dict, self.config.collection.sparse_vectors_config)[key] = cast(
                    dict, self.config.collection.sparse_vectors_config
                ).pop(old_key)
            else:
                self.config.collection.sparse_vectors_config[key] = value
            return

        # Note: In qdrant-client 1.16+, SparseVectorParams no longer has a 'datatype' attribute
        # Datatype is now managed internally and doesn't need explicit validation
        # The sparse vector configuration is validated through the index and modifier parameters

    def _validate_vector_problem(
        self,
        key: str,
        value: VectorParams | SparseVectorParams,
        our_flattened_params: dict[str, Any],
        collection_name: str,
        actual_dense: VectorParams | None,
        expected_dense: VectorParams | None,
    ) -> None:
        """Validate a single vector configuration problem."""
        logger.debug(
            "Vector config mismatch for collection '%s': %s in collection %s vs %s in current config",
            key,
            value,
            collection_name,
            our_flattened_params.get(key),
        )

        ours = our_flattened_params.get(key)

        if not ours:
            self._handle_missing_vector(key, value, collection_name)
        elif isinstance(value, VectorParams):
            self._validate_dense_vector(
                key, value, ours, collection_name, actual_dense, expected_dense
            )
        elif isinstance(value, SparseVectorParams):
            self._validate_sparse_vector(key, value, collection_name)

    async def _find_dense_vectors(
        self, store_params: Any
    ) -> tuple[VectorParams | None, VectorParams | None]:
        """Find actual and expected dense vectors for dimension validation."""
        actual_dense = None
        expected_dense = None
        expected_vectors = (await self.config.collection.params()).vectors

        for vector_name, vector_config in store_params.vectors.items():
            if isinstance(vector_config, VectorParams):
                actual_dense = vector_config
                expected_dense = expected_vectors.get(vector_name)
                if expected_dense:
                    break

        return actual_dense, expected_dense

    async def _get_flattened_params(self) -> dict[str, Any]:
        """Get flattened vector and sparse vector parameters for comparison."""
        collection_params = await self.config.collection.params()
        return cast(dict[str, Any], collection_params.vectors) | cast(
            dict[str, Any], collection_params.sparse_vectors
        )

    async def _validate_collection_config(self, collection_name: str) -> None:
        """Validate that existing collection configuration matches current provider settings.

        Checks for dimension mismatches (critical) and configuration drift (warnings).

        Args:
            collection_name: Name of the collection to validate.

        Raises:
            DimensionMismatchError: Collection dimension doesn't match configured dimension.
        """
        try:
            collection_info = await self.client.get_collection(collection_name)
            self._validate_collection_name(collection_name)

            store_params = collection_info.config.params
            actual_dense, expected_dense = await self._find_dense_vectors(store_params)

            # Flatten vector configs for comparison
            flattened_params = cast(dict[str, Any], store_params.vectors) | cast(
                dict[str, Any], store_params.sparse_vectors
            )
            our_flattened_params = await self._get_flattened_params()

            # Early return if all configs match
            if all(item for item in flattened_params.items() if item in our_flattened_params):
                return

            # Validate each mismatched configuration
            problems = tuple(
                item for item in flattened_params.items() if item not in our_flattened_params
            )
            for key, value in problems:
                self._validate_vector_problem(
                    key, value, our_flattened_params, collection_name, actual_dense, expected_dense
                )

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
            "limit": DEFAULT_VECTOR_STORE_MAX_RESULTS,
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

    async def _get_registry(self) -> EmbeddingRegistry:
        """Retrieve the EmbeddingRegistry from the DI container."""
        from codeweaver.core.di.container import get_container
        from codeweaver.providers.embedding.registry import EmbeddingRegistry

        container = get_container()
        return await container.resolve(EmbeddingRegistry)

    async def _prepare_vectors(self, chunk: CodeChunk) -> dict[str, Any]:
        """Prepare vector dictionary for a code chunk.

        With role-based architecture, intent names (e.g., "primary", "sparse", "backup")
        are used directly as physical Qdrant vector names. No mapping needed.

        Args:
            chunk: Code chunk with embeddings.

        Returns:
            Dictionary mapping physical vector names to vector data.
        """
        from qdrant_client.http.models import SparseVector

        vectors: dict[str, Any] = {}
        has_sparse = False

        embedding_registry = await self._get_registry()

        # Get the ChunkEmbeddings for this chunk from the registry
        chunk_embeddings = embedding_registry.get(chunk.chunk_id)
        if chunk_embeddings is None:
            raise ProviderError(
                f"No embeddings found in registry for chunk {chunk.chunk_id}. "
                "Embeddings must be registered before upserting chunks."
            )

        # Iterate over all embeddings in the chunk
        for intent in chunk.embeddings:
            # Get the actual embedding data from the ChunkEmbeddings
            embedding_info = chunk_embeddings.embeddings.get(intent)
            if embedding_info is None:
                raise ProviderError(
                    f"No embedding found for intent '{intent}' in chunk {chunk.chunk_id}"
                )

            # Use intent name directly as physical vector name (role-based architecture)
            vector_name = intent

            # Prepare vector data based on embedding kind
            if embedding_info.is_dense:
                # Dense vector: just convert to list
                vectors[vector_name] = list(embedding_info.embeddings)
            elif embedding_info.is_sparse:
                # Sparse vector: convert to Qdrant SparseVector format
                has_sparse = True
                sparse_emb = embedding_info.embeddings
                if isinstance(sparse_emb, CodeWeaverSparseEmbedding):
                    indices = sparse_emb.indices
                    values = sparse_emb.values
                    # Normalize to lists
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
                    vectors[vector_name] = SparseVector.model_validate({
                        "indices": normed_indices,
                        "values": normed_values,
                    })

        # Fallback: if no sparse vector exists but sparse/IDF is configured, use BM25 document
        # Only add BM25 if we have sparse or IDF capabilities configured in the embedding group
        if (
            not has_sparse
            and "sparse" not in vectors
            and (self.caps.sparse is not None or self.caps.idf is not None)
        ):
            vectors["sparse"] = Document(text=chunk.content, model="qdrant/bm25")

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
        await self.delete_by_files([file_path])

    async def delete_by_files(self, file_paths: list[Path]) -> None:
        """Delete all chunks for multiple files in a single operation.

        Args:
            file_paths: List of file paths to remove from index.
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
                must=[
                    FieldCondition(
                        key="file_path", match=MatchAny(any=[str(p) for p in file_paths])
                    )
                ]
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

    async def _chunks_to_points(self, chunks: list[CodeChunk]) -> list[PointStruct]:
        """Convert code chunks to Qdrant points.

        Args:
            chunks: List of code chunks to convert.

        Returns:
            List of PointStruct objects.
        """
        points: list[PointStruct] = []
        for chunk in chunks:
            vectors = await self._prepare_vectors(chunk)
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
        points = await self._chunks_to_points(chunks)
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
