"""Qdrant provider for vector and hybrid search/store."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from pydantic import UUID4
from codeweaver.config.providers import QdrantConfig
from codeweaver.core.chunks import CodeChunk, SearchResult
from codeweaver.core.spans import Span
from codeweaver.engine.filter import Filter
from codeweaver.exceptions import ProviderError
from codeweaver.providers.embedding.providers import EmbeddingProvider
from codeweaver.providers.provider import Provider
from codeweaver.providers.reranking import RerankingProvider
from codeweaver.providers.vector_stores.base import VectorStoreProvider
QdrantClient = None
try:
    from qdrant_client import AsyncQdrantClient
except ImportError as e:
    raise ProviderError('Qdrant client is required for QdrantVectorStore. Install it with: pip install qdrant-client') from e

class QdrantVectorStore(VectorStoreProvider[AsyncQdrantClient]):
    """Qdrant vector store provider supporting local and remote deployments.

    Supports hybrid search with dense and sparse embeddings via named vectors.
    """
    _client: AsyncQdrantClient | None = None
    _embedder: EmbeddingProvider[Any]
    _reranker: RerankingProvider[Any] | None = None
    config: QdrantConfig
    _metadata: dict[str, Any] | None = None
    _provider: Provider = Provider.QDRANT

    @property
    def base_url(self) -> str | None:
        """The base URL for the Qdrant server.

        Returns:
            Qdrant server URL or None if using default localhost.
        """
        return self.config.get('url')

    @property
    def collection(self) -> str | None:
        """Name of the currently configured collection.

        Returns:
            Collection name from config or None.
        """
        return self.config.get('collection_name')

    def _telemetry_keys(self) -> dict[str, str] | None:
        """Get telemetry keys for the provider.

        Returns:
            None (no special telemetry handling needed).
        """
        return None

    async def _initialize(self) -> None:
        """Initialize Qdrant client and ensure collection exists.

        Raises:
            ConnectionError: Failed to connect to Qdrant server.
            ProviderError: Client initialization failed.
        """
        url = self.config.get('url', 'http://localhost:6333')
        api_key = self.config.get('api_key')
        prefer_grpc = self.config.get('prefer_grpc', False)
        self._client = AsyncQdrantClient(url=url, api_key=str(api_key) if api_key else None, prefer_grpc=prefer_grpc)
        collection_name = self.collection
        if collection_name:
            await self._ensure_collection(collection_name)

    async def _ensure_collection(self, collection_name: str, dense_dim: int=768) -> None:
        """Ensure collection exists, creating it if necessary.

        Args:
            collection_name: Name of the collection to ensure exists.
            dense_dim: Dimension of dense vectors (default 768).
        """
        from qdrant_client.models import Distance, VectorParams
        collections = await self._client.get_collections()
        collection_names = [col.name for col in collections.collections]
        if collection_name not in collection_names:
            await self._client.create_collection(collection_name=collection_name, vectors_config={'dense': VectorParams(size=dense_dim, distance=Distance.COSINE)}, sparse_vectors_config={'sparse': {}})

    async def list_collections(self) -> list[str] | None:
        """List all collections in the Qdrant instance.

        Returns:
            List of collection names.

        Raises:
            ConnectionError: Failed to connect to Qdrant server.
            ProviderError: Qdrant operation failed.
        """
        collections = await self._client.get_collections()
        return [col.name for col in collections.collections]

    async def search(self, vector: list[float] | dict[str, list[float] | Any], query_filter: Filter | None=None) -> list[SearchResult]:
        """Search for similar vectors using dense, sparse, or hybrid search.

        Args:
            vector: Query vector (list for dense-only or dict for hybrid).
            query_filter: Optional filter for search results.

        Returns:
            List of search results sorted by relevance score.

        Raises:
            CollectionNotFoundError: Collection doesn't exist.
            DimensionMismatchError: Vector dimension doesn't match collection.
            SearchError: Search operation failed.
        """
        collection_name = self.collection
        if not collection_name:
            raise ProviderError('No collection configured')
        await self._ensure_collection(collection_name)
        if isinstance(vector, list):
            query_vector = 'dense'
            query_value = vector
        elif vector.get('dense'):
            query_vector = 'dense'
            query_value = vector['dense']
        elif vector.get('sparse'):
            query_vector = 'sparse'
            query_value = vector['sparse']
        else:
            raise ProviderError("No valid vector provided (expected 'dense' or 'sparse' key in dict)")
        try:
            qdrant_filter = None
            if query_filter:
                pass
            if query_vector == 'sparse' and isinstance(query_value, dict):
                from qdrant_client.models import SparseVector
                query_value = SparseVector(indices=query_value.get('indices', []), values=query_value.get('values', []))
            results = await self._client.query_points(collection_name=collection_name, query=query_value, using=query_vector, limit=100, with_payload=True, with_vectors=False, query_filter=qdrant_filter)
            search_results: list[SearchResult] = []
            for point in results.points:
                payload = point.payload or {}
                from uuid import UUID
                chunk = CodeChunk.model_construct(chunk_id=UUID(payload['chunk_id']) if payload.get('chunk_id') else None, chunk_name=payload.get('chunk_name'), file_path=Path(payload['file_path']) if payload.get('file_path') else None, language=payload.get('language'), content=payload.get('content', ''), line_range=Span(start=payload.get('line_start', 1), end=payload.get('line_end', 1)))
                search_result = SearchResult.model_construct(content=chunk, file_path=Path(payload['file_path']) if payload.get('file_path') else None, score=point.score if point.score is not None else 0.0, metadata=None)
                search_results.append(search_result)
        except Exception as e:
            raise ProviderError(f'Search operation failed: {e}') from e
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
        if not chunks:
            return
        collection_name = self.collection
        if not collection_name:
            raise ProviderError('No collection configured')
        if chunks:
            first_embedding = chunks[0].embeddings
            dense_dim = len(first_embedding.get('dense', [])) if first_embedding else 768
            await self._ensure_collection(collection_name, dense_dim)
        from datetime import UTC, datetime
        from qdrant_client.models import PointStruct
        points = []
        for chunk in chunks:
            vectors: dict[str, list[float]] = {}
            if chunk.embeddings.get('dense'):
                vectors['dense'] = chunk.embeddings['dense']
            if chunk.embeddings.get('sparse'):
                sparse = chunk.embeddings['sparse']
                vectors['sparse'] = sparse
            payload = {'chunk_id': str(chunk.chunk_id), 'chunk_name': chunk.chunk_name, 'file_path': str(chunk.file_path), 'language': chunk.language.value if chunk.language else None, 'content': chunk.content, 'line_start': chunk.line_start, 'line_end': chunk.line_end, 'indexed_at': datetime.now(UTC).isoformat(), 'provider_name': 'qdrant', 'embedding_complete': bool(chunk.embeddings.get('dense') and chunk.embeddings.get('sparse'))}
            points.append(PointStruct(id=str(chunk.chunk_id), vector=vectors, payload=payload))
        await self._client.upsert(collection_name=collection_name, points=points)

    async def delete_by_file(self, file_path: Path) -> None:
        """Delete all chunks for a specific file.

        Args:
            file_path: File path to remove from index.

        Raises:
            CollectionNotFoundError: Collection doesn't exist.
            DeleteError: Delete operation failed.
        """
        collection_name = self.collection
        if not collection_name:
            raise ProviderError('No collection configured')
        await self._ensure_collection(collection_name)
        from qdrant_client.models import FieldCondition, MatchValue
        from qdrant_client.models import Filter as QdrantFilter
        await self._client.delete(collection_name=collection_name, points_selector=QdrantFilter(must=[FieldCondition(key='file_path', match=MatchValue(value=str(file_path)))]))

    async def delete_by_id(self, ids: list[UUID4]) -> None:
        """Delete chunks by their unique identifiers.

        Args:
            ids: List of chunk IDs to delete.

        Raises:
            CollectionNotFoundError: Collection doesn't exist.
            DeleteError: Delete operation failed.
        """
        collection_name = self.collection
        if not collection_name:
            raise ProviderError('No collection configured')
        await self._ensure_collection(collection_name)
        point_ids = [str(id_) for id_ in ids]
        for i in range(0, len(point_ids), 1000):
            batch = point_ids[i:i + 1000]
            await self._client.delete(collection_name=collection_name, points_selector=batch)

    async def delete_by_name(self, names: list[str]) -> None:
        """Delete chunks by their unique names.

        Args:
            names: List of chunk names to delete.

        Raises:
            CollectionNotFoundError: Collection doesn't exist.
            DeleteError: Delete operation failed.
        """
        collection_name = self.collection
        if not collection_name:
            raise ProviderError('No collection configured')
        await self._ensure_collection(collection_name)
        from qdrant_client.models import FieldCondition, MatchAny
        from qdrant_client.models import Filter as QdrantFilter
        await self._client.delete(collection_name=collection_name, points_selector=QdrantFilter(must=[FieldCondition(key='chunk_name', match=MatchAny(any=names))]))
__all__ = ('QdrantVectorStore',)