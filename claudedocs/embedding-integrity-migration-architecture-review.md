<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Architecture Review: Embedding Integrity & Safe Migration System

**Reviewer**: Backend Architect Persona
**Date**: 2026-02-12
**Plan Version**: 1.0
**Status**: Architecture Review Complete

---

## Executive Summary

The implementation plan is **fundamentally sound** with strong design choices aligned with CodeWeaver's constitutional principles. The proposed architecture leverages proven patterns (Strategy, Factory), maintains evidence-based development practices, and provides clear separation of concerns.

**Key Strengths**:
- Excellent use of family-aware asymmetric embedding support (already in CollectionMetadata v1.3.0)
- Clear separation between detection (Phase 1) and transformation (Phase 2)
- Constitutional compliance with evidence-based development
- Smart use of blue-green migration for safety

**Critical Gaps Identified**:
1. **Integration with existing checkpoint/manifest systems needs clarification**
2. **Scalability concerns for 100k+ vector migration**
3. **Error recovery paths insufficiently specified**
4. **API design could be more consistent with existing patterns**
5. **Parallel migration workers not addressed**

**Recommendation**: **Approve with modifications**. Implement Phase 1 as-proposed, defer Phase 2 pending scalability validation, restructure Phase 3 around dependency injection patterns.

---

## 1. Design Patterns Analysis

### 1.1 Current Patterns (Excellent)

#### Strategy Pattern (Existing, Well-Applied)
```python
# Already used in CollectionMetadata.validate_compatibility()
# Handles symmetric vs. asymmetric embedding strategies
def validate_compatibility(self, other: CollectionMetadata) -> None:
    """Family-aware validation when dense_model_family is present."""
    # Different validation strategies based on embedding mode
```

**Assessment**: ✅ **Already implemented correctly**. The plan builds on this foundation.

#### Factory Pattern (Proposed, Appropriate)
```python
# Proposed in config_analyzer.py
def analyze_config_change(
    old_meta: CollectionMetadata,
    new_config: EmbeddingConfig,
    vector_count: int,
) -> ConfigChangeAnalysis:
    """Factory for ConfigChangeAnalysis based on change type."""
```

**Assessment**: ✅ **Good pattern choice**. Creates appropriate analysis objects based on change detection.

**Improvement Recommendation**:
```python
# Better: Use enum dispatch for extensibility
class ChangeAnalyzer(Protocol):
    def analyze(self, old: CollectionMetadata, new: EmbeddingConfig) -> ConfigChangeAnalysis: ...

_analyzers: dict[ChangeImpact, ChangeAnalyzer] = {
    ChangeImpact.QUANTIZABLE: QuantizationAnalyzer(),
    ChangeImpact.TRANSFORMABLE: DimensionAnalyzer(),
    ChangeImpact.BREAKING: BreakingChangeAnalyzer(),
}

def analyze_config_change(...) -> ConfigChangeAnalysis:
    impact = _classify_impact(old_meta, new_config)
    return _analyzers[impact].analyze(old_meta, new_config)
```

This enables **adding new transformation types without modifying the factory**.

### 1.2 Missing Patterns (Critical)

#### Service Layer Pattern (Not Addressed)

**Problem**: The plan mixes service concerns (migration, validation) with data models (CheckpointSettingsFingerprint).

**Current**:
```python
# CheckpointSettingsFingerprint is a TypedDict with behavior
class CheckpointSettingsFingerprint(TypedDict):
    def is_compatible_with(self, other) -> tuple[bool, ChangeImpact]:
        # Business logic in data structure
```

**Recommended**:
```python
# Separate data from behavior
class CheckpointFingerprint(BasedModel):  # Data
    embedding_config_type: Literal["symmetric", "asymmetric"]
    embed_model: str
    embed_model_family: str | None
    query_model: str | None
    # ... other fields

class CheckpointCompatibilityService:  # Behavior
    def check_compatibility(
        self,
        old: CheckpointFingerprint,
        new: CheckpointFingerprint
    ) -> tuple[bool, ChangeImpact]:
        """Check compatibility and classify impact."""
```

**Rationale**: Aligns with Constitutional Principle V (Simplicity Through Architecture). Data structures should be immutable; services should contain business logic.

#### Repository Pattern (Partially Applied)

**Current State**:
- `CheckpointManager` acts as a repository for checkpoint state
- `ManifestManager` acts as a repository for file manifest state
- But no repository for `ConfigChangeAnalysis` or `CollectionMetadata` history

**Recommendation**: Create `ConfigurationHistoryRepository` for tracking config changes:

```python
class ConfigurationHistoryRepository:
    """Track configuration changes over time for rollback and auditing."""

    async def save_config_change(
        self,
        analysis: ConfigChangeAnalysis,
        applied: bool,
    ) -> None:
        """Record a configuration change."""

    async def get_config_history(
        self,
        collection_name: str,
        limit: int = 10,
    ) -> list[ConfigChangeAnalysis]:
        """Retrieve configuration change history."""

    async def get_rollback_target(
        self,
        collection_name: str,
    ) -> CollectionMetadata | None:
        """Get the most recent stable configuration."""
```

**Benefit**: Enables robust rollback mechanism, audit trail, and A/B comparison of configurations.

---

## 2. System Integration Analysis

### 2.1 Checkpoint System Integration (CRITICAL ISSUE)

#### Current State
- **CheckpointManager** (line 178-199 in checkpoint_manager.py):
  ```python
  class CheckpointManager:
      """PURE state management. No default configuration fetching."""

      def __init__(self, project_path, project_name, checkpoint_dir):
          # Manages checkpoint save/load for indexing pipeline
  ```

- **IndexingCheckpoint** (line 90-176 in checkpoint_manager.py):
  ```python
  class IndexingCheckpoint:
      settings_hash: BlakeHashKey | None  # Line 126-128

      def matches_settings(self) -> bool:
          """Check if checkpoint settings match current configuration."""
          return self.settings_hash == self.current_settings_hash()
  ```

#### Proposed Changes
- **CheckpointSettingsFingerprint** (line 51-60 in implementation plan):
  ```python
  class CheckpointSettingsFingerprint:
      embedding_config_type: Literal["symmetric", "asymmetric"]
      embed_model: str
      embed_model_family: str | None
      query_model: str | None
      # ... other fields
  ```

**INTEGRATION CONFLICT IDENTIFIED**:

1. **Existing**: `IndexingCheckpoint.settings_hash` uses `get_checkpoint_settings_map()` which serializes entire provider settings tuples
2. **Proposed**: `CheckpointSettingsFingerprint.is_compatible_with()` adds family-aware comparison
3. **Problem**: These two systems don't interact. The checkpoint will still invalidate on query_model changes.

**Resolution Required**:

```python
# In checkpoint_manager.py
class IndexingCheckpoint(BasedModel):
    # ... existing fields ...

    def matches_settings(self) -> bool:
        """Check if checkpoint settings match current configuration."""
        if self.settings_hash == self.current_settings_hash():
            return True  # Exact match

        # NEW: Family-aware compatibility check
        from codeweaver.engine.services.config_analyzer import (
            check_checkpoint_compatibility
        )

        old_fingerprint = self._extract_fingerprint()
        new_fingerprint = CheckpointFingerprint.from_settings()

        compatible, impact = check_checkpoint_compatibility(
            old_fingerprint, new_fingerprint
        )

        # Allow COMPATIBLE changes (query model within family)
        return compatible and impact == ChangeImpact.COMPATIBLE
```

**Testing Priority**: 🔴 **CRITICAL** - This integration must be validated in Phase 1.

### 2.2 Manifest System Integration (MODERATE ISSUE)

