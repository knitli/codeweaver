# CodeWeaver Failover Architecture - Revised Implementation Plan

**Date**: 2026-01-19
**Status**: Design Complete - Implementation Ready
**Priority**: High - Alpha Release 3 Target
**Replaces**: Previous failover plan (2026-01-18)

---

## Executive Summary

This plan details a **radically simplified** failover implementation that leverages Qdrant's named vectors feature and naive reconciliation to provide seamless provider failover with minimal complexity and overhead.

**Key Simplifications from Original Plan:**
- ✅ **Single collection** with named vectors (no primary/backup collections)
- ✅ **Single chunk granularity** (~7000 tokens works for all providers)
- ✅ **No state machine** (collection state = system state)
- ✅ **No provider modifications** (all logic in service layer)
- ✅ **Conditional overhead** (only enabled for cloud providers)
- ✅ **Self-healing** (automatic gap detection and filling)

**Implementation Effort:** 4 weeks (vs 8 weeks in original plan)

---

## Table of Contents

1. [Architectural Overview](#architectural-overview)
2. [Core Design Decisions](#core-design-decisions)
3. [Current State Analysis](#current-state-analysis)
4. [Required Changes](#required-changes)
5. [Implementation Phases](#implementation-phases)
6. [Testing Strategy](#testing-strategy)
7. [Success Metrics](#success-metrics)

---

## Architectural Overview

### **System Context**

**Current Reality:**
- CodeWeaver runs as **continuously-running daemon**
- Indexing happens on startup and file changes (not on MCP requests)
- File watcher monitors changes in real-time
- MCP requests query already-indexed data
- Provider failures impact indexing, not just search

**Design Insight:**
- **All sparse embedders are local** (fastembed, sentence-transformers)
- **Backup embedding + reranking models** now have 8192 token context windows
- **Chunk size cap** of ~7500 tokens works for all providers as top limit (adjusted down by lowest context window across primary dense embedder and reranker)
- **No multi-granularity chunking needed!**
- **Preemptive turn off** If dense embedding provider is local, turn off backup system

### **High-Level Architecture**

```
┌─────────────────────────────────────────────────────────┐
│              Daemon Startup / File Change               │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              ChunkingService (Single Granularity)        │
│              Chunk Limit: max ~7500 tokens                   │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│         EmbeddingService (Conditional Backup)            │
│  ┌─────────────────────────────────────────────────┐   │
│  │ Sparse (Always): SPLADE / BM-25                 │   │
│  │ Dense Primary:  Cloud (i.e. voyage) or local    │   │
│  │ Dense Backup: jinaai/jina-v2-small (if cloud primary)
│  └─────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
NOTE: This point setup may not be the right approach, needs discussion
┌─────────────────────────────────────────────────────────┐
│   Qdrant Collection (Named Vectors - Single Collection) │
│                                                           │
│   Point Structure:                                        │
│   {                                                       │
│     "id": "chunk-uuid",                                   │
│     "vector": {                                           │
│       "dense": [0.1, 0.2, ...],      // Primary          │
│       "dense_backup": [0.3, ...],    // If cloud provider│
│       "sparse": {"indices": [...], "values": [...]}      │
│     },                                                    │
│     "payload": { chunk metadata }                         │
│   }                                                       │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
┌──────────────────┐      ┌──────────────────────────┐
│  Search Service  │      │ Reconciliation Service   │
│                  │      │ (Background Task)        │
│  - Query time    │      │                          │
│  - Try primary rerank   │ Scans for points missing │
│  - Fallback to   │      │ one or more vectors      │
│    backup        │      │                          │
│                  │      │ Fills gaps incrementally │
└──────────────────┘      └──────────────────────────┘
```

---

## Core Design Decisions

### **Decision 1: Single Collection with Named Vectors**

**Rationale:** Qdrant supports multiple named vectors per point. This eliminates the need for separate collections and complex reconciliation logic. 

**Implementation:**
```python
# Collection configuration
vectors_config = {
    "dense": VectorParams(
        size=1024,  # Primary embedding dimension
        distance=Distance.COSINE,
    ),
    "dense_backup": VectorParams(
        size=512,  # Backup embedding dimension (jinaai)
        distance=Distance.COSINE,
    ),
    "sparse": SparseVectorParams(
    ),
}
```

**Point Structure:**
```python
# Nominal, needs discussion before finalizing
PointStruct(
    id=chunk.id,
    vector={
        "dense": [0.1, 0.2, ...],           # Primary embedding
        "dense_backup": [0.3, 0.4, ...],    # Backup (conditional)
        "sparse": {"indices": [1, 5, 12], "values": [0.8, 0.6, 0.5]}
    },
    payload=chunk.to_payload(),
)
```

**Benefits:**
- **No cross-collection queries** - single search operation
- **Instant failover** - just change vector name in search
- **No reconciliation complexity** - same points, just different vectors
- **Simpler storage** - one collection to manage
- **Clear semantics** - collection state IS system state

---

### **Decision 2: Single Chunk Granularity**

**Rationale:** Modern backup models (jinaai/jina-embeddings-v2-small-en, jina-reranker-v2-small-en) have 8192 token context windows. By capping chunks at ~7500 tokens, they work with all providers without complexity of managing multiple chunk sizes. Only the primary models will serve as a lower overall limiter.

**Implementation:**
```python
BACKUP_SAFE_LIMIT = 7500

class ChunkGovernor:
    """Determines chunk size with backup-aware limits."""

    @computed_field
    @property
    def chunk_limit(self) -> PositiveInt:
        """Compute safe chunk limit considering backup constraints."""
        # Get primary provider limits
        # Need to verify that ChunkGovernor has `capabilities` property. It definitely has the info in subproperties, unsure on top-level.
        primary_limits = [
            cap.context_window or cap.max_tokens
            for cap in self.capabilities
        ]

        # Use minimum of primary limits and backup safe limit
        return min(min(primary_limits), BACKUP_SAFE_LIMIT) if primary_limits else BACKUP_SAFE_LIMIT
```

**Benefits:**
- **No multi-granularity chunking** - single code path
- **No Span reconciliation** needed - chunks are chunks
- **Simpler indexing** - one chunk set per file
- **Works everywhere** - compatible with all current providers

**Trade-off:** Many modern cloud-based embed/rerank models have caps exceeding 32K tokens or more, but we cap at 7K. This is acceptable given the simplicity gained and because:
  1. Most codebases will primarily use ast-based chunking, which is unlikely to produce chunks this large.
  2. While many models support larger windows, they usually recommend keeping chunks much smaller to speed up inference and throughput.
  3. Larger chunks risk dilluting important context and creating big size disparities between the largest and smallest chunks that can affect model performance.

---

### **Decision 3: Conditional Backup Creation**

**Rationale:** Only create backup vectors when using cloud providers. Local provider failures are permanent (model loading issues), not transient.

**Configuration Detection:**
```python
class BackupConfig(BasedModel):
    """Auto-detected backup configuration."""

    enable_dense_backup: bool
    enable_vector_store_backup: bool

    @classmethod
    def from_settings(cls, settings: ProviderSettings, *, user_disabled: bool = False) -> BackupConfig:
        """Auto-detect backup needs."""
        def _get_setting[T: BaseProviderSettings](provider_settings: tuple[T, ...] | T | None) -> T | None:
            """Get the primary config for a given provider kind's settings."""
            if not provider_settings:
                return None
            return next((setting for setting in provider_settings if not setting.as_backup), None) if isinstance(provider_settings, tuple) else provider_settings
        # user_disabled comes from global settings: [global_settings].failover.disable_failover
        # all ProviderSettings objects (the base class) implement an `is_cloud` and `is_local` method
        vector_store = _get_setting(settings)
        embedding = _get_setting(settings)

        return cls(
            enable_dense_backup=embedding.is_cloud() and not user_disabled,
            enable_vector_store_backup=vector_store.is_cloud() and not user_disabled,
        )
```

**Scenarios:**

| Embedding | Vector Store | Dense Backup | Store Backup |
|-----------|--------------|--------------|--------------|
| Local     | Local        | ❌ No        | ❌ No        |
| Local     | Cloud        | ❌ No        | ✅ Yes       |
| Cloud     | Local        | ✅ Yes       | ❌ No        |
| Cloud     | Cloud        | ✅ Yes       | ✅ Yes       |

---

### **Decision 4: Naive Reconciliation (No State Machine)**

**Rationale:** Instead of tracking state (HEALTHY/DEGRADED/BACKUP_ONLY), just ensure collection state matches configuration. The collection itself is the source of truth.

**Reconciliation Algorithm:**
```python
# helper
@cache
def expected_vectors(metadata: CollectionMetadata | None) -> tuple[VectorParams | SparseVectorParams, ...] | None:
    if metadata:
        return tuple(p for param in (metadata.vector_config, metadata.sparse_config) for p in param.items() if param and p)
    return None


class QdrantBaseProvider(VectorStoreProvider[AsyncQdrantClient], ABC):

    # existing methods

    # in _BaseQdrantVectorStoreProvider
    async def reconcile_vectors(self):
        """Ensure all points have required vectors."""

        expected_vectors = asyncio.to_thread(await self.collection_info())

        missing_vectors = vector for vector in 
        if not missing_backup_ids:
            return  # All good

        # 3. Fill in gaps (batched) -- a update_points operation
        await fill_missing_vectors(
            collection_name=collection_name,
            point_ids=missing_backup_ids,
            vector_name="dense_backup",
        )
```

**Key Insight:** Since stale points are deleted during indexing, we only need to find points **missing the third vector**. We never have orphaned old vectors to clean up.

**Benefits:**
- **Idempotent** - safe to run anytime
- **Self-healing** - automatically fixes gaps
- **Observable** - collection state visible in Qdrant
- **Simple** - no complex state transitions
- **Incremental** - only scans modified points

---

### **Decision 5: Incremental Reconciliation**

**Rationale:** For large collections (100K+ points), full scans are expensive. Track reconciliation timestamp and only process modified points.

**Implementation:**
```python
async def find_points_missing_vector(
    collection_name: str,
    vector_name: str,
    modified_since: datetime,
) -> list[UUID]:
    """Find points missing a specific vector (incremental)."""

    # Scroll through points modified since last check
    missing_ids = []

    scroll_filter = {
        "must": [
            {
                "key": "updated_at",
                "range": {
                    "gte": modified_since.isoformat()
                }
            }
        ]
    }

    async for batch in scroll_collection(
        collection_name=collection_name,
        scroll_filter=scroll_filter,
        with_vectors={"dense_backup"},  # Only fetch this vector
    ):
        for point in batch:
            # Check if vector exists and is non-null
            if vector_name not in point.vector or point.vector[vector_name] is None:
                missing_ids.append(point.id)

    return missing_ids
```

**Benefits:**
- **Performance** - only scans modified points
- **Scalable** - works with millions of points
- **Efficient** - minimal Qdrant load

---

### **Decision 6: Query-Time Reranking Fallback**

**Rationale:** Reranking failover is simple try/catch. No need for complex state management in the critical query path.

**Implementation:**
```python
async def rerank_results(
    query: str,
    results: list[SearchResult],
    primary_reranker: RerankingProvider | None,
    backup_reranker: RerankingProvider,
) -> list[SearchResult]:
    """Rerank with simple fallback."""

    # Try primary if available
    if primary_reranker:
        try:
            return await primary_reranker.rerank(query, results)
        except Exception as e:
            logger.warning("Primary reranker failed: %s", e)
            # Fall through to backup

    # Use backup (always local, always fast)
    return await backup_reranker.rerank(query, results)
```

**Benefits:**
- **Simple** - no state machine
- **Fast** - minimal overhead
- **Reliable** - backup is always local

---

## Current State Analysis

### **✅ Working Components**

1. **Daemon Architecture** (`packages/codeweaver-daemon/`)
   - Background process spawning
   - Health check endpoint
   - Continuous operation

2. **Collection Naming** (`core/utils/general.py:21-35`)
   - Path hashing for uniqueness
   - Backup suffix support
   - Already supports failover naming

3. **Provider Registry** (`providers/dependencies.py`)
   - Backup class factory (`create_backup_class`)
   - Separate registries for primary/backup
   - DI integration ready

4. **Chunking Service** (`engine/services/chunking_service.py`)
   - Single granularity chunking
   - Governor with capability-based limits
   - Ready for 7000 token cap

5. **Sparse Embeddings** (Always Local)
   - SPLADE via fastembed
   - BM-25 fallback
   - No backup needed

### **⚠️ Components Needing Updates**

1. **Qdrant Collection Setup**
   - Currently: Single `dense` vector
   - Needed: Named vectors (`dense`, `dense_backup`, `sparse`)

2. **EmbeddingService**
   - Currently: Single embedding call
   - Needed: Conditional backup vector creation

3. **Point Construction**
   - Currently: `vector=[...]` (single vector)
   - Needed: `vector={"dense": [...], "sparse": {...}}`

4. **Search Logic**
   - Currently: Default vector
   - Needed: Named vector specification

5. **Reconciliation Service**
   - Currently: Doesn't exist
   - Needed: New service for gap filling

---

## Required Changes

### **Phase 1: Named Vectors Foundation** (Week 1)

#### 1.1 Update Qdrant Collection Creation

**File:** `src/codeweaver/providers/vector_stores/qdrant.py`

**Changes:**
```python
async def create_collection(
    self,
    collection_name: str,
    embedding_dim: int,
    backup_embedding_dim: int | None = None,
):
    """Create collection with named vectors."""

    from qdrant_client.models import VectorParams, SparseVectorParams, Distance

    vectors_config = {
        "dense": VectorParams(
            size=embedding_dim,
            distance=Distance.COSINE,
        ),
        "sparse": SparseVectorParams(
            modifier=Modifier.IDF,
        ),
    }

    # Add backup vector if configured
    if backup_embedding_dim:
        vectors_config["dense_backup"] = VectorParams(
            size=backup_embedding_dim,
            distance=Distance.COSINE,
        )

    await self.client.create_collection(
        collection_name=collection_name,
        vectors_config=vectors_config,
    )
```

#### 1.2 Update Point Construction

**File:** `src/codeweaver/providers/vector_stores/qdrant.py`

**Changes:**
```python
def build_point(
    chunk: CodeChunk,
    dense_vector: list[float],
    sparse_vector: SparseEmbedding,
    backup_dense_vector: list[float] | None = None,
) -> PointStruct:
    """Build Qdrant point with named vectors."""

    vectors = {
        "dense": dense_vector,
        "sparse": {
            "indices": sparse_vector.indices,
            "values": sparse_vector.values,
        },
    }

    if backup_dense_vector is not None:
        vectors["dense_backup"] = backup_dense_vector

    return PointStruct(
        id=str(chunk.id),
        vector=vectors,
        payload=chunk.to_payload(),
    )
```

#### 1.3 Update Search to Use Named Vectors

**File:** `src/codeweaver/providers/vector_stores/qdrant.py`

**Changes:**
```python
async def search(
    self,
    collection_name: str,
    query_vector: list[float],
    vector_name: str = "dense",  # NEW: specify which vector
    limit: int = 20,
    **kwargs,
) -> list[SearchResult]:
    """Search using specified named vector."""

    results = await self.client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        using=vector_name,  # Use named vector
        limit=limit,
        **kwargs,
    )

    return [self._to_search_result(r) for r in results]
```

---

### **Phase 2: Conditional Backup Creation** (Week 2)

#### 2.1 Create BackupConfig Auto-Detection

**New File:** `src/codeweaver/config/backup.py`

```python
from codeweaver.core.types import BasedModel
from codeweaver.providers import Provider

CLOUD_PROVIDERS = {
    Provider.VOYAGE,
    Provider.OPENAI,
    Provider.COHERE,
    Provider.MISTRAL,
    Provider.BEDROCK,
    # ... others
}

class BackupConfig(BasedModel):
    """Auto-detected backup configuration."""

    enable_dense_backup: bool
    """Whether to create backup dense embeddings."""

    enable_vector_store_backup: bool
    """Whether to mirror to local vector store."""

    @classmethod
    def from_settings(cls, settings: Settings) -> BackupConfig:
        """Detect backup needs from configuration."""

        embedding_is_cloud = settings.embedding.provider in CLOUD_PROVIDERS
        vector_store_is_cloud = settings.vector_store.provider in CLOUD_PROVIDERS
        user_disabled = settings.failover.disable_backups

        return cls(
            enable_dense_backup=embedding_is_cloud and not user_disabled,
            enable_vector_store_backup=vector_store_is_cloud and not user_disabled,
        )
```

#### 2.2 Update EmbeddingService

**File:** `src/codeweaver/engine/services/embedding_service.py` (new file)

```python
class EmbeddingService:
    """Coordinates embedding with conditional backup."""

    def __init__(
        self,
        primary_embedding: EmbeddingProvider,
        backup_embedding: EmbeddingProvider | None,
        sparse_provider: SparseEmbeddingProvider,
        backup_config: BackupConfig,
    ):
        self.primary = primary_embedding
        self.backup = backup_embedding
        self.sparse = sparse_provider
        self.config = backup_config

    async def embed_batch(
        self,
        chunks: list[CodeChunk]
    ) -> list[EmbeddedChunk]:
        """Create embeddings with all configured vectors."""

        # 1. Sparse (always)
        sparse_vectors = await self.sparse.embed_batch(chunks)

        # 2. Primary dense (with retry fallback)
        dense_vectors = await self._embed_primary_with_retry(chunks)

        # 3. Backup dense (if configured, best effort)
        backup_vectors = None
        if self.config.enable_dense_backup and self.backup:
            backup_vectors = await self._embed_backup_best_effort(chunks)

        # 4. Combine
        return [
            EmbeddedChunk(
                chunk=chunks[i],
                dense_vector=dense_vectors[i],
                backup_vector=backup_vectors[i] if backup_vectors else None,
                sparse_vector=sparse_vectors[i],
            )
            for i in range(len(chunks))
        ]

    async def _embed_primary_with_retry(
        self,
        chunks: list[CodeChunk],
        max_retries: int = 2,
    ) -> list[list[float]]:
        """Try primary with retries, fall back to backup."""

        for attempt in range(max_retries + 1):
            try:
                return await asyncio.wait_for(
                    self.primary.embed_batch(chunks),
                    timeout=30.0,
                )
            except Exception as e:
                if attempt == max_retries:
                    # Last attempt - use backup
                    logger.error(
                        "Primary embedding failed after %d attempts: %s",
                        max_retries + 1, e
                    )

                    if not self.backup:
                        raise EmbeddingError("Primary failed, no backup")

                    logger.info("Using backup embedding")
                    return await self.backup.embed_batch(chunks)

                await asyncio.sleep(2 ** attempt)  # Exponential backoff

    async def _embed_backup_best_effort(
        self,
        chunks: list[CodeChunk]
    ) -> list[list[float]] | None:
        """Create backup embeddings (non-blocking, best effort)."""

        try:
            return await self.backup.embed_batch(chunks)
        except Exception as e:
            logger.warning("Backup embedding creation failed: %s", e)
            # Return None - reconciliation will fill later
            return None
```

#### 2.3 Update IndexingService

**File:** `src/codeweaver/engine/services/indexing_service.py`

**Changes:**
```python
class IndexingService:
    def __init__(
        self,
        chunking_service: ChunkingService,
        embedding_service: EmbeddingService,  # NEW: Use EmbeddingService
        vector_store: VectorStoreProvider,
        # ... other deps
    ):
        self._chunking = chunking_service
        self._embedding = embedding_service
        self._vector_store = vector_store
        # ...

    async def _index_files_batch(self, files):
        """Index files with conditional backup."""

        # 1. Chunk
        chunks = list(self._chunking.chunk_files(files))

        # 2. Embed (handles backup internally)
        embedded_chunks = await self._embedding.embed_batch(chunks)

        # 3. Build points
        points = [
            build_point(
                chunk=ec.chunk,
                dense_vector=ec.dense_vector,
                sparse_vector=ec.sparse_vector,
                backup_dense_vector=ec.backup_vector,
            )
            for ec in embedded_chunks
        ]

        # 4. Upsert
        await self._vector_store.upsert(
            collection_name=self.collection_name,
            points=points,
        )
```

---

### **Phase 3: Reconciliation Service** (Week 3)

#### 3.1 Create Reconciliation Service

**New File:** `src/codeweaver/engine/services/reconciliation_service.py`

```python
class VectorReconciliationService:
    """Ensures collection vectors match configuration."""

    def __init__(
        self,
        vector_store: VectorStoreProvider,
        backup_embedding: EmbeddingProvider,
        backup_config: BackupConfig,
    ):
        self.vector_store = vector_store
        self.backup_embedding = backup_embedding
        self.config = backup_config

        # Track last reconciliation time
        self._last_reconciliation: datetime = datetime.now(UTC)

    async def reconcile_collection(
        self,
        collection_name: str
    ):
        """Reconcile vectors in collection (incremental)."""

        # Only reconcile if backup enabled
        if not self.config.enable_dense_backup:
            return

        # Find points missing backup vector (incremental)
        missing_ids = await self._find_missing_backup_vectors(
            collection_name=collection_name,
            modified_since=self._last_reconciliation,
        )

        if not missing_ids:
            logger.debug("No points missing backup vectors")
            self._last_reconciliation = datetime.now(UTC)
            return

        logger.info(
            "Found %d points missing backup vectors, filling gaps",
            len(missing_ids)
        )

        # Fill gaps in batches
        await self._fill_backup_vectors(
            collection_name=collection_name,
            point_ids=missing_ids,
        )

        # Update timestamp
        self._last_reconciliation = datetime.now(UTC)

    async def _find_missing_backup_vectors(
        self,
        collection_name: str,
        modified_since: datetime,
    ) -> list[UUID]:
        """Find points missing dense_backup vector."""

        missing_ids = []

        # Scroll filter for modified points
        scroll_filter = {
            "must": [
                {
                    "key": "updated_at",
                    "range": {"gte": modified_since.isoformat()}
                }
            ]
        }

        # Scroll through collection
        offset = None
        while True:
            batch, offset = await self.vector_store.scroll(
                collection_name=collection_name,
                scroll_filter=scroll_filter,
                limit=100,
                offset=offset,
                with_vectors={"dense_backup"},  # Only fetch this vector
            )

            for point in batch:
                # Check if vector missing or None
                vec = point.vector.get("dense_backup")
                if vec is None or (isinstance(vec, list) and not vec):
                    missing_ids.append(UUID(point.id))

            if offset is None:
                break

        return missing_ids

    async def _fill_backup_vectors(
        self,
        collection_name: str,
        point_ids: list[UUID],
    ):
        """Fill missing backup vectors (batched)."""

        batch_size = 100

        for i in range(0, len(point_ids), batch_size):
            batch_ids = point_ids[i:i + batch_size]

            # Retrieve points
            points = await self.vector_store.retrieve(
                collection_name=collection_name,
                ids=[str(id) for id in batch_ids],
                with_payload=True,
                with_vectors=False,  # Don't need existing vectors
            )

            # Reconstruct chunks from payloads
            chunks = [
                CodeChunk.from_payload(point.payload)
                for point in points
            ]

            # Generate backup embeddings
            backup_vectors = await self.backup_embedding.embed_batch(chunks)

            # Update points with new vectors
            await self.vector_store.update_vectors(
                collection_name=collection_name,
                points=[
                    UpdateVectorsRequest(
                        id=str(batch_ids[j]),
                        vector={"dense_backup": backup_vectors[j]},
                    )
                    for j in range(len(batch_ids))
                ],
            )

            logger.debug("Filled %d backup vectors", len(batch_ids))
```

#### 3.2 Add Background Reconciliation Task

**File:** `src/codeweaver/server/management.py`

**Changes:**
```python
async def run_reconciliation_loop(
    reconciliation_service: VectorReconciliationService,
    collection_name: str,
    interval_seconds: int,
):
    """Background task for periodic reconciliation."""

    while True:
        try:
            await reconciliation_service.reconcile_collection(collection_name)
        except Exception as e:
            logger.error("Reconciliation failed: %s", e, exc_info=True)

        await asyncio.sleep(interval_seconds)

# In startup:
async def start_daemon_services():
    # ... other services

    # Start reconciliation if backups enabled
    backup_config = container.resolve(BackupConfig)
    if backup_config.enable_dense_backup:
        reconciliation_service = container.resolve(VectorReconciliationService)
        collection_name = generate_collection_name(project_path=project_path)

        asyncio.create_task(
            run_reconciliation_loop(
                reconciliation_service=reconciliation_service,
                collection_name=collection_name,
                interval_seconds=settings.failover.reconciliation_interval_sec,
            )
        )
```

---

### **Phase 4: Vector Store Backup** (Week 4 - Optional)

#### 4.1 Cloud → Local Mirroring

**New File:** `src/codeweaver/engine/services/vector_store_backup.py`

```python
class VectorStoreBackupService:
    """Manages local backup of cloud vector store."""

    def __init__(
        self,
        primary_store: VectorStoreProvider,
        backup_store: VectorStoreProvider | None,
        backup_config: BackupConfig,
    ):
        self.primary = primary_store
        self.backup = backup_store
        self.config = backup_config

    async def upsert_with_backup(
        self,
        collection_name: str,
        points: list[PointStruct],
    ):
        """Upsert to primary, mirror to backup if enabled."""

        # Always write to primary
        await self.primary.upsert(
            collection_name=collection_name,
            points=points,
        )

        # Mirror to backup if enabled
        if self.config.enable_vector_store_backup and self.backup:
            # Background task - don't block
            asyncio.create_task(
                self._mirror_to_backup(collection_name, points)
            )

    async def _mirror_to_backup(
        self,
        collection_name: str,
        points: list[PointStruct],
    ):
        """Background mirroring to local backup."""
        try:
            await self.backup.upsert(
                collection_name=collection_name,
                points=points,
            )
        except Exception as e:
            logger.warning("Backup mirroring failed: %s", e)

    async def search_with_fallback(
        self,
        collection_name: str,
        **search_params,
    ) -> list[SearchResult]:
        """Search with automatic fallback."""

        try:
            return await self.primary.search(
                collection_name=collection_name,
                **search_params,
            )
        except Exception as e:
            logger.warning("Primary search failed: %s", e)

            if not self.backup:
                raise

            logger.info("Using backup vector store")
            return await self.backup.search(
                collection_name=collection_name,
                **search_params,
            )
```

---

## Implementation Phases

### **Phase 1: Named Vectors Foundation** (Week 1)

**Tasks:**
1. Update Qdrant collection creation for named vectors
2. Modify point construction to include all 3 vectors
3. Update search to use named vector parameter
4. Add `updated_at` timestamp to point payloads

**Testing:**
- Verify collection created with correct vector config
- Verify points have named vectors
- Verify search works with vector name specification

**Deliverable:** Single collection with named vectors operational

---

### **Phase 2: Conditional Backup Creation** (Week 2)

**Tasks:**
1. Create `BackupConfig` with auto-detection
2. Implement `EmbeddingService` with conditional backup
3. Update `IndexingService` to use `EmbeddingService`
4. Add retry logic with exponential backoff
5. Wire into DI system

**Testing:**
- Test auto-detection for different provider combinations
- Verify backup vectors only created when needed
- Test primary failure fallback to backup
- Verify best-effort backup creation (non-blocking)

**Deliverable:** Backup vectors created conditionally, failover works during indexing

---

### **Phase 3: Reconciliation Service** (Week 3)

**Tasks:**
1. Create `VectorReconciliationService`
2. Implement incremental scanning with `modified_since` filter
3. Implement gap-filling logic (batched)
4. Add background reconciliation task
5. Wire into daemon startup

**Testing:**
- Test finding missing vectors incrementally
- Test gap-filling in batches
- Test reconciliation loop (background task)
- Performance test with large collections

**Deliverable:** Automatic gap detection and filling operational

---

### **Phase 4: Vector Store Backup** (Week 4 - Optional)

**Tasks:**
1. Create `VectorStoreBackupService`
2. Implement cloud → local mirroring
3. Implement search fallback logic
4. Add sync health monitoring

**Testing:**
- Test mirroring to local backup
- Test fallback on primary failure
- Test sync lag monitoring

**Deliverable:** Full resilience against cloud vector store outages

---

## Testing Strategy

### **Unit Tests**

```python
# tests/engine/services/test_reconciliation_service.py

@pytest.mark.asyncio
async def test_find_missing_backup_vectors():
    """Test incremental scanning for missing vectors."""

    # Create points with missing backup vectors
    points = [
        PointStruct(
            id="1",
            vector={"dense": [...], "sparse": {...}},  # Missing backup
            payload={...}
        ),
        PointStruct(
            id="2",
            vector={"dense": [...], "dense_backup": [...], "sparse": {...}},
            payload={...}
        ),
    ]

    # Mock vector store
    vector_store = Mock()
    vector_store.scroll = AsyncMock(return_value=(points, None))

    # Test
    service = VectorReconciliationService(vector_store, ...)
    missing = await service._find_missing_backup_vectors(
        collection_name="test",
        modified_since=datetime.now(UTC) - timedelta(hours=1),
    )

    assert len(missing) == 1
    assert missing[0] == "1"
```

### **Integration Tests**

```python
# tests/integration/test_failover_e2e.py

@pytest.mark.integration
@pytest.mark.asyncio
async def test_primary_failure_with_reconciliation():
    """Test complete failover workflow."""

    # 1. Index with working primary
    files = [create_test_file()]
    result = await indexing_service.index_files(files)

    # Verify points have dense and sparse, maybe backup

    # 2. Simulate primary failure
    primary_provider.embed_batch = Mock(side_effect=Exception("API down"))

    # 3. Index more files
    more_files = [create_test_file()]
    result = await indexing_service.index_files(more_files)

    # Verify fallback to backup worked

    # 4. Run reconciliation
    await reconciliation_service.reconcile_collection(collection_name)

    # 5. Verify all points now have backup vectors
    points = await vector_store.retrieve(...)
    for point in points:
        assert "dense_backup" in point.vector
        assert point.vector["dense_backup"] is not None
```

### **Performance Tests**

```python
# tests/performance/test_reconciliation_performance.py

@pytest.mark.performance
@pytest.mark.asyncio
async def test_reconciliation_scales():
    """Test reconciliation performance with large collections."""

    # Create 100K points
    points = [create_test_point() for _ in range(100_000)]
    await vector_store.upsert(collection_name, points)

    # Time reconciliation
    start = time.time()
    await reconciliation_service.reconcile_collection(collection_name)
    duration = time.time() - start

    # Should complete in reasonable time
    assert duration < 60  # < 1 minute for 100K points
```

---

## Success Metrics

### **Functional Metrics**
- ✅ Zero feature degradation during provider failures
- ✅ Reconciliation detects all gaps within one cycle
- ✅ Backup vectors created for 100% of points (when enabled)
- ✅ Primary → backup failover latency <1s

### **Performance Metrics**
- ✅ Backup creation overhead <15% (indexing time)
- ✅ Reconciliation completes in <60s for 100K points
- ✅ Storage overhead 2-2.5x (acceptable for reliability)
- ✅ Search latency identical (vector name switch has no overhead)

### **Reliability Metrics**
- ✅ Auto-detection accuracy 100% (correct backup strategy)
- ✅ Gap detection accuracy 100% (no missed vectors)
- ✅ Reconciliation idempotency (safe to run anytime)
- ✅ Zero data loss during failover

---

## Configuration Schema

```python
class FailoverSettings(BasedModel):
    """Simplified failover configuration."""

    disable_backups: Annotated[bool, Field(False)]
    """Explicitly disable all backup functionality."""

    reconciliation_interval_sec: Annotated[int, Field(300, ge=60, le=3600)]
    """Interval between reconciliation runs (default 5 minutes)."""

    reconciliation_batch_size: Annotated[int, Field(100, ge=10, le=1000)]
    """Batch size for filling missing vectors."""

    primary_retry_attempts: Annotated[int, Field(2, ge=0, le=5)]
    """Number of retries before falling back to backup."""

    primary_timeout_sec: Annotated[float, Field(30.0, ge=5.0, le=300.0)]
    """Timeout for primary embedding requests."""
```

---

## Summary

This revised plan achieves **all the goals** of the original plan with:
- **75% less code** (no multi-granularity, no state machine)
- **50% less time** (4 weeks vs 8 weeks)
- **Zero breaking changes** (no provider modifications)
- **Better observability** (collection state is visible)
- **Simpler operations** (just run reconciliation periodically)

**Key Insight:** By using named vectors and naive reconciliation, we eliminate nearly all the complexity while achieving the same reliability goals.
