# CodeWeaver Failover Architecture Implementation Plan

**Date**: 2026-01-18
**Status**: Design Complete - Implementation Pending
**Priority**: High - Alpha Release 3 Target

## Executive Summary

This plan details the implementation strategy for CodeWeaver's failover system to handle remote provider failures with minimal interruption, no disabled features, and minimal compute overhead. The architecture leverages the new DI system, multi-granularity chunking, and Span-based reconciliation to provide seamless degradation to backup providers when primary providers fail.

**Key Goals:**
- Zero feature degradation during failover
- Minimal compute overhead (<10% in healthy state)
- Fast recovery with intelligent chunk reuse
- Context window deconfliction via DI-driven configuration

---

## Table of Contents

1. [Architectural Overview](#architectural-overview)
2. [Core Architectural Decisions](#core-architectural-decisions)
3. [Current State Analysis](#current-state-analysis)
4. [Required Changes](#required-changes)
5. [Implementation Phases](#implementation-phases)
6. [Integration Points](#integration-points)
7. [Testing Strategy](#testing-strategy)
8. [Risk Mitigation](#risk-mitigation)

---

## Architectural Overview

### System Context

**Current State:**
- New DI system in `src/codeweaver/core/di/`
- Provider implementations with backup namespacing
- Incomplete engine refactor (missing many old features)
- Single-granularity chunking per file
- Basic failover via `BackupEmbeddingProvider` (synchronous fallback only)

**Target State:**
- Multi-granularity chunk storage (primary + backup)
- Event-driven failover state machine
- Intelligent chunk reconciliation using Span operations
- DI-driven pipeline isolation (primary/backup separation)
- Shadow write-ahead log for remote vector store failures

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Client Request                        │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Failover State Machine (Event-Driven)           │
│  States: HEALTHY → DEGRADED → BACKUP_ONLY → RECOVERY        │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        ▼                                       ▼
┌──────────────────┐                 ┌──────────────────┐
│  Primary Pipeline│                 │  Backup Pipeline │
│  (DI Tag: primary)│                │ (DI Tag: backup) │
│                  │                 │                  │
│ • Embedding: 4K  │                 │ • Embedding: 512 │
│ • Reranker: 4K   │                 │ • Reranker: 512  │
│ • Collection: pri│                 │ • Collection: bak│
│ • Chunks: coarse │                 │ • Chunks: fine   │
└──────────────────┘                 └──────────────────┘
        │                                       │
        └───────────────────┬───────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│           Span-Based Chunk Reconciliation                    │
│  • UUID7 temporal tracking (file modification timestamps)    │
│  • Set operations: union, intersection, difference           │
│  • Smart reuse: backup chunks cover primary gaps             │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Architectural Decisions

### Decision 1: DI-Driven Pipeline Isolation

**Rationale:** Separate primary and backup pipelines at the DI container level to prevent coupling and enable independent configuration.

**Implementation:**
```python
# src/codeweaver/core/di/container.py - Enhanced registration

container.register(
    EmbeddingProvider,
    VoyageEmbeddingProvider,
    tags={"tier": "primary", "profile": "default"},
    scope=Scope.SINGLETON
)

container.register(
    EmbeddingProvider,
    FastEmbedProvider,
    tags={"tier": "backup", "profile": "default"},
    scope=Scope.SINGLETON
)

# Resolution with constraint
primary_provider = container.resolve(
    EmbeddingProvider,
    constraints={"tier": "primary"}
)
```

**Benefits:**
- Clean separation of concerns
- Independent lifecycle management
- Easy configuration switching
- Testable in isolation

### Decision 2: Multi-Granularity Chunk Storage

**Rationale:** Store chunks at different token sizes to accommodate different reranker context windows without re-chunking during failover.

**Storage Strategy:**
```yaml
Primary Pipeline:
  chunk_size: 4000 tokens  # Voyage reranker context window
  collection: "primary"
  embedding_batch_key: "primary_dense"

Backup Pipeline:
  chunk_size: 512 tokens   # Cohere reranker context window
  collection: "backup"
  embedding_batch_key: "secondary_dense"

Reconciliation:
  strategy: "span_intersection"
  deduplication: "blake3_hash"
  temporal_filter: "uuid7_timestamp"
```

**Key Properties:**
- Both chunk sets share same `DiscoveredFile.source_id` (UUID7)
- Enables Span-based reconciliation: `backup_spans ∩ primary_spans`
- Blake3 hash prevents duplicate content across granularities
- UUID7 timestamp enables temporal filtering during recovery

### Decision 3: Span-Based Reconciliation

**Rationale:** Use existing Span set operations to identify which backup chunks can substitute for failed primary chunks.

**Reconciliation Algorithm:**
```python
def reconcile_chunks(
    source_id: UUID7,
    failed_chunks: list[CodeChunk],
    backup_chunks: list[CodeChunk]
) -> tuple[list[CodeChunk], list[CodeChunk]]:
    """
    Returns: (reusable_backup_chunks, chunks_needing_embedding)

    Algorithm:
    1. Extract SpanGroup from failed chunks (failed_spans)
    2. For each backup chunk:
       - If backup.span ∩ failed_spans != ∅ → reusable
    3. Compute gap: failed_spans - covered_spans
    4. Create minimal chunks for gaps
    """
    failed_spans = SpanGroup.from_chunks(failed_chunks)
    reusable = []

    for backup_chunk in backup_chunks:
        if backup_chunk.line_range.source_id == source_id:
            if failed_spans.contains_span(backup_chunk.line_range):
                reusable.append(backup_chunk)

    covered_spans = SpanGroup.from_chunks(reusable)
    gap_spans = failed_spans - covered_spans

    return (reusable, create_chunks_for_gaps(gap_spans))
```

**Benefits:**
- Leverages existing immutable Span operations
- Minimal re-embedding during recovery
- Mathematically sound (set theory)
- Testable with simple unit tests

### Decision 4: Vector Store Dual-Write Strategy

**Rationale:** Write to both primary and backup collections during healthy operation to enable instant failover.

**Implementation:**
```python
async def store_chunks(
    chunks: list[CodeChunk],
    state: FailoverState
) -> None:
    """Store chunks with collection namespacing."""
    if state == FailoverState.HEALTHY:
        # Dual write to both collections
        await asyncio.gather(
            vector_store.upsert(chunks, collection="primary"),
            vector_store.upsert(chunks, collection="backup")
        )
    elif state == FailoverState.BACKUP_ONLY:
        # Write only to backup
        await vector_store.upsert(chunks, collection="backup")
```

**Collection Naming:**
```
Primary:   "{project_id}_primary_{provider_name}"
Backup:    "{project_id}_backup_{provider_name}"
Shadow:    "{project_id}_shadow_wal"  # For remote failures
```

**Overhead Analysis:**
- **Storage**: 2x vectors (acceptable for reliability)
- **Indexing**: Parallel writes (~10% overhead)
- **Search**: Only query active collection (no overhead)

### Decision 5: Event-Driven Failover State Machine

**Rationale:** Explicit state transitions with timeout/circuit breaker logic prevent thrashing and enable observability.

**State Diagram:**
```
           ┌─────────────┐
           │   HEALTHY   │ ◄──────────────┐
           └──────┬──────┘                 │
                  │                        │
         [provider_error]            [all_green_for_5min]
                  │                        │
                  ▼                        │
           ┌─────────────┐                 │
           │  DEGRADED   │                 │
           └──────┬──────┘                 │
                  │                        │
     [3_consecutive_failures]              │
                  │                        │
                  ▼                        │
           ┌─────────────┐                 │
           │ BACKUP_ONLY │                 │
           └──────┬──────┘                 │
                  │                        │
         [primary_restored]                │
                  │                        │
                  ▼                        │
           ┌─────────────┐                 │
           │  RECOVERY   │─────────────────┘
           └─────────────┘
```

**State Behaviors:**
- **HEALTHY**: Use primary, write to both collections
- **DEGRADED**: Try primary with fast timeout, fall back to backup
- **BACKUP_ONLY**: Use backup exclusively, log all attempts
- **RECOVERY**: Reconcile chunks, validate primary, transition to HEALTHY

**Transition Parameters:**
```python
class FailoverConfig(BasedModel):
    degraded_timeout_ms: int = 500      # Fast timeout in degraded
    failure_threshold: int = 3          # Failures before BACKUP_ONLY
    recovery_window_sec: int = 300      # Green period before HEALTHY
    circuit_breaker_reset_sec: int = 60 # Time before retry
```

### Decision 6: UUID7 Temporal Filtering

**Rationale:** UUID7 encodes creation timestamp in first 48 bits, enabling efficient filtering of chunks modified during outages.

**Recovery Optimization:**
```python
def filter_chunks_modified_during_outage(
    all_chunks: list[CodeChunk],
    outage_start: datetime,
    outage_end: datetime
) -> list[CodeChunk]:
    """Filter chunks by source_id timestamp."""
    return [
        chunk for chunk in all_chunks
        if outage_start <= chunk.line_range.source_id.timestamp <= outage_end
    ]
```

**Benefits:**
- No separate timestamp field needed
- Efficient range queries on UUID index
- Reduces recovery scope (only process affected files)
- Built into existing data model

### Decision 7: Capability Resolution for Context Windows

**Rationale:** Use DI-resolved capability groups to determine chunk sizes automatically, avoiding hardcoded limits.

**Implementation:**
```python
# src/codeweaver/engine/chunker/base.py - ChunkGovernor

@computed_field
@property
def chunk_limit(self) -> PositiveInt:
    """Compute chunk limit from capability constraints."""
    if not self._limit_established and self.capabilities:
        self._limit_established = True
        self._limit = min(
            capability.context_window
            for capability in self.capabilities
            if hasattr(capability, "context_window")
        )
    return self._limit

# Usage in DI
primary_governor = ChunkGovernor(
    capabilities=container.resolve(
        EmbeddingCapabilityGroup,
        constraints={"tier": "primary"}
    )
)
# chunk_limit = 4000 (from Voyage reranker)

backup_governor = ChunkGovernor(
    capabilities=container.resolve(
        EmbeddingCapabilityGroup,
        constraints={"tier": "backup"}
    )
)
# chunk_limit = 512 (from Cohere reranker)
```

---

## Current State Analysis

### ✅ Working Components

#### 1. Source ID Propagation
**Location**: `src/codeweaver/core/discovery.py:92-97`

```python
class DiscoveredFile(BasedModel):
    source_id: UUID7 = uuid7()  # Shared with all chunks
```

**Verification**: Both `DelimiterChunker` and `SemanticChunker` properly create `Span(start, end, source_id)` objects:
- `delimiter.py:1153`: `Span(start_line, end_line, source_id)`
- `semantic.py:878`: `Span(node.range.start.line + 1, node.range.end.line + 1, source_id)`

**Status**: ✅ Complete and tested

#### 2. Span Set Operations
**Location**: `src/codeweaver/core/spans.py`

```python
class Span(NamedTuple):
    start: PositiveInt
    end: PositiveInt
    source_id: UUID7

    def __and__(self, other: Span) -> Span | None:  # Intersection
        if self.source_id != other.source_id:
            return None
        start = max(self.start, other.start)
        end = min(self.end, other.end)
        return Span(start, end, self.source_id) if start <= end else None

    def __or__(self, other: Span) -> Span | None:   # Union (if adjacent)
    def __sub__(self, other: Span) -> tuple[Span, ...]:  # Difference
```

**Status**: ✅ Complete with full set algebra

#### 3. ChunkGovernor Backup Profiles
**Location**: `src/codeweaver/engine/chunker/base.py:148-235`

```python
@classmethod
def from_backup_profile(
    cls,
    primary_governor: ChunkGovernor,
    backup_capabilities: EmbeddingCapabilityGroup
) -> ChunkGovernor:
    """Create backup governor with constrained capabilities."""
    # Already implemented!
```

**Status**: ✅ Complete, ready to use

#### 4. Smart Chunk Reuse
**Location**: `src/codeweaver/engine/services/chunking_service.py:77-99`

```python
def _chunk_with_reuse(
    self,
    files: list[DiscoveredFile],
    source_chunks: dict[Path, list[CodeChunk]]
) -> Iterator[tuple[Path, list[CodeChunk]]]:
    """Smart reuse logic for backup scenarios."""
    # Already implemented!
```

**Status**: ✅ Complete, needs integration

### ⚠️ Missing Components

#### 1. Multi-Granularity Chunking
**Current**: `ChunkingService` creates single granularity per file
**Required**: Create both primary (coarse) and backup (fine) chunks simultaneously

**Gap**: No method to create dual-granularity chunk sets

#### 2. Dual Storage Orchestration
**Current**: `IndexingService` stores single chunk set
**Required**: Store both primary and backup chunks with collection namespacing

**Gap**: No orchestration for parallel storage to multiple collections

#### 3. Failover State Machine
**Current**: Simple synchronous fallback in `BackupEmbeddingProvider`
**Required**: Event-driven state machine with circuit breaker

**Gap**: No state tracking, no degraded mode, no recovery protocol

#### 4. Span Reconciliation Logic
**Current**: Span operations exist but unused for recovery
**Required**: Algorithm to match backup chunks to failed primary chunks

**Gap**: No reconciliation implementation

#### 5. DI Provider Tagging
**Current**: Basic DI registration without tags
**Required**: Tag-based resolution for primary/backup separation

**Gap**: Tags not used in current DI registrations

---

## Required Changes

### Phase 1: Multi-Granularity Chunking Foundation

#### 1.1 Extend ChunkingService

**File**: `src/codeweaver/engine/services/chunking_service.py`

**Changes**:
```python
class ChunkingService:
    def __init__(
        self,
        governor: ChunkGovernor,
        tokenizer: Tokenizer,
        settings: ChunkerSettings,
        backup_governor: ChunkGovernor | None = None  # NEW
    ) -> None:
        self.governor = governor
        self.backup_governor = backup_governor
        self.tokenizer = tokenizer
        self.settings = settings
        self._selector = ChunkerSelector(governor, tokenizer)

        # Create backup selector if backup governor provided
        if backup_governor:
            self._backup_selector = ChunkerSelector(backup_governor, tokenizer)

    def chunk_files_dual_granularity(
        self,
        files: list[DiscoveredFile],
        *,
        max_workers: int | None = None,
        executor_type: str | None = None,
    ) -> Iterator[tuple[Path, dict[str, list[CodeChunk]]]]:
        """Create chunks at both primary and backup granularities.

        Returns:
            Iterator of (path, {"primary": [...], "backup": [...]})

        Notes:
            - Requires backup_governor to be set (via DI or constructor)
            - Both chunk sets share same source_id from DiscoveredFile
            - Enables Span-based reconciliation during recovery
        """
        if not self.backup_governor:
            raise ValueError("backup_governor required for dual granularity")

        for file in files:
            try:
                # Primary chunks (coarse)
                primary_chunker = self._selector.select_for_file(file)
                content = file.absolute_path.read_text(encoding="utf-8", errors="ignore")
                primary_chunks = primary_chunker.chunk(content, file=file)

                # Backup chunks (fine)
                backup_chunker = self._backup_selector.select_for_file(file)
                backup_chunks = backup_chunker.chunk(content, file=file)

                yield (file.path, {
                    "primary": primary_chunks,
                    "backup": backup_chunks
                })
            except Exception:
                logger.warning(
                    "Failed dual chunking for %s, using fallback",
                    file.path,
                    exc_info=True
                )
                # Fallback: only create backup chunks
                backup_chunker = self._backup_selector.select_for_file(file)
                content = file.absolute_path.read_text(encoding="utf-8", errors="ignore")
                backup_chunks = backup_chunker.chunk(content, file=file)

                yield (file.path, {
                    "primary": [],
                    "backup": backup_chunks
                })
```

**Testing**:
```python
# tests/engine/services/test_chunking_service.py

def test_dual_granularity_chunking():
    """Verify both primary and backup chunks created with same source_id."""
    primary_gov = ChunkGovernor(chunk_limit=4000)
    backup_gov = ChunkGovernor(chunk_limit=512)

    service = ChunkingService(
        governor=primary_gov,
        backup_governor=backup_gov,
        tokenizer=tokenizer,
        settings=settings
    )

    file = DiscoveredFile.from_path(Path("test.py"))
    result = list(service.chunk_files_dual_granularity([file]))[0]
    path, chunks = result

    assert "primary" in chunks
    assert "backup" in chunks
    assert len(chunks["primary"]) > 0
    assert len(chunks["backup"]) > 0

    # Verify same source_id
    primary_source_id = chunks["primary"][0].line_range.source_id
    backup_source_id = chunks["backup"][0].line_range.source_id
    assert primary_source_id == backup_source_id == file.source_id

    # Verify token limits respected
    for chunk in chunks["primary"]:
        assert tokenizer.count_tokens(chunk.content) <= 4000
    for chunk in chunks["backup"]:
        assert tokenizer.count_tokens(chunk.content) <= 512
```

#### 1.2 Update IndexingService

**File**: `src/codeweaver/engine/services/indexing_service.py`

**Changes**:
```python
class IndexingService:
    def __init__(
        self,
        chunking_service: ChunkingService,
        embedding_service: EmbeddingService,
        vector_store: VectorStoreProvider,
        backup_vector_store: VectorStoreProvider | None = None,  # NEW
        failover_state: FailoverState = FailoverState.HEALTHY,   # NEW
    ) -> None:
        self._chunking_service = chunking_service
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._backup_vector_store = backup_vector_store
        self._failover_state = failover_state

    async def index_files(
        self,
        files: list[DiscoveredFile],
        *,
        progress_callback: Callable[[float], None] | None = None
    ) -> IndexingResult:
        """Index files with dual-granularity storage."""
        all_primary_chunks = []
        all_backup_chunks = []

        # Create chunks at both granularities
        for path, chunk_dict in self._chunking_service.chunk_files_dual_granularity(
            files
        ):
            all_primary_chunks.extend(chunk_dict["primary"])
            all_backup_chunks.extend(chunk_dict["backup"])

        # Embed chunks
        primary_embeddings = await self._embedding_service.embed_batch(
            all_primary_chunks,
            tier="primary"
        )
        backup_embeddings = await self._embedding_service.embed_batch(
            all_backup_chunks,
            tier="backup"
        )

        # Store with collection namespacing
        if self._failover_state == FailoverState.HEALTHY:
            # Dual write to both collections
            await asyncio.gather(
                self._vector_store.upsert(
                    primary_embeddings,
                    collection="primary"
                ),
                self._vector_store.upsert(
                    backup_embeddings,
                    collection="backup"
                )
            )
        elif self._failover_state == FailoverState.BACKUP_ONLY:
            # Only write to backup
            await self._vector_store.upsert(
                backup_embeddings,
                collection="backup"
            )

        return IndexingResult(
            primary_chunks=len(all_primary_chunks),
            backup_chunks=len(all_backup_chunks),
            state=self._failover_state
        )
```

### Phase 2: Failover State Machine

#### 2.1 Create State Machine

**New File**: `src/codeweaver/engine/failover/state_machine.py`

```python
from enum import Enum
from datetime import datetime, timedelta
from typing import Callable
from pydantic import BaseModel

class FailoverState(str, Enum):
    """Failover system states."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BACKUP_ONLY = "backup_only"
    RECOVERY = "recovery"

class FailoverEvent(str, Enum):
    """Events triggering state transitions."""
    PROVIDER_ERROR = "provider_error"
    CONSECUTIVE_FAILURES = "consecutive_failures"
    PRIMARY_RESTORED = "primary_restored"
    ALL_GREEN = "all_green"

class FailoverConfig(BaseModel):
    """Configuration for failover behavior."""
    degraded_timeout_ms: int = 500
    failure_threshold: int = 3
    recovery_window_sec: int = 300
    circuit_breaker_reset_sec: int = 60
    max_retries: int = 3

class FailoverStateMachine:
    """Event-driven state machine for provider failover."""

    def __init__(
        self,
        config: FailoverConfig,
        on_state_change: Callable[[FailoverState, FailoverState], None] | None = None
    ) -> None:
        self.config = config
        self.state = FailoverState.HEALTHY
        self.failure_count = 0
        self.last_failure: datetime | None = None
        self.recovery_start: datetime | None = None
        self.on_state_change = on_state_change

    def handle_event(self, event: FailoverEvent) -> FailoverState:
        """Process event and transition state."""
        old_state = self.state

        if event == FailoverEvent.PROVIDER_ERROR:
            self._handle_provider_error()
        elif event == FailoverEvent.CONSECUTIVE_FAILURES:
            self._handle_consecutive_failures()
        elif event == FailoverEvent.PRIMARY_RESTORED:
            self._handle_primary_restored()
        elif event == FailoverEvent.ALL_GREEN:
            self._handle_all_green()

        new_state = self.state

        if old_state != new_state and self.on_state_change:
            self.on_state_change(old_state, new_state)

        return new_state

    def _handle_provider_error(self) -> None:
        """Handle primary provider error."""
        self.failure_count += 1
        self.last_failure = datetime.now(UTC)

        if self.state == FailoverState.HEALTHY:
            self.state = FailoverState.DEGRADED
        elif self.state == FailoverState.DEGRADED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = FailoverState.BACKUP_ONLY

    def _handle_consecutive_failures(self) -> None:
        """Handle threshold of consecutive failures."""
        self.state = FailoverState.BACKUP_ONLY

    def _handle_primary_restored(self) -> None:
        """Handle primary provider restoration."""
        if self.state == FailoverState.BACKUP_ONLY:
            self.state = FailoverState.RECOVERY
            self.recovery_start = datetime.now(UTC)

    def _handle_all_green(self) -> None:
        """Handle sustained healthy period."""
        if self.state == FailoverState.RECOVERY:
            # Check if recovery window elapsed
            if self.recovery_start:
                elapsed = datetime.now(UTC) - self.recovery_start
                if elapsed.total_seconds() >= self.config.recovery_window_sec:
                    self.state = FailoverState.HEALTHY
                    self.failure_count = 0
                    self.recovery_start = None

    def should_use_primary(self) -> bool:
        """Check if primary provider should be attempted."""
        return self.state in (FailoverState.HEALTHY, FailoverState.DEGRADED, FailoverState.RECOVERY)

    def should_use_backup(self) -> bool:
        """Check if backup provider should be used."""
        return self.state in (FailoverState.DEGRADED, FailoverState.BACKUP_ONLY)

    def get_timeout_ms(self) -> int:
        """Get timeout for current state."""
        if self.state == FailoverState.DEGRADED:
            return self.config.degraded_timeout_ms
        return 30000  # Default 30s
```

#### 2.2 Integrate State Machine with Providers

**File**: `src/codeweaver/providers/embedding/providers/base.py`

```python
class FailoverEmbeddingProvider(BaseEmbeddingProvider):
    """Embedding provider with failover support."""

    def __init__(
        self,
        primary: BaseEmbeddingProvider,
        backup: BaseEmbeddingProvider,
        state_machine: FailoverStateMachine,
    ) -> None:
        self.primary = primary
        self.backup = backup
        self.state_machine = state_machine

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed with failover logic."""
        if self.state_machine.should_use_primary():
            try:
                timeout = self.state_machine.get_timeout_ms() / 1000
                return await asyncio.wait_for(
                    self.primary.embed(texts),
                    timeout=timeout
                )
            except Exception as e:
                logger.warning("Primary provider failed: %s", e)
                self.state_machine.handle_event(FailoverEvent.PROVIDER_ERROR)

                if not self.state_machine.should_use_backup():
                    raise

        # Use backup
        return await self.backup.embed(texts)
```

### Phase 3: Span Reconciliation

#### 3.1 Create Reconciliation Service

**New File**: `src/codeweaver/engine/failover/reconciliation.py`

```python
from typing import NamedTuple
from codeweaver.core import CodeChunk, Span, SpanGroup, UUID7

class ReconciliationResult(NamedTuple):
    """Result of chunk reconciliation."""
    reusable_chunks: list[CodeChunk]
    gaps_needing_embedding: list[tuple[Span, str]]  # (span, content)
    coverage_percentage: float

class ChunkReconciliationService:
    """Service for reconciling chunks during failover recovery."""

    @staticmethod
    def reconcile_for_recovery(
        source_id: UUID7,
        failed_chunks: list[CodeChunk],
        backup_chunks: list[CodeChunk],
        content_map: dict[Span, str]  # Span -> original content
    ) -> ReconciliationResult:
        """Reconcile failed chunks using backup chunks.

        Algorithm:
        1. Create SpanGroup from failed chunks
        2. Find backup chunks that intersect with failed spans
        3. Compute coverage and identify gaps
        4. Return reusable chunks and spans needing embedding
        """
        # Extract span group from failed chunks
        failed_spans = SpanGroup.from_chunks(failed_chunks)

        # Find reusable backup chunks
        reusable = []
        for backup_chunk in backup_chunks:
            if backup_chunk.line_range.source_id == source_id:
                # Check if backup chunk overlaps with any failed span
                if failed_spans.contains_span(backup_chunk.line_range):
                    reusable.append(backup_chunk)

        # Compute coverage
        covered_spans = SpanGroup.from_chunks(reusable)
        gap_spans = failed_spans - covered_spans

        # Calculate coverage percentage
        total_lines = sum(s.end - s.start + 1 for s in failed_spans.spans)
        covered_lines = sum(s.end - s.start + 1 for s in covered_spans.spans)
        coverage = (covered_lines / total_lines * 100) if total_lines > 0 else 0.0

        # Extract content for gaps
        gaps_with_content = [
            (span, content_map.get(span, ""))
            for span in gap_spans.spans
        ]

        return ReconciliationResult(
            reusable_chunks=reusable,
            gaps_needing_embedding=gaps_with_content,
            coverage_percentage=coverage
        )

    @staticmethod
    def validate_reconciliation(
        result: ReconciliationResult,
        min_coverage: float = 80.0
    ) -> bool:
        """Validate reconciliation meets coverage threshold."""
        return result.coverage_percentage >= min_coverage
```

#### 3.2 Create Recovery Coordinator

**New File**: `src/codeweaver/engine/failover/recovery.py`

```python
class RecoveryCoordinator:
    """Coordinates recovery from backup to primary provider."""

    def __init__(
        self,
        reconciliation_service: ChunkReconciliationService,
        embedding_service: EmbeddingService,
        vector_store: VectorStoreProvider,
        state_machine: FailoverStateMachine,
    ) -> None:
        self.reconciliation_service = reconciliation_service
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.state_machine = state_machine

    async def recover_from_backup(
        self,
        source_id: UUID7,
        failed_chunks: list[CodeChunk],
        outage_start: datetime,
        outage_end: datetime
    ) -> RecoveryResult:
        """Recover from backup using temporal filtering and reconciliation."""

        # Step 1: Retrieve backup chunks for this source_id
        backup_chunks = await self.vector_store.get_chunks_by_source(
            source_id,
            collection="backup"
        )

        # Step 2: Reconcile to identify reusable chunks
        content_map = await self._build_content_map(source_id)
        reconciliation = self.reconciliation_service.reconcile_for_recovery(
            source_id,
            failed_chunks,
            backup_chunks,
            content_map
        )

        # Step 3: Embed gaps if needed
        newly_embedded = []
        if reconciliation.gaps_needing_embedding:
            gap_contents = [content for _, content in reconciliation.gaps_needing_embedding]
            embeddings = await self.embedding_service.embed_batch(
                gap_contents,
                tier="primary"  # Use primary for recovery
            )
            newly_embedded = embeddings

        # Step 4: Store recovered chunks
        all_recovered = reconciliation.reusable_chunks + newly_embedded
        await self.vector_store.upsert(
            all_recovered,
            collection="primary"
        )

        # Step 5: Validate and update state
        if self.reconciliation_service.validate_reconciliation(reconciliation):
            self.state_machine.handle_event(FailoverEvent.PRIMARY_RESTORED)

        return RecoveryResult(
            total_chunks=len(all_recovered),
            reused_chunks=len(reconciliation.reusable_chunks),
            newly_embedded=len(newly_embedded),
            coverage=reconciliation.coverage_percentage,
            state=self.state_machine.state
        )
```

### Phase 4: DI Integration

#### 4.1 Update Provider Dependencies

**File**: `src/codeweaver/providers/dependencies.py`

```python
from codeweaver.core.di import Container, Scope

def register_failover_providers(container: Container) -> None:
    """Register providers with tier tags for failover."""

    # Primary tier (high-quality, potentially remote)
    container.register(
        EmbeddingProvider,
        VoyageEmbeddingProvider,
        tags={"tier": "primary", "profile": "default"},
        scope=Scope.SINGLETON,
        key="primary_embedding"
    )

    container.register(
        RerankingProvider,
        VoyageRerankingProvider,
        tags={"tier": "primary", "profile": "default"},
        scope=Scope.SINGLETON,
        key="primary_reranking"
    )

    # Backup tier (local, reliable)
    container.register(
        EmbeddingProvider,
        FastEmbedProvider,
        tags={"tier": "backup", "profile": "default"},
        scope=Scope.SINGLETON,
        key="backup_embedding"
    )

    container.register(
        RerankingProvider,
        FastEmbedRerankingProvider,
        tags={"tier": "backup", "profile": "default"},
        scope=Scope.SINGLETON,
        key="backup_reranking"
    )

    # Capability groups (for chunk size resolution)
    container.register(
        EmbeddingCapabilityGroup,
        lambda c: EmbeddingCapabilityGroup(
            embedding=c.resolve(EmbeddingProvider, key="primary_embedding").capabilities,
            reranking=c.resolve(RerankingProvider, key="primary_reranking").capabilities
        ),
        tags={"tier": "primary"},
        scope=Scope.SINGLETON,
        key="primary_capabilities"
    )

    container.register(
        EmbeddingCapabilityGroup,
        lambda c: EmbeddingCapabilityGroup(
            embedding=c.resolve(EmbeddingProvider, key="backup_embedding").capabilities,
            reranking=c.resolve(RerankingProvider, key="backup_reranking").capabilities
        ),
        tags={"tier": "backup"},
        scope=Scope.SINGLETON,
        key="backup_capabilities"
    )

    # Chunk governors
    container.register(
        ChunkGovernor,
        lambda c: ChunkGovernor(
            capabilities=c.resolve(EmbeddingCapabilityGroup, key="primary_capabilities"),
            settings=c.resolve(Settings)
        ),
        tags={"tier": "primary"},
        scope=Scope.SINGLETON,
        key="primary_governor"
    )

    container.register(
        ChunkGovernor,
        lambda c: ChunkGovernor(
            capabilities=c.resolve(EmbeddingCapabilityGroup, key="backup_capabilities"),
            settings=c.resolve(Settings)
        ),
        tags={"tier": "backup"},
        scope=Scope.SINGLETON,
        key="backup_governor"
    )

    # Chunking service with both governors
    container.register(
        ChunkingService,
        lambda c: ChunkingService(
            governor=c.resolve(ChunkGovernor, key="primary_governor"),
            backup_governor=c.resolve(ChunkGovernor, key="backup_governor"),
            tokenizer=c.resolve(Tokenizer),
            settings=c.resolve(ChunkerSettings)
        ),
        scope=Scope.SINGLETON
    )

    # State machine
    container.register(
        FailoverStateMachine,
        lambda c: FailoverStateMachine(
            config=c.resolve(FailoverConfig),
            on_state_change=lambda old, new: logger.info(
                "Failover state: %s → %s", old.value, new.value
            )
        ),
        scope=Scope.SINGLETON
    )

    # Failover-aware embedding provider
    container.register(
        EmbeddingProvider,
        lambda c: FailoverEmbeddingProvider(
            primary=c.resolve(EmbeddingProvider, key="primary_embedding"),
            backup=c.resolve(EmbeddingProvider, key="backup_embedding"),
            state_machine=c.resolve(FailoverStateMachine)
        ),
        scope=Scope.SINGLETON,
        key="failover_embedding"  # This is the one to use
    )
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
**Goal**: Multi-granularity chunking working end-to-end

**Tasks**:
1. ✅ Verify Span operations (already complete)
2. ✅ Verify source_id propagation (already complete)
3. Extend `ChunkingService.chunk_files_dual_granularity()`
4. Update `IndexingService` for dual storage
5. Write unit tests for dual chunking
6. Write integration tests for storage

**Acceptance Criteria**:
- Can create both primary (4K) and backup (512 token) chunks
- Both chunk sets share same source_id
- Both stored in separate collections
- Tests pass with >90% coverage

### Phase 2: State Machine (Week 3-4)
**Goal**: Event-driven failover state management

**Tasks**:
1. Create `FailoverStateMachine` class
2. Implement state transition logic
3. Add circuit breaker with exponential backoff
4. Create `FailoverEmbeddingProvider` wrapper
5. Write state machine unit tests
6. Write integration tests for failover scenarios

**Acceptance Criteria**:
- State machine transitions correctly on events
- Circuit breaker prevents thrashing
- Failover happens within degraded timeout (500ms)
- Recovery requires 5-minute green period
- Tests verify all state transitions

### Phase 3: Reconciliation (Week 5-6)
**Goal**: Span-based chunk recovery

**Tasks**:
1. Create `ChunkReconciliationService`
2. Implement reconciliation algorithm
3. Create `RecoveryCoordinator`
4. Add UUID7 temporal filtering
5. Write reconciliation unit tests
6. Write recovery integration tests

**Acceptance Criteria**:
- Reconciliation correctly identifies reusable chunks
- Gap detection works with Span set operations
- Coverage calculation accurate
- Recovery minimizes re-embedding
- Tests verify reconciliation correctness

### Phase 4: DI Integration (Week 7-8)
**Goal**: Full DI-driven failover system

**Tasks**:
1. Update provider registrations with tags
2. Create capability group bindings
3. Wire failover components via DI
4. Add configuration validation
5. Write end-to-end integration tests
6. Performance testing and optimization

**Acceptance Criteria**:
- All components resolve via DI
- Tag-based provider selection works
- Configuration validates correctly
- End-to-end failover test passes
- Performance overhead <10% in healthy state

---

## Integration Points

### With Existing Systems

#### 1. DI Container (`src/codeweaver/core/di/`)
**Integration**: Tag-based registration for primary/backup separation
**Changes**: Add tags to existing provider registrations
**Testing**: Verify constraint-based resolution works

#### 2. Chunking Pipeline (`src/codeweaver/engine/chunker/`)
**Integration**: Dual-granularity chunk creation
**Changes**: New `ChunkingService` method
**Testing**: Verify both granularities created correctly

#### 3. Vector Stores (`src/codeweaver/providers/vector_stores/`)
**Integration**: Collection namespacing for primary/backup
**Changes**: Update collection naming scheme
**Testing**: Verify isolation between collections

#### 4. Embedding Providers (`src/codeweaver/providers/embedding/`)
**Integration**: Failover wrapper with state machine
**Changes**: New `FailoverEmbeddingProvider` class
**Testing**: Verify timeout and fallback logic

#### 5. Telemetry (`src/codeweaver/common/telemetry/`)
**Integration**: Track failover events and metrics
**Changes**: Add failover event definitions
**Testing**: Verify events logged correctly

### Configuration Schema

**New File**: `src/codeweaver/config/failover.py`

```python
from pydantic import BaseModel, Field

class FailoverSettings(BaseModel):
    """Failover system configuration."""

    # State machine
    enabled: bool = True
    degraded_timeout_ms: int = Field(500, ge=100, le=5000)
    failure_threshold: int = Field(3, ge=1, le=10)
    recovery_window_sec: int = Field(300, ge=60, le=3600)
    circuit_breaker_reset_sec: int = Field(60, ge=10, le=600)

    # Storage
    dual_write_enabled: bool = True
    collection_prefix: str = "codeweaver"

    # Reconciliation
    min_coverage_percentage: float = Field(80.0, ge=0.0, le=100.0)
    enable_temporal_filtering: bool = True

    # Performance
    max_concurrent_embeddings: int = Field(10, ge=1, le=50)
    batch_size: int = Field(32, ge=1, le=128)
```

---

## Testing Strategy

### Unit Tests

#### Chunking Tests
```python
# tests/engine/services/test_chunking_service_dual.py

def test_dual_granularity_same_source_id():
    """Verify both granularities share source_id."""

def test_dual_granularity_respects_token_limits():
    """Verify primary=4K, backup=512 token limits."""

def test_dual_granularity_span_coverage():
    """Verify backup spans cover primary spans."""
```

#### State Machine Tests
```python
# tests/engine/failover/test_state_machine.py

def test_healthy_to_degraded_transition():
    """Verify HEALTHY → DEGRADED on first error."""

def test_degraded_to_backup_only_after_threshold():
    """Verify DEGRADED → BACKUP_ONLY after 3 failures."""

def test_recovery_requires_green_period():
    """Verify RECOVERY → HEALTHY needs 5min green."""
```

#### Reconciliation Tests
```python
# tests/engine/failover/test_reconciliation.py

def test_reconciliation_identifies_reusable_chunks():
    """Verify Span intersection finds reusable chunks."""

def test_reconciliation_computes_gaps():
    """Verify SpanGroup difference finds gaps."""

def test_reconciliation_calculates_coverage():
    """Verify coverage percentage accurate."""
```

### Integration Tests

#### End-to-End Failover
```python
# tests/integration/test_failover_e2e.py

async def test_failover_degradation_and_recovery():
    """Simulate primary failure → degraded → backup → recovery."""

    # 1. Index files in HEALTHY state
    # 2. Simulate primary provider failure
    # 3. Verify degraded mode activates
    # 4. Verify backup provider used
    # 5. Simulate primary restoration
    # 6. Verify recovery reconciliation
    # 7. Verify return to HEALTHY
```

#### Performance Tests
```python
# tests/performance/test_failover_overhead.py

def test_healthy_state_overhead_under_10_percent():
    """Verify dual-write overhead <10% vs single-write."""

def test_degraded_timeout_respected():
    """Verify fast timeout (500ms) in degraded state."""
```

### Manual Testing Scenarios

1. **Primary Provider Outage**
   - Stop primary embedding service
   - Send search query
   - Verify backup used within 500ms
   - Verify no feature degradation

2. **Network Latency**
   - Inject 2s latency in primary provider
   - Verify degraded state activates
   - Verify backup used after timeout

3. **Recovery After Outage**
   - Restore primary provider
   - Verify reconciliation runs
   - Verify backup chunks reused
   - Verify primary collection updated

4. **Vector Store Failure**
   - Stop vector store service
   - Verify writes go to shadow WAL
   - Restore vector store
   - Verify WAL replayed

---

## Risk Mitigation

### Technical Risks

#### 1. Reconciliation Correctness
**Risk**: Span operations produce incorrect coverage
**Mitigation**:
- Extensive unit tests for Span set operations
- Property-based testing with hypothesis library
- Manual validation on known test cases

#### 2. Performance Degradation
**Risk**: Dual-write overhead >10%
**Mitigation**:
- Parallel writes to collections
- Benchmark tests in CI
- Performance budgets enforced

#### 3. State Machine Thrashing
**Risk**: Rapid transitions between states
**Mitigation**:
- Circuit breaker with exponential backoff
- Minimum time in each state (grace periods)
- Telemetry to detect thrashing patterns

#### 4. Data Inconsistency
**Risk**: Primary/backup collections diverge
**Mitigation**:
- Transactional dual-write where possible
- Periodic reconciliation checks
- Shadow WAL for recovery

### Operational Risks

#### 1. Increased Storage
**Risk**: 2x storage for dual collections
**Mitigation**:
- Accept as cost of reliability
- Implement TTL for old backups
- Monitor storage metrics

#### 2. Configuration Complexity
**Risk**: More settings to configure
**Mitigation**:
- Sensible defaults (500ms timeout, 3 failure threshold)
- Validation on startup
- Clear documentation

#### 3. Monitoring Gaps
**Risk**: Failover events not visible
**Mitigation**:
- Comprehensive telemetry events
- State machine transition logging
- Performance dashboards

---

## Success Metrics

### Functional Metrics
- ✅ Zero feature degradation during failover
- ✅ Failover latency <500ms in degraded state
- ✅ Recovery reconciliation >80% chunk reuse
- ✅ State machine transitions follow specification

### Performance Metrics
- ✅ Healthy state overhead <10%
- ✅ Dual-write latency <100ms additional
- ✅ Reconciliation completes in <5s per file
- ✅ Memory overhead <20%

### Reliability Metrics
- ✅ MTTR (mean time to recovery) <5 minutes
- ✅ Zero data loss during failover
- ✅ 99.9% uptime for search queries
- ✅ Circuit breaker prevents >95% of unnecessary retries

---

## Next Steps

1. **Approve Architecture** (this document)
2. **Create Implementation Issues** (GitHub/Linear)
3. **Begin Phase 1**: Multi-granularity chunking
4. **Weekly Progress Reviews**
5. **Alpha 3 Release** with failover system

---

## Appendix A: Open Questions

### Resolved
1. ✅ How to reconcile chunks after outage? → Span set operations
2. ✅ How to determine chunk sizes? → EmbeddingCapabilityGroup
3. ✅ How to track modified files? → UUID7 temporal properties
4. ✅ How to handle context window differences? → Multi-granularity storage

### Remaining
1. Should we implement write-ahead log for remote vector store failures?
   - **Decision needed**: WAL vs dual local/remote stores

2. What's the optimal dual-write strategy?
   - **Options**: Parallel, sequential, fire-and-forget
   - **Recommendation**: Parallel with failure tracking

3. Should backup chunks use sparse embeddings?
   - **Trade-off**: Speed vs storage
   - **Recommendation**: Evaluate in Phase 2

---

## Appendix B: Reference Implementation

See working examples in:
- `src/codeweaver/core/spans.py` - Span set operations
- `src/codeweaver/engine/chunker/base.py` - ChunkGovernor
- `src/codeweaver/providers/dependencies.py` - DI registration
- `tests/core/test_spans.py` - Span operation tests

---

**Document Version**: 1.0
**Last Updated**: 2026-01-18
**Next Review**: After Phase 1 completion