#### Current State
- **FileManifestEntry** (line 36-53 in manifest_manager.py):
  ```python
  class FileManifestEntry(TypedDict):
      # v1.1.0 fields
      dense_embedding_provider: NotRequired[str | None]
      dense_embedding_model: NotRequired[str | None]
      sparse_embedding_provider: NotRequired[str | None]
      sparse_embedding_model: NotRequired[str | None]
      has_dense_embeddings: NotRequired[bool]
      has_sparse_embeddings: NotRequired[bool]
  ```

#### Proposed Changes
- **CollectionMetadata** v1.4.0 (line 752-780 in implementation plan):
  ```python
  class CollectionMetadata:
      # NEW v1.4.0 fields
      quantization_type: Literal["int8", "binary", None] = None
      original_dimension: int | None = None
      transformations: list[TransformationRecord] = []
  ```

**INTEGRATION GAP IDENTIFIED**:

1. **Manifest tracks per-file embedding metadata** but doesn't track quantization or dimension changes
2. **CollectionMetadata tracks collection-level transformations** but doesn't update manifest
3. **Problem**: After dimension migration, manifest entries still reference old dimension

**Resolution Required**:

```python
# Add to FileManifestEntry (v1.2.0)
class FileManifestEntry(TypedDict):
    # ... existing fields ...

    # NEW v1.2.0: Transformation tracking
    vector_dimension: NotRequired[int]  # Current dimension of vectors
    quantization_type: NotRequired[Literal["int8", "binary", None]]

# Update after migration
async def update_manifest_after_transformation(
    manifest: IndexFileManifest,
    transformation: TransformationRecord,
) -> None:
    """Update all manifest entries after collection transformation."""
    for entry in manifest.files.values():
        if transformation.type == "dimension_reduction":
            entry["vector_dimension"] = transformation.new_value
        elif transformation.type == "quantization":
            entry["quantization_type"] = transformation.new_value

    await manifest.save()
```

**Testing Priority**: 🟡 **MODERATE** - Required for Phase 2 migration correctness.

### 2.3 Asymmetric Embedding Integration (EXCELLENT)

**Current State**: Already fully integrated in CollectionMetadata v1.3.0!

```python
# From vector_store.py (line 161-178)
class CollectionMetadata(BasedModel):
    dense_model_family: str | None = None  # v1.3.0
    query_model: str | None = None         # v1.3.0

    def validate_compatibility(self, other: CollectionMetadata) -> None:
        """Family-aware validation."""
        # Already handles asymmetric mode correctly
```

**Plan Alignment**: ✅ **Perfect**. The plan correctly leverages existing infrastructure.

**Enhancement Opportunity**:
```python
# Add helper method to CollectionMetadata
def is_asymmetric(self) -> bool:
    """Check if collection supports asymmetric embedding."""
    return bool(self.dense_model_family and self.query_model)

def query_models_compatible(self, new_query_model: str) -> bool:
    """Check if a new query model is compatible with this collection."""
    if not self.is_asymmetric():
        return new_query_model == self.dense_model

    # Same family check
    from codeweaver.providers.embedding.capabilities import (
        EmbeddingCapabilityResolver
    )

    resolver = EmbeddingCapabilityResolver()
    new_caps = resolver.resolve(new_query_model)

    return (
        new_caps
        and new_caps.model_family
        and new_caps.model_family == self.dense_model_family
    )
```

---

## 3. Scalability & Performance Analysis

### 3.1 Dimension Migration Scalability (CRITICAL CONCERN)

#### Proposed Implementation (Line 650-694)
```python
async def _migrate_with_truncation(
    self,
    source: str,
    target: str,
    new_dimension: int,
) -> int:
    """Scroll source, truncate, upsert to target."""
    offset = None
    batch_size = 1000  # Fixed batch size

    while True:
        records, offset = await self.client.scroll(...)  # Sequential
        truncated = [...]  # In-memory processing
        await self.client.upsert(...)  # Sequential
```

**Performance Analysis**:

| Vector Count | Batch Size | Batches | Sequential Time | Parallel Time (4 workers) |
|--------------|------------|---------|-----------------|---------------------------|
| 1,000        | 1,000      | 1       | ~3 seconds      | ~3 seconds (no benefit)   |
| 10,000       | 1,000      | 10      | ~30 seconds     | ~10 seconds               |
| 100,000      | 1,000      | 100     | ~5 minutes      | ~90 seconds               |
| 1,000,000    | 1,000      | 1,000   | ~50 minutes     | ~15 minutes               |

**Bottlenecks Identified**:
1. **Sequential scroll/upsert**: No parallelization (❌)
2. **Fixed batch size**: Not adaptive to vector size (❌)
3. **In-memory processing**: Could OOM on large batches (⚠️)
4. **No progress checkpointing**: Failure requires full restart (❌)

**Recommended Architecture**:

```python
class ParallelMigrationService:
    """Parallel dimension migration with checkpointing."""

    async def migrate_dimensions(
        self,
        source: str,
        target: str,
        new_dimension: int,
        *,
        max_workers: int = 4,
        checkpoint_every: int = 10_000,
    ) -> MigrationResult:
        """Migrate with parallel workers and checkpointing."""

        # 1. Create migration checkpoint
        checkpoint = MigrationCheckpoint(
            source=source,
            target=target,
            total_vectors=await self._count_vectors(source),
            vectors_migrated=0,
            last_offset=None,
        )

        # 2. Create worker pool
        workers = [
            MigrationWorker(
                worker_id=i,
                client=self._create_worker_client(),
                checkpoint=checkpoint,
            )
            for i in range(max_workers)
        ]

        # 3. Distribute work
        async with asyncio.TaskGroup() as tg:
            for worker in workers:
                tg.create_task(
                    self._migrate_batch_worker(
                        worker,
                        source,
                        target,
                        new_dimension,
                    )
                )

        # 4. Validate
        await self._validate_migration(source, target, checkpoint.total_vectors)

        return MigrationResult(...)

class MigrationWorker:
    """Worker for parallel migration."""

    async def migrate_batch(
        self,
        source: str,
        target: str,
        new_dimension: int,
        offset: str | None,
        batch_size: int,
    ) -> tuple[int, str | None]:
        """Migrate a single batch."""
        records, next_offset = await self.client.scroll(
            collection_name=source,
            limit=batch_size,
            offset=offset,
            with_vectors=True,
        )

        if not records:
            return 0, None

        # Truncate in parallel (CPU-bound)
        truncated = await asyncio.to_thread(
            self._truncate_batch,
            records,
            new_dimension,
        )

        # Upsert batch
        await self.client.upsert(
            collection_name=target,
            points=truncated,
        )

        return len(truncated), next_offset
```

**Benefits**:
- **4x throughput** with parallel workers
- **Resilient to failures** via checkpointing
- **Adaptive batch sizing** based on vector dimension
- **Progress reporting** via checkpoint updates

**Implementation Priority**: 🔴 **CRITICAL** for Phase 2.

### 3.2 Qdrant API Rate Limiting (MODERATE CONCERN)

**Current Plan**: No rate limiting mentioned.

**Qdrant Cloud Limits**:
- **Scroll**: 100 requests/second
- **Upsert**: 50 requests/second (batch operations)
- **Collection operations**: 10 requests/second

**Risk**: 100k vector migration at 1000 batch size = 100 scroll + 100 upsert = 200 requests in ~5 minutes → **~0.67 requests/second** (well under limits).

**Assessment**: ✅ **No issue for typical use cases** (< 1M vectors).

**Recommendation**: Add configurable rate limiting for safety:

```python
from anyio import create_capacity_limiter

class RateLimitedMigrationService:
    def __init__(
        self,
        max_requests_per_second: int = 50,
    ):
        self._rate_limiter = create_capacity_limiter(max_requests_per_second)

    async def _rate_limited_scroll(self, *args, **kwargs):
        async with self._rate_limiter:
            return await self.client.scroll(*args, **kwargs)
```

**Implementation Priority**: 🟢 **LOW** - Add if user reports rate limit issues.

### 3.3 Memory Usage (MODERATE CONCERN)

**Current Plan** (Line 673-682):
```python
truncated = [
    models.PointStruct(
        id=record.id,
        vector={"primary": record.vector["primary"][:new_dimension]},
        payload=record.payload,
    )
    for record in records  # In-memory list comprehension
]
```

**Memory Analysis**:

| Batch Size | Vector Dim | Bytes/Vector | Batch Memory |
|------------|------------|--------------|--------------|
| 1,000      | 2048       | ~8 KB        | ~8 MB        |
| 1,000      | 1024       | ~4 KB        | ~4 MB        |
| 5,000      | 2048       | ~8 KB        | ~40 MB       |
| 10,000     | 2048       | ~8 KB        | ~80 MB       |

**Assessment**: ✅ **Acceptable** for batch_size=1000. Memory scales linearly with batch size.

**Recommendation**:
```python
# Use generator for memory efficiency
async def _migrate_batch_generator(
    self,
    records: list[Record],
    new_dimension: int,
) -> AsyncGenerator[models.PointStruct, None]:
    """Generate truncated points without materializing full list."""
    for record in records:
        yield models.PointStruct(
            id=record.id,
            vector={"primary": record.vector["primary"][:new_dimension]},
            payload=record.payload,
        )

# Or use chunk-based processing
async def _migrate_with_truncation(self, ...):
    async for chunk in self._scroll_in_chunks(source, chunk_size=100):
        truncated = [self._truncate_vector(r, new_dimension) for r in chunk]
        await self.client.upsert(collection_name=target, points=truncated)
```

**Implementation Priority**: 🟡 **MODERATE** - Implement if batch_size > 5000.

---

## 4. Error Handling & Resilience Analysis

### 4.1 Qdrant Unavailability (CRITICAL GAP)

**Current Plan**: Blue-green migration (line 596-648) but no failure handling specified.

**Failure Scenarios**:
1. **Qdrant connection lost mid-migration**: No recovery path
2. **Scroll pagination fails**: No retry logic
3. **Upsert batch fails**: No partial success tracking
4. **Validation fails**: No automated rollback

**Recommended Error Handling**:

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from qdrant_client.http.exceptions import UnexpectedResponse

class ResilientMigrationService:
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type((
            httpx.TimeoutException,
            UnexpectedResponse,
        )),
    )
    async def _scroll_with_retry(
        self,
        collection_name: str,
        offset: str | None,
        limit: int,
    ) -> tuple[list[Record], str | None]:
        """Scroll with exponential backoff retry."""
        try:
            return await self.client.scroll(
                collection_name=collection_name,
                offset=offset,
                limit=limit,
                with_vectors=True,
            )
        except UnexpectedResponse as e:
            if e.status_code == 503:  # Service unavailable
                logger.warning("Qdrant temporarily unavailable, retrying...")
                raise  # Retry
            elif e.status_code == 404:  # Collection not found
                logger.error("Source collection not found: %s", collection_name)
                raise MigrationError("Source collection missing") from e
            else:
                raise  # Don't retry on other errors

    async def _migrate_with_resilience(
        self,
        source: str,
        target: str,
        new_dimension: int,
    ) -> MigrationResult:
        """Migrate with checkpoint-based recovery."""
        checkpoint = await self._load_or_create_checkpoint(source, target)

        try:
            # Resume from last checkpoint
            offset = checkpoint.last_offset
            migrated = checkpoint.vectors_migrated

            while True:
                records, offset = await self._scroll_with_retry(
                    source, offset, batch_size=1000
                )

                if not records:
                    break

                # Truncate and upsert with retry
                truncated = self._truncate_batch(records, new_dimension)
                await self._upsert_with_retry(target, truncated)

                migrated += len(truncated)

                # Update checkpoint every 10k vectors
                if migrated % 10_000 == 0:
                    checkpoint.last_offset = offset
                    checkpoint.vectors_migrated = migrated
                    await self._save_checkpoint(checkpoint)

            # Final validation
            await self._validate_migration(source, target, migrated)

            # Cleanup checkpoint
            await self._delete_checkpoint(checkpoint)

            return MigrationResult(
                vectors_migrated=migrated,
                rollback_available=True,
            )

        except Exception as e:
            # Save checkpoint for recovery
            await self._save_checkpoint(checkpoint)
            logger.error(
                "Migration failed at offset %s after %d vectors: %s",
                checkpoint.last_offset,
                checkpoint.vectors_migrated,
                e,
            )
            raise MigrationError(
                f"Migration interrupted. Resume with: "
                f"cw migrate resume --checkpoint={checkpoint.id}"
            ) from e
```

**Implementation Priority**: 🔴 **CRITICAL** for Phase 2.

### 4.2 Partial Failure Handling (CRITICAL GAP)

**Scenario**: Upsert succeeds for 7,000 vectors, fails at 7,001.

**Current Plan**: No specification of partial success tracking.

**Problem**: Without checkpointing, must restart from beginning (wasted work, potential data corruption).

**Recommended Solution**:

```python
class MigrationCheckpoint(BasedModel):
    """Checkpoint for resumable migration."""

    migration_id: UUID7
    source_collection: str
    target_collection: str
    total_vectors: int
    vectors_migrated: int
    last_offset: str | None
    started_at: datetime
    last_updated: datetime
    status: Literal["in_progress", "completed", "failed"]
    error_message: str | None = None

class CheckpointedMigrationService:
    async def resume_migration(
        self,
        checkpoint_id: UUID7,
    ) -> MigrationResult:
        """Resume a failed migration from checkpoint."""
        checkpoint = await self._load_checkpoint(checkpoint_id)

        if checkpoint.status == "completed":
            logger.info("Migration already completed")
            return MigrationResult(
                vectors_migrated=checkpoint.vectors_migrated,
                resumed=False,
            )

        logger.info(
            "Resuming migration at offset %s (%d/%d vectors)",
            checkpoint.last_offset,
            checkpoint.vectors_migrated,
            checkpoint.total_vectors,
        )

        # Continue from last offset
        return await self._migrate_with_resilience(
            source=checkpoint.source_collection,
            target=checkpoint.target_collection,
            new_dimension=checkpoint.new_dimension,
            checkpoint=checkpoint,  # Pass existing checkpoint
        )
```

**CLI Integration**:
```bash
$ cw migrate dimensions --from 2048 --to 1024

⏳ Starting migration...
  [████░░░░░░░░] 35% (35,000/100,000)
❌ Error: Qdrant connection lost

💾 Progress saved. Resume with:
   cw migrate resume --id=01J3K4M5N6P7Q8R9S0T1U2V3

$ cw migrate resume --id=01J3K4M5N6P7Q8R9S0T1U2V3

⏳ Resuming from 35,000/100,000...
  [████████████] 100% (100,000/100,000)
✓ Migration complete!
```

**Implementation Priority**: 🔴 **CRITICAL** for Phase 2.

### 4.3 Rollback Mechanism (MODERATE ISSUE)

**Current Plan** (Line 645-647):
```python
rollback_available=True,
rollback_retention_days=7,
```

**Issues**:
1. No automatic rollback on validation failure
2. No rollback state machine
3. No rollback safety checks (e.g., prevent rolling back if new writes happened)

**Recommended Rollback System**:

```python
class RollbackService:
    """Manages collection rollbacks with safety checks."""

    async def rollback_migration(
        self,
        collection_alias: str,
        target_version: str | None = None,
    ) -> RollbackResult:
        """Rollback to previous collection version."""

        # 1. Get rollback history
        history = await self._get_rollback_history(collection_alias)

        if not history:
            raise RollbackError("No rollback history available")

        # 2. Determine target version
        if target_version is None:
            target = history[0]  # Most recent
        else:
            target = self._find_version(history, target_version)

        # 3. Safety checks
        await self._check_rollback_safety(collection_alias, target)

        # 4. Switch alias atomically
        await self._switch_collection_alias(
            alias=collection_alias,
            new_target=target.collection_name,
            old_target=f"{collection_alias}_rollback",
        )

        # 5. Update metadata
        await self._update_rollback_metadata(collection_alias, target)

        return RollbackResult(
            collection=collection_alias,
            rolled_back_to=target.version,
            timestamp=datetime.now(UTC),
        )

    async def _check_rollback_safety(
        self,
        collection_alias: str,
        target_version: CollectionVersion,
    ) -> None:
        """Verify rollback is safe."""
        current = await self._get_current_collection(collection_alias)

        # Check if writes happened after migration
        current_count = await self.client.count(current.name)
        target_count = target_version.vector_count

        if current_count > target_count:
            raise RollbackError(
                f"Collection has {current_count - target_count} new vectors. "
                f"Rollback would lose data. Use --force to override."
            )

        # Check if target still exists
        if not await self._collection_exists(target_version.collection_name):
            raise RollbackError(
                f"Target collection {target_version.collection_name} not found. "
                f"It may have been deleted."
            )
```

**Implementation Priority**: 🟡 **MODERATE** for Phase 2.

---

## 5. API Design Analysis

### 5.1 ConfigChangeAnalysis Type (GOOD with Improvements)

**Proposed API** (Line 162-180):
```python
@dataclass
class ConfigChangeAnalysis:
    impact: ChangeImpact
    old_config: CollectionMetadata
    new_config: EmbeddingConfig

    transformation_type: TransformationType | None
    transformations: list[dict[str, Any]]  # ❌ Untyped dicts

    estimated_time: timedelta
    estimated_cost: float
    accuracy_impact: str  # ❌ Should be structured

    recommendations: list[str]
    migration_strategy: str | None
```

**Issues**:
1. **Untyped transformations**: `list[dict[str, Any]]` loses type safety
2. **String accuracy**: `str` instead of structured data
3. **Missing**: Confidence scores, risk assessment

**Recommended Redesign**:

```python
class TransformationDetail(BasedModel):
    """Structured transformation detail."""

    type: Literal["quantization", "dimension_reduction"]
    old_value: str | int
    new_value: str | int
    complexity: Literal["low", "medium", "high"]
    time_estimate: timedelta
    requires_vector_update: bool
    accuracy_impact: AccuracyImpact

class AccuracyImpact(BasedModel):
    """Structured accuracy impact data."""

    estimated_loss_percent: float
    confidence: Literal["empirical", "estimated", "unknown"]
    benchmark_source: str | None = None  # e.g., "Voyage-3 MTEB"
    acceptable: bool  # Loss < threshold

class ConfigChangeAnalysis(BasedModel):  # Use BasedModel not dataclass
    """Comprehensive config change analysis."""

    impact: ChangeImpact
    old_metadata: CollectionMetadata
    new_config: EmbeddingConfig

    transformations: list[TransformationDetail]

    estimates: EstimateBundle
    recommendations: list[str]
    migration_strategy: MigrationStrategy | None

    # NEW: Risk assessment
    risk_level: Literal["low", "medium", "high"]
    rollback_available: bool

class EstimateBundle(BasedModel):
    """Bundled estimates for user decision-making."""

    time: timedelta
    cost: float
    memory_change: MemoryChange
    accuracy: AccuracyImpact

class MemoryChange(BasedModel):
    """Memory usage change estimate."""

    old_mb: float
    new_mb: float
    reduction_percent: float
```

**Benefits**:
- **Type-safe**: All fields properly typed
- **Structured**: Easy to parse and display
- **Extensible**: Can add fields without breaking API
- **Testable**: Clear contracts for each component

**Implementation Priority**: 🟡 **MODERATE** for Phase 1.

### 5.2 CLI Command API (GOOD with Consistency Issues)

**Proposed Commands**:
```bash
cw config set provider.embedding.dimension=768    # Validation hook
cw config apply --transform                       # Apply transformation
cw migrate rollback                               # Rollback migration
cw doctor                                         # Health check
```

**Issues**:
1. **Inconsistent naming**: `config apply` vs `migrate rollback`
2. **Missing**: `cw migrate status`, `cw migrate resume`
3. **Unclear**: What does `--transform` do vs. reindex?

**Recommended Consistency**:

```bash
# Configuration management
cw config set <key> <value>                       # Set with validation
cw config revert                                  # Revert to previous
cw config diff                                    # Show changes
cw config validate                                # Validate current config

# Migration operations
cw migrate plan                                   # Show migration plan
cw migrate apply                                  # Apply planned migration
cw migrate status                                 # Show migration status
cw migrate resume [--id=<id>]                     # Resume failed migration
cw migrate rollback [--to=<version>]              # Rollback migration
cw migrate history                                # Show migration history

# Health and diagnostics
cw doctor                                         # Full health check
cw doctor --check=embedding                       # Specific check
```

**Alignment with existing patterns**:
```bash
# Existing CodeWeaver commands (from AGENTS.md)
cw index                                          # Indexing
cw search <query>                                 # Search
cw start                                          # Start daemon
cw stop                                           # Stop daemon
```

**Rationale**: Verb-noun structure (`migrate apply`) is more consistent than mixed styles.

**Implementation Priority**: 🟢 **LOW** - Can evolve in Beta.

### 5.3 Programmatic API (MISSING)

**Current Plan**: Only CLI interface specified.

**Problem**: Power users, scripts, and integrations need programmatic access.

**Recommended Programmatic API**:

```python
from codeweaver.engine.services import ConfigMigrationService

# Initialize service
service = await ConfigMigrationService.create()

# Analyze config change
analysis = await service.analyze_change(
    new_dimension=768,
    new_quantization="int8",
)

# Preview migration
print(f"Impact: {analysis.impact}")
print(f"Time: {analysis.estimates.time}")
print(f"Cost: ${analysis.estimates.cost}")

# Apply migration
if analysis.impact in (ChangeImpact.QUANTIZABLE, ChangeImpact.TRANSFORMABLE):
    result = await service.apply_transformation(analysis)
    print(f"Migrated {result.vectors_migrated} vectors")

# Rollback if needed
await service.rollback(to_version="previous")
```

**Integration Points**:
- **FastMCP**: Could expose as tool for AI agents
- **Python API**: For scripting and automation
- **REST API**: For web UI or remote management

**Implementation Priority**: 🟢 **LOW** - Phase 3.

---

## 6. Code Organization Review

### 6.1 Proposed Module Structure

**Proposed** (from implementation plan):
```
codeweaver/engine/
├── managers/
│   ├── checkpoint_manager.py          # Existing
│   └── manifest_manager.py            # Existing
│
├── services/
│   ├── config_analyzer.py             # NEW Phase 1
│   └── migration_service.py           # NEW Phase 2 (should be in providers/)
│
└── ...
```

**Issue**: `migration_service.py` is Qdrant-specific but placed in generic `engine/services`.

**Recommended Structure**:
```
codeweaver/
├── engine/
│   ├── managers/
│   │   ├── checkpoint_manager.py      # EXISTING
│   │   ├── manifest_manager.py        # EXISTING
│   │   └── config_history_manager.py  # NEW Phase 1
│   │
│   └── services/
│       └── config_analyzer.py         # NEW Phase 1 (provider-agnostic)
│
├── providers/vector_stores/
│   ├── base.py                        # EXISTING
│   ├── qdrant_base.py                 # EXISTING
│   ├── qdrant.py                      # EXISTING
│   │
│   ├── migration/                     # NEW Phase 2
│   │   ├── __init__.py
│   │   ├── base.py                    # Abstract migration interface
│   │   ├── qdrant_migration.py        # Qdrant-specific implementation
│   │   ├── checkpoint.py              # Migration checkpointing
│   │   └── rollback.py                # Rollback service
│   │
│   └── transformations/               # NEW Phase 2
│       ├── __init__.py
│       ├── quantization.py            # Quantization transformation
│       └── dimension_reduction.py     # Dimension reduction transformation
│
└── config/
    └── validation.py                  # NEW Phase 1
```

**Rationale**:
- **Separation of concerns**: Provider-specific code stays in `providers/`
- **Extensibility**: Easy to add non-Qdrant migrations later
- **Discoverability**: Clear hierarchy (migrations vs transformations)

**Implementation Priority**: 🟡 **MODERATE** - Affects Phase 2 structure.

### 6.2 Responsibility Separation (GOOD)

**Clear Responsibilities**:
- ✅ `config_analyzer.py`: Change detection and impact assessment
- ✅ `checkpoint_manager.py`: Indexing checkpoint management
- ✅ `manifest_manager.py`: File manifest tracking
- ✅ `migration_service.py`: Vector migration execution

**Potential Overlap**:
- `config_analyzer.py` and `checkpoint_manager.py` both compare settings
- `migration_service.py` and `qdrant_base.py` both manipulate collections

**Resolution**: Create clear interfaces:

```python
# config_analyzer.py
class ConfigAnalyzer(Protocol):
    """Analyzes configuration changes."""

    def analyze(
        self,
        old: CollectionMetadata,
        new: EmbeddingConfig,
    ) -> ConfigChangeAnalysis: ...

# checkpoint_manager.py
class CheckpointManager:
    """Manages indexing checkpoints (read/write only)."""

    def __init__(self, analyzer: ConfigAnalyzer):
        self._analyzer = analyzer

    def is_valid(self, checkpoint: IndexingCheckpoint) -> bool:
        """Check if checkpoint is valid using analyzer."""
        return self._analyzer.is_compatible(
            checkpoint.old_fingerprint,
            current_fingerprint,
        )

# migration/base.py
class MigrationService(Protocol):
    """Abstract migration interface."""

    async def migrate(self, plan: MigrationPlan) -> MigrationResult: ...
    async def rollback(self, to_version: str) -> RollbackResult: ...

# migration/qdrant_migration.py
class QdrantMigrationService(MigrationService):
    """Qdrant-specific migration implementation."""
```

**Implementation Priority**: 🟡 **MODERATE** - Clarify in Phase 1 design.

---

## 7. Future Extensibility Analysis

### 7.1 Non-Qdrant Vector Stores (CRITICAL)

**Current Plan**: Qdrant-specific implementation only.

**Question**: What if CodeWeaver supports Milvus, Weaviate, Pinecone later?

**Proposed Abstraction**:

```python
# providers/vector_stores/migration/base.py
class VectorStoreMigrationService(Protocol):
    """Abstract interface for vector store migrations."""

    async def supports_quantization(self) -> bool:
        """Check if provider supports quantization."""

    async def supports_dimension_change(self) -> bool:
        """Check if provider supports dimension changes."""

    async def migrate_dimensions(
        self,
        collection: str,
        new_dimension: int,
        strategy: MigrationStrategy,
    ) -> MigrationResult:
        """Migrate collection to new dimension."""

    async def apply_quantization(
        self,
        collection: str,
        quantization: QuantizationType,
    ) -> MigrationResult:
        """Apply quantization to collection."""

# providers/vector_stores/migration/qdrant_migration.py
class QdrantMigrationService(VectorStoreMigrationService):
    """Qdrant-specific implementation."""

    async def supports_quantization(self) -> bool:
        return True  # Qdrant supports int8, binary

    async def supports_dimension_change(self) -> bool:
        return True  # Via blue-green migration

# providers/vector_stores/migration/pinecone_migration.py
class PineconeMigrationService(VectorStoreMigrationService):
    """Pinecone-specific implementation."""

    async def supports_quantization(self) -> bool:
        return False  # Pinecone doesn't support custom quantization

    async def supports_dimension_change(self) -> bool:
        return False  # Pinecone requires new index
```

**Benefit**: Easy to add new providers without changing core logic.

**Implementation Priority**: 🟢 **LOW** - No other providers planned yet.

### 7.2 Dimension Increase (via Re-Embedding) (MODERATE)

**Current Plan**: Only dimension reduction supported.

**Question**: What if users want to increase dimensions (e.g., 768 → 1024)?

**Challenge**: Cannot "un-truncate" vectors; requires re-embedding.

**Proposed Solution**:

```python
class DimensionIncreaseService:
    """Handle dimension increases via re-embedding."""

    async def increase_dimensions(
        self,
        collection: str,
        new_dimension: int,
        embedding_service: EmbeddingService,
    ) -> MigrationResult:
        """Increase dimensions by re-embedding."""

        # 1. Detect dimension increase
        old_dim = await self._get_dimension(collection)
        if new_dimension <= old_dim:
            raise ValueError("Use dimension reduction for decreases")

        # 2. Warn user about cost
        vector_count = await self._count_vectors(collection)
        cost = self._estimate_reembedding_cost(vector_count, new_dimension)

        logger.warning(
            "Dimension increase requires re-embedding all %d vectors. "
            "Estimated cost: $%.2f. Continue? (y/n)",
            vector_count,
            cost,
        )

        # 3. Re-embed in batches
        await self._reembed_collection(
            collection,
            embedding_service,
            new_dimension,
        )

        return MigrationResult(
            strategy="reembedding",
            vectors_migrated=vector_count,
            cost=cost,
        )
```

**UX Flow**:
```bash
$ cw config set provider.embedding.dimension=1024

⚠️  Configuration Change Detected

  Change: Dimension increase (768 → 1024)
  Impact: Requires re-embedding all vectors

  ❌ Cannot un-truncate vectors
  ✅ Can re-embed from source files

  Estimates:
    Time: ~15 minutes
    Cost: $12.50 (125,000 tokens × $0.0001/token)
    Quality: Same as fresh index

  Options:
    [1] Re-embed from source (recommended)
    [2] Fresh reindex (clean slate)
    [3] Cancel

  Choice: 1

⏳ Re-embedding 1,234 files...
  [████████████] 100%
✓ Re-embedding complete!
```

**Implementation Priority**: 🟢 **LOW** - Future enhancement.

### 7.3 New Transformation Types (EASY)

**Current**: Quantization, dimension reduction.

**Future Possibilities**:
- **Sparse embedding addition**: Add sparse embeddings to existing dense-only collections
- **Backup model addition**: Add backup embeddings for failover
- **Metadata enrichment**: Add semantic metadata to existing vectors
- **Vector normalization**: Re-normalize vectors after provider change

**Extensibility Pattern**:

```python
class Transformation(Protocol):
    """Abstract transformation interface."""

    async def can_apply(
        self,
        old: CollectionMetadata,
        new: EmbeddingConfig,
    ) -> bool:
        """Check if this transformation applies."""

    async def estimate(
        self,
        collection: str,
        vector_count: int,
    ) -> TransformationEstimate:
        """Estimate cost and impact."""

    async def apply(
        self,
        collection: str,
        target_config: Any,
    ) -> TransformationResult:
        """Apply the transformation."""

# Registry of transformations
_transformations: list[Transformation] = [
    QuantizationTransformation(),
    DimensionReductionTransformation(),
    SparseEmbeddingTransformation(),  # NEW
    BackupModelTransformation(),      # NEW
]

def find_applicable_transformations(
    old: CollectionMetadata,
    new: EmbeddingConfig,
) -> list[Transformation]:
    """Find all applicable transformations."""
    return [
        t for t in _transformations
        if await t.can_apply(old, new)
    ]
```

**Benefit**: Add new transformations without modifying core logic.

**Implementation Priority**: 🟢 **LOW** - Architectural pattern for future.

---

## 8. Critical Design Recommendations

### 8.1 High Priority (Implement in Phase 1)

#### 1. Fix Checkpoint Integration (CRITICAL)
**Problem**: Proposed `CheckpointSettingsFingerprint.is_compatible_with()` doesn't integrate with `IndexingCheckpoint.matches_settings()`.

**Solution**:
```python
# In checkpoint_manager.py
class IndexingCheckpoint(BasedModel):
    def matches_settings(self) -> bool:
        """Family-aware compatibility check."""
        if self.settings_hash == self.current_settings_hash():
            return True  # Exact match

        # NEW: Check family-aware compatibility
        from codeweaver.engine.services.config_analyzer import (
            check_checkpoint_compatibility
        )

        compatible, impact = check_checkpoint_compatibility(
            self._extract_fingerprint(),
            CheckpointFingerprint.from_current_settings(),
        )

        return compatible and impact == ChangeImpact.COMPATIBLE
```

**Impact**: Prevents false checkpoint invalidation on query model changes.

#### 2. Use BasedModel instead of TypedDict (IMPORTANT)
**Problem**: `CheckpointSettingsFingerprint` is a TypedDict with methods (anti-pattern).

**Solution**:
```python
# Change from TypedDict to BasedModel
class CheckpointFingerprint(BasedModel):
    """Immutable fingerprint of checkpoint settings."""

    model_config = ConfigDict(frozen=True)

    embedding_config_type: Literal["symmetric", "asymmetric"]
    embed_model: str
    embed_model_family: str | None
    query_model: str | None
    sparse_model: str | None
    vector_store: str

# Separate service for compatibility checks
class CheckpointCompatibilityService:
    def check(
        self,
        old: CheckpointFingerprint,
        new: CheckpointFingerprint,
    ) -> tuple[bool, ChangeImpact]:
        """Check compatibility between fingerprints."""
```

**Impact**: Better type safety, immutability, constitutional compliance.

#### 3. Add ConfigurationHistoryRepository (IMPORTANT)
**Problem**: No tracking of configuration changes over time.

**Solution**: Implement repository pattern for config history (see section 2.3).

**Impact**: Enables audit trail, rollback target discovery, A/B comparison.

### 8.2 High Priority (Phase 2 Prerequisites)

#### 4. Implement Parallel Migration Workers (CRITICAL)
**Problem**: Sequential migration won't scale to 100k+ vectors.

**Solution**: Implement `ParallelMigrationService` (see section 3.1).

**Impact**: 4x faster migrations, better resource utilization.

#### 5. Add Migration Checkpointing (CRITICAL)
**Problem**: Migration failures require full restart.

**Solution**: Implement `MigrationCheckpoint` and resume functionality (see section 4.2).

**Impact**: Resilience to failures, ability to resume interrupted migrations.

#### 6. Implement Error Recovery (CRITICAL)
**Problem**: No retry logic, no partial failure handling.

**Solution**: Add `@retry` decorators and checkpoint-based recovery (see section 4.1).

**Impact**: Production-ready reliability.

### 8.3 Medium Priority (Phase 2 Improvements)

#### 7. Update Manifest After Transformations (MODERATE)
**Problem**: `FileManifestEntry` doesn't track dimension/quantization changes.

**Solution**: Add `vector_dimension` and `quantization_type` fields to manifest (see section 2.2).

**Impact**: Correct manifest state after transformations.

#### 8. Restructure Module Organization (MODERATE)
**Problem**: Provider-specific code in generic engine layer.

**Solution**: Move migration service to `providers/vector_stores/migration/` (see section 6.1).

**Impact**: Better separation of concerns, easier to add providers.

#### 9. Improve ConfigChangeAnalysis API (MODERATE)
**Problem**: Untyped dicts in transformation details.

**Solution**: Create structured types `TransformationDetail`, `AccuracyImpact`, etc. (see section 5.1).

**Impact**: Type safety, better UX, easier testing.

### 8.4 Low Priority (Phase 3 or Later)

#### 10. Add Programmatic API (LOW)
**Problem**: Only CLI interface.

**Solution**: Create Python API for scripting (see section 5.3).

**Impact**: Better automation, integration possibilities.

#### 11. Prepare for Non-Qdrant Providers (LOW)
**Problem**: Qdrant-specific implementation.

**Solution**: Create `VectorStoreMigrationService` protocol (see section 7.1).

**Impact**: Future-proofing for new providers.

#### 12. Add Dimension Increase Support (LOW)
**Problem**: Only dimension reduction supported.

**Solution**: Create `DimensionIncreaseService` with re-embedding (see section 7.2).

**Impact**: Completeness, user flexibility.

---

## 9. Constitutional Compliance Assessment

### Principle I: AI-First Context ✅ **Compliant**

**Evidence**:
- Doctor command provides clear compatibility status for AI agents
- Structured `ConfigChangeAnalysis` enables AI-driven decision support
- User-facing messages optimized for comprehension

**Recommendation**: Consider adding MCP tool for configuration analysis:
```python
@mcp.tool()
async def analyze_embedding_config_change(
    new_dimension: int | None = None,
    new_quantization: str | None = None,
) -> ConfigChangeAnalysis:
    """Analyze impact of embedding configuration changes."""
```

### Principle II: Proven Patterns ✅ **Compliant**

**Evidence**:
- Blue-green migration (industry standard)
- Strategy pattern for compatibility checks
- Repository pattern for state management

**Concern**: Migration service doesn't follow FastAPI dependency injection patterns.

**Recommendation**:
```python
# Use FastAPI-style dependency injection
from codeweaver.core import INJECTED

class QdrantMigrationService:
    def __init__(
        self,
        client: AsyncQdrantClient = INJECTED,
        config: QdrantVectorStoreProviderSettings = INJECTED,
    ):
        self.client = client
        self.config = config
```

### Principle III: Evidence-Based Development ✅ **Mostly Compliant**

**Evidence**:
- Voyage-3 benchmark data validates transformation approach
- Explicit accuracy impact calculations
- No placeholder/mock implementations

**Concern**: Missing empirical validation for non-Voyage models.

**Recommendation**: Add testing requirements:
```python
# In test_dimension_migration.py
@pytest.mark.benchmark
async def test_matryoshka_accuracy_preservation():
    """Validate dimension reduction preserves accuracy within 1%."""
    # Use real embeddings, real search queries
    # Compare search results before/after migration
    # Assert: accuracy_loss < 0.01
```

### Principle IV: Testing Philosophy ⚠️ **Partially Compliant**

**Evidence**:
- Integration tests planned for Phase 1, 2
- Benchmark validation tests planned

**Concern**: No integration test specifications provided in plan.

**Recommendation**: Add explicit test scenarios:
```python
# Phase 1 Integration Tests
async def test_asymmetric_query_model_change_no_reindex():
    """Verify query model change within family doesn't trigger reindex."""
    # 1. Create collection with voyage-4-large
    # 2. Change query model to voyage-4-nano
    # 3. Run doctor check
    # 4. Assert: impact == ChangeImpact.COMPATIBLE
    # 5. Assert: no reindex required

async def test_dimension_change_triggers_transformation():
    """Verify dimension change offers transformation."""
    # 1. Create collection with dimension=2048
    # 2. Change config to dimension=1024
    # 3. Run config analyzer
    # 4. Assert: impact == ChangeImpact.TRANSFORMABLE
    # 5. Assert: transformation plan provided

# Phase 2 Integration Tests
async def test_dimension_migration_end_to_end():
    """Verify complete dimension migration workflow."""
    # 1. Index 1000 files with dimension=2048
    # 2. Migrate to dimension=1024
    # 3. Validate vector count matches
    # 4. Validate search quality (MTEB benchmark)
    # 5. Assert: accuracy_loss < 1%

async def test_migration_recovery_from_failure():
    """Verify migration resumes correctly after failure."""
    # 1. Start migration of 10k vectors
    # 2. Inject failure at 5000 vectors
    # 3. Resume migration
    # 4. Assert: all 10k vectors migrated
    # 5. Assert: no duplicates
```

### Principle V: Simplicity Through Architecture ✅ **Compliant**

**Evidence**:
- Clear separation: detection (Phase 1) vs transformation (Phase 2)
- Flat module structure
- Obvious purpose for each component

**Recommendation**: Improve by extracting interfaces:
```python
# Clear protocol interfaces
class ConfigAnalyzer(Protocol): ...
class MigrationService(Protocol): ...
class RollbackService(Protocol): ...

# Simple composition
class ConfigMigrationOrchestrator:
    def __init__(
        self,
        analyzer: ConfigAnalyzer,
        migration: MigrationService,
        rollback: RollbackService,
    ):
        self.analyzer = analyzer
        self.migration = migration
        self.rollback = rollback
```

---

## 10. Alternative Approaches

### Alternative 1: In-Place Dimension Truncation (Rejected)

**Idea**: Modify vectors in-place instead of blue-green migration.

**Pros**:
- Faster (no collection copy)
- Less disk space

**Cons**:
- ❌ No rollback capability
- ❌ Risky (corruption if fails mid-update)
- ❌ Qdrant doesn't support in-place vector dimension changes

**Verdict**: **Rejected**. Blue-green is safer and aligns with Constitutional Principle III (evidence-based, no workarounds).

### Alternative 2: Always Reindex (Rejected)

**Idea**: Skip transformations, always reindex from source.

**Pros**:
- Simpler implementation
- Guaranteed fresh embeddings

**Cons**:
- ❌ Wasteful for benign changes (query model within family)
- ❌ Expensive ($$ for API embeddings)
- ❌ Slow (minutes to hours vs seconds)

**Verdict**: **Rejected**. Contradicts Voyage-3 benchmark evidence showing minimal accuracy loss.

### Alternative 3: Lazy Migration (Considered)

**Idea**: Migrate vectors on-demand during queries instead of upfront.

**Pros**:
- Zero downtime
- Gradual migration

**Cons**:
- ⚠️ Complex query path (check dimension, truncate if needed)
- ⚠️ Inconsistent query latency
- ⚠️ Hard to track migration progress

**Verdict**: **Consider for future**. Interesting for zero-downtime requirements, but adds complexity. Could be Phase 4 enhancement.

### Alternative 4: Qdrant Collection Aliases (Adopted ✅)

**Idea**: Use Qdrant aliases for blue-green switching.

**Pros**:
- ✅ Atomic switching
- ✅ Zero downtime
- ✅ Clean rollback

**Cons**:
- None significant

**Verdict**: **Adopted**. Plan already uses this (line 635-639).

---

## 11. Open Questions Resolution

### Q1: Collection Naming
**Question**: Should we enforce internal versioned names for all collections?

**Recommendation**: **No, only when migrations happen.**

**Rationale**:
- User-friendly names better for simple use cases
- Versioned names add complexity
- Only needed when rollback capability required

**Implementation**:
```python
async def create_collection(
    self,
    name: str,
    enable_versioning: bool = False,
) -> str:
    """Create collection with optional versioning."""
    if enable_versioning:
        versioned_name = f"{name}_{datetime.now():%Y%m%d_%H%M%S}"
        await self._create_versioned_collection(versioned_name)
        await self._create_alias(name, versioned_name)
        return versioned_name
    else:
        await self._create_simple_collection(name)
        return name
```

### Q2: Rollback Duration
**Question**: 7 days for rollback seems reasonable, but should it be configurable?

**Recommendation**: **Yes, make it configurable with 7-day default.**

**Implementation**:
```python
# In config
class MigrationSettings(BasedModel):
    rollback_retention_days: int = 7
    auto_cleanup_enabled: bool = True

# In service
async def cleanup_old_rollback_targets(self):
    """Clean up rollback targets older than retention period."""
    retention = self.config.migration.rollback_retention_days
    cutoff = datetime.now(UTC) - timedelta(days=retention)

    for version in await self._list_rollback_targets():
        if version.created_at < cutoff:
            await self._delete_collection(version.collection_name)
```

### Q3: Transformation Defaults
**Question**: Should we auto-apply COMPATIBLE changes, or always ask?

**Recommendation**: **Auto-apply COMPATIBLE, ask for TRANSFORMABLE, block BREAKING.**

**Rationale**:
- COMPATIBLE = same family query model change (safe, no data change)
- TRANSFORMABLE = dimension/quantization (data change, needs approval)
- BREAKING = model switch (dangerous, explicit user action)

**Implementation**:
```python
async def apply_config_change(
    self,
    analysis: ConfigChangeAnalysis,
    force: bool = False,
) -> ConfigChangeResult:
    """Apply configuration change with appropriate approval."""

    match analysis.impact:
        case ChangeImpact.NONE:
            # No-op
            return ConfigChangeResult(applied=False, reason="No change")

        case ChangeImpact.COMPATIBLE:
            # Auto-apply (query model within family)
            logger.info("Auto-applying compatible change")
            await self._update_collection_metadata(analysis.new_config)
            return ConfigChangeResult(applied=True, auto=True)

        case ChangeImpact.QUANTIZABLE | ChangeImpact.TRANSFORMABLE:
            # Ask user
            if not force:
                approval = await self._prompt_user(analysis)
                if not approval:
                    return ConfigChangeResult(applied=False, reason="User declined")

            result = await self._apply_transformation(analysis)
            return ConfigChangeResult(applied=True, auto=False, result=result)

        case ChangeImpact.BREAKING:
            # Block unless forced
            if not force:
                raise ConfigurationError(
                    "Breaking change detected. Use --force to override."
                )

            logger.warning("Forcing breaking change (--force flag)")
            await self._full_reindex()
            return ConfigChangeResult(applied=True, forced=True)
```

### Q4: Profile Evolution
**Question**: How should we handle profile updates between minor vs. major versions?

**Recommendation**: **Semantic versioning with migration notifications.**

**Implementation**:
```python
# In profiles.py
class ProfileVersion:
    major: int  # Breaking changes (incompatible)
    minor: int  # New features (compatible)
    patch: int  # Bug fixes (compatible)

    def is_compatible_with(self, other: ProfileVersion) -> bool:
        """Major version must match."""
        return self.major == other.major

# In doctor check
async def check_profile_compatibility(settings):
    """Check if profile version is compatible with collection."""
    metadata = await vector_store.get_collection_metadata()

    if not metadata.profile_version:
        return DoctorCheck.warning("Profile version unknown (pre-v0.3)")

    current = ProfileVersion.parse(settings.profile.version)
    collection = ProfileVersion.parse(metadata.profile_version)

    if not current.is_compatible_with(collection):
        return DoctorCheck.fail(
            f"Profile major version mismatch: "
            f"collection uses {collection.major}.x, "
            f"current profile is {current.major}.x. "
            f"Reindex required."
        )

    if current.minor > collection.minor:
        return DoctorCheck.warning(
            f"Profile updated to {current}. "
            f"Collection uses {collection}. "
            f"Run 'cw optimize' to apply improvements."
        )

    return DoctorCheck.success("Profile version compatible")
```

### Q5: Quantization Rescoring
**Question**: Always enable by default, or make it configurable?

**Recommendation**: **Enable by default with config option.**

**Rationale**:
- Rescoring improves accuracy (Qdrant best practice)
- Minimal performance impact
- Can be disabled for speed-critical applications

**Implementation**:
```python
# In config
class QuantizationSettings(BasedModel):
    type: Literal["int8", "binary", None] = None
    rescore: bool = True  # Default: enabled

# In service
async def apply_quantization(self, config: QuantizationSettings):
    """Apply quantization with optional rescoring."""
    quantization_config = self._build_quantization_config(
        type=config.type,
        rescore=config.rescore,
    )

    await self.client.update_collection(
        collection_name=self.collection_name,
        quantization_config=quantization_config,
    )
```

### Q6: Doctor Frequency
**Question**: Should `cw doctor` run automatically, or only on-demand?

**Recommendation**: **On-demand by default, with --watch mode for continuous monitoring.**

**Rationale**:
- Auto-run can be annoying/slow
- But continuous monitoring useful for CI/CD
- Let users choose their preference

**Implementation**:
```bash
# On-demand (default)
cw doctor

# Continuous monitoring
cw doctor --watch

# CI/CD integration
cw doctor --format=json --exit-code
```

### Q7: Migration Validation
**Question**: What validation checks should be mandatory vs. optional?

**Recommendation**: **Mandatory: vector count, schema. Optional: search quality.**

**Validation Levels**:
```python
class ValidationLevel(Enum):
    MINIMAL = "minimal"      # Just count
    STANDARD = "standard"    # Count + schema
    THOROUGH = "thorough"    # + sample search quality

async def validate_migration(
    self,
    source: str,
    target: str,
    level: ValidationLevel = ValidationLevel.STANDARD,
) -> ValidationResult:
    """Validate migration at specified level."""

    errors = []

    # MANDATORY: Vector count
    source_count = await self.client.count(source)
    target_count = await self.client.count(target)

    if source_count != target_count:
        errors.append(f"Count mismatch: {source_count} vs {target_count}")

    if level >= ValidationLevel.STANDARD:
        # MANDATORY: Schema validation
        source_schema = await self._get_schema(source)
        target_schema = await self._get_schema(target)

        if source_schema.payload != target_schema.payload:
            errors.append("Payload schema mismatch")

    if level >= ValidationLevel.THOROUGH:
        # OPTIONAL: Search quality
        quality_loss = await self._benchmark_search_quality(source, target)

        if quality_loss > 0.05:  # > 5% loss
            errors.append(f"Search quality degraded by {quality_loss:.1%}")

    return ValidationResult(
        passed=len(errors) == 0,
        errors=errors,
        level=level,
    )
```

### Q8: Error Recovery
**Question**: If dimension migration fails mid-way, what's the safest recovery path?

**Recommendation**: **Resume from checkpoint (safest), or rollback (if corrupt).**

**Decision Tree**:
```python
async def recover_from_migration_failure(
    self,
    checkpoint: MigrationCheckpoint,
) -> RecoveryResult:
    """Recover from failed migration."""

    # 1. Assess damage
    target_count = await self.client.count(checkpoint.target_collection)
    expected_count = checkpoint.vectors_migrated

    if target_count == expected_count:
        # Clean failure, target collection intact
        logger.info("Target collection intact, resuming...")
        return await self.resume_migration(checkpoint)

    elif target_count < expected_count:
        # Partial failure, some vectors lost
        logger.warning(
            "Target collection has fewer vectors than expected. "
            "Rolling back..."
        )
        await self._delete_collection(checkpoint.target_collection)
        return RecoveryResult(
            strategy="rollback",
            message="Migration failed, target deleted. Retry with 'cw migrate apply'",
        )

    else:  # target_count > expected_count
        # Impossible unless checkpoint is stale
        raise RecoveryError(
            "Target has more vectors than checkpoint indicates. "
            "Checkpoint may be stale or corrupted."
        )
```

---

## 12. Final Recommendations

### Phase 1 (Sprint 1) - Approve with Modifications

**Must-Have Changes**:
1. ✅ Fix checkpoint integration (section 8.1.1)
2. ✅ Change `CheckpointSettingsFingerprint` to `BasedModel` (section 8.1.2)
3. ✅ Add `ConfigurationHistoryRepository` (section 8.1.3)
4. ✅ Specify integration tests explicitly (section 9, Principle IV)

**Should-Have Changes**:
5. ✅ Improve `ConfigChangeAnalysis` API with structured types (section 5.1)
6. ✅ Add programmatic API spec (even if implementation deferred) (section 5.3)

**Estimated Effort**: 1 week → **1.5 weeks** (with modifications)

### Phase 2 (Sprint 2-3) - Conditional Approval

**Prerequisites**:
1. ✅ Implement parallel migration workers (section 3.1)
2. ✅ Implement migration checkpointing (section 4.2)
3. ✅ Add error recovery with retry logic (section 4.1)
4. ✅ Update manifest after transformations (section 2.2)

**Should-Have**:
5. ✅ Restructure modules per section 6.1
6. ✅ Add rate limiting (section 3.2)

**Recommendation**: **Defer Phase 2 until Phase 1 complete and validated.**

**Estimated Effort**: 2 weeks → **3 weeks** (with resilience improvements)

### Phase 3 (Sprint 4-6) - Redesign Recommended

**Current Issues**:
- Collection policies feel heavyweight
- Profile versioning conflicts with DI migration (planned)
- Optimization wizard scope creep

**Recommended Restructure**:
1. **Replace registry-based approach with dependency injection** (Constitutional alignment)
2. **Simplify collection policies** to just `strict` vs `flexible`
3. **Make profile versioning passive** (detect, warn, don't enforce)
4. **Defer optimization wizard** to Phase 4 (AI-powered optimization)

**Estimated Effort**: 3 weeks → **2 weeks** (with simplification)

---

## 13. Summary

### Overall Assessment: **APPROVE WITH MODIFICATIONS**

**Strengths**:
- ✅ Excellent foundation with asymmetric embedding support already in place
- ✅ Constitutional compliance with evidence-based development
- ✅ Smart use of blue-green migration for safety
- ✅ Clear phasing and separation of concerns

**Critical Gaps**:
- ❌ Checkpoint integration needs fixing (Phase 1 blocker)
- ❌ Scalability not addressed (Phase 2 blocker)
- ❌ Error recovery insufficient (Phase 2 blocker)

**Recommended Path Forward**:
1. **Implement Phase 1** with modifications from section 8.1
2. **Validate Phase 1** with comprehensive integration tests
3. **Prototype parallel migration** before committing to Phase 2
4. **Benchmark performance** with 100k+ vectors on real Qdrant instance
5. **Redesign Phase 3** around dependency injection patterns
6. **Iterate** based on early user feedback (Alpha testing)

### Risk-Adjusted Timeline

| Phase | Original | Adjusted | Confidence |
|-------|----------|----------|------------|
| Phase 1 | 1 week | 1.5 weeks | High (85%) |
| Phase 2 | 2 weeks | 3 weeks | Medium (70%) |
| Phase 3 | 3 weeks | 2 weeks | Low (60%) |
| **Total** | **6 weeks** | **6.5 weeks** | **Medium (72%)** |

**Recommendation**: Budget **8 weeks** to account for unknowns and beta testing.

---

## Appendix: Constitutional Compliance Checklist

- [x] **Principle I (AI-First Context)**: Doctor command provides AI-consumable compatibility status
- [x] **Principle II (Proven Patterns)**: Blue-green migration, Strategy pattern, Repository pattern used
- [x] **Principle III (Evidence-Based)**: Voyage-3 benchmarks validate transformation approach
- [ ] **Principle IV (Testing Philosophy)**: Integration test specs missing (must add in Phase 1)
- [x] **Principle V (Simplicity)**: Clear separation of concerns, flat structure, obvious purpose

**Overall**: 4/5 principles satisfied. Phase 1 modifications will achieve 5/5.

---

**End of Architecture Review**
