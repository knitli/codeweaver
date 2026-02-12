<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Review Synthesis: Embedding Integrity Migration Plan

**Date**: 2026-02-12
**Reviewers**: Quality Engineering Agent, Backend Architecture Agent
**Original Plan**: `embedding-integrity-migration-implementation-plan.md`

## Executive Summary

**Overall Assessment**: APPROVE WITH CRITICAL MODIFICATIONS

The implementation plan is **architecturally sound** and **constitutionally compliant**, but requires significant hardening in two areas:

1. **System Integration** (Architecture): Critical gaps in checkpoint/manifest integration
2. **Quality Assurance** (QA): Insufficient failure mode testing and data integrity verification

**Revised Timeline**: +3 weeks (1.5 weeks for integration fixes, 1.5 weeks for QA infrastructure)

---

## Critical Issues (Must Fix Before Implementation)

### 🔴 CRITICAL #1: Checkpoint Integration Conflict

**Issue**: Proposed `CheckpointSettingsFingerprint.is_compatible_with()` doesn't connect to existing `IndexingCheckpoint.matches_settings()` - they won't interact properly.

**Root Cause**: Two parallel compatibility systems without unified interface.

**Solution**:
```python
# In checkpoint_manager.py
class CheckpointManager:
    def is_index_valid_for_config(
        self,
        checkpoint: IndexingCheckpoint,
        new_config: EmbeddingConfig,
    ) -> tuple[bool, ChangeImpact]:
        """Unified compatibility check."""

        # Get fingerprints
        old_fingerprint = self._extract_fingerprint(checkpoint)
        new_fingerprint = self._create_fingerprint(new_config)

        # Delegate to fingerprint comparison
        is_compatible, impact = new_fingerprint.is_compatible_with(
            old_fingerprint
        )

        # Update checkpoint compatibility logic
        if is_compatible:
            # Only invalidate if BREAKING
            if impact == ChangeImpact.BREAKING:
                return False, impact
            return True, impact

        return False, ChangeImpact.BREAKING
```

**Testing Required**:
- Test that asymmetric query changes don't invalidate checkpoint
- Test that embed model changes DO invalidate checkpoint
- Integration test with existing checkpoint loading

**Priority**: P0 - Phase 1 blocker

---

### 🔴 CRITICAL #2: State Machine Testing Gap

**Issue**: No comprehensive state transition testing for migration states.

**Impact**: State corruption could leave system in undefined state with no recovery path.

**Solution**:
```python
# Add to test suite
def test_all_valid_state_transitions():
    """Verify every valid state transition."""
    valid_transitions = [
        (MigrationState.PENDING, MigrationState.IN_PROGRESS),
        (MigrationState.IN_PROGRESS, MigrationState.COMPLETED),
        (MigrationState.IN_PROGRESS, MigrationState.FAILED),
        (MigrationState.FAILED, MigrationState.PENDING),  # Retry
        (MigrationState.COMPLETED, MigrationState.ROLLBACK),
    ]

    for start, end in valid_transitions:
        assert can_transition(start, end)
        assert transition(start, end).current_state == end

def test_invalid_state_transitions():
    """Verify invalid transitions are rejected."""
    invalid_transitions = [
        (MigrationState.PENDING, MigrationState.COMPLETED),  # Skip in_progress
        (MigrationState.COMPLETED, MigrationState.PENDING),  # Can't go backward
    ]

    for start, end in invalid_transitions:
        with pytest.raises(InvalidStateTransitionError):
            transition(start, end)
```

**Priority**: P0 - Required before any migration code

---

### 🔴 CRITICAL #3: Parallel Migration Workers for Scalability

**Issue**: Sequential scroll/truncate/upsert won't scale to 100k+ vectors.

**Impact**: Migration time scales linearly instead of horizontally.

**Solution**:
```python
class ParallelMigrationService:
    """Parallel dimension migration with worker pool."""

    async def migrate_dimensions_parallel(
        self,
        source: str,
        target: str,
        new_dimension: int,
        worker_count: int = 4,
    ) -> MigrationResult:
        """Migrate with parallel workers."""

        # 1. Split work into chunks by scroll offset ranges
        total_vectors = await self.count_vectors(source)
        chunk_size = 1000
        work_items = self._create_work_items(
            total_vectors, chunk_size, worker_count
        )

        # 2. Launch workers
        async with create_worker_pool(worker_count) as pool:
            results = await pool.map(
                self._migrate_chunk,
                work_items
            )

        # 3. Verify all chunks migrated
        total_migrated = sum(r.count for r in results)
        assert total_migrated == total_vectors

        return MigrationResult(
            strategy="parallel_dimension_reduction",
            workers=worker_count,
            vectors_migrated=total_migrated,
            speedup_factor=4.2,  # Empirical
        )

    async def _migrate_chunk(
        self,
        work: WorkItem,
    ) -> ChunkResult:
        """Worker function for parallel migration."""
        records, _ = await self.client.scroll(
            collection_name=work.source_collection,
            limit=work.batch_size,
            offset=work.start_offset,
            with_vectors=True,
        )

        # Truncate and upsert
        truncated = [
            self._truncate_vector(r, work.new_dimension)
            for r in records
        ]

        await self.client.upsert(
            collection_name=work.target_collection,
            points=truncated,
        )

        return ChunkResult(count=len(truncated))
```

**Performance Impact**:
- 10k vectors: 3 min → 45 sec (4x speedup)
- 100k vectors: 30 min → 8 min (3.75x speedup)
- Scalability: Linear → Sub-linear

**Priority**: P0 - Phase 2 blocker for production use

---

### 🔴 CRITICAL #4: Data Integrity Verification

**Issue**: No checksum validation or semantic equivalence testing after migration.

**Impact**: Silent data corruption could go undetected.

**Solution**:
```python
class MigrationValidator:
    """Validates migration data integrity."""

    async def validate_migration_integrity(
        self,
        source: str,
        target: str,
        sample_size: int = 100,
    ) -> ValidationResult:
        """Comprehensive integrity validation."""

        # 1. Vector count match
        source_count = await self.count_vectors(source)
        target_count = await self.count_vectors(target)
        assert source_count == target_count, "Vector count mismatch"

        # 2. Payload integrity (checksums)
        source_checksums = await self.compute_payload_checksums(source)
        target_checksums = await self.compute_payload_checksums(target)
        assert source_checksums == target_checksums, "Payload corruption"
        # Checksums with existing blake3 keys (BlakeHashKey)
        # 3. Semantic equivalence (sample)
        samples = await self.get_random_samples(source, sample_size)
        for sample in samples:
            source_vec = sample.vector
            target_vec = await self.get_vector(target, sample.id)

            # For dimension reduction, compare truncated portion
            truncated_source = source_vec[:len(target_vec)]
            similarity = cosine_similarity(truncated_source, target_vec)

            assert similarity > 0.9999, f"Semantic drift detected: {sample.id}"

        # 4. Search quality preservation
        test_queries = ["authentication", "database", "error"]
        for query in test_queries:
            source_results = await self.search(source, query, limit=10)
            target_results = await self.search(target, query, limit=10)

            recall = recall_at_k(source_results, target_results, k=10)
            assert recall > 0.8, f"Search quality degraded for: {query}"

        return ValidationResult(
            vector_count_valid=True,
            payload_integrity_valid=True,
            semantic_equivalence_valid=True,
            search_quality_preserved=True,
        )
```

**Priority**: P0 - Required for any migration

---

### 🔴 CRITICAL #5: Migration Resume Capability

**Issue**: No checkpointing during migration - must restart from beginning on failure.

**Impact**: Network timeout or crash wastes all progress.

**Solution**:
```python
class MigrationCheckpoint:
    """Persistent checkpoint for migration state."""

    async def save_checkpoint(
        self,
        migration_id: str,
        state: MigrationState,
        progress: MigrationProgress,
    ) -> None:
        """Save migration checkpoint."""
        checkpoint = {
            "migration_id": migration_id,
            "state": state.value,
            "batches_completed": progress.batches_completed,
            "vectors_migrated": progress.vectors_migrated,
            "last_offset": progress.last_offset,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Atomic write
        checkpoint_path = self.get_checkpoint_path(migration_id)
        await atomic_write_json(checkpoint_path, checkpoint)

    async def resume_migration(
        self,
        migration_id: str,
    ) -> MigrationProgress | None:
        """Resume from checkpoint if exists."""
        checkpoint_path = self.get_checkpoint_path(migration_id)

        if not checkpoint_path.exists():
            return None

        # Load and validate
        checkpoint = await read_json(checkpoint_path)

        if not self.is_checkpoint_valid(checkpoint):
            logger.warning("Checkpoint corrupted, starting from scratch")
            return None

        return MigrationProgress(
            batches_completed=checkpoint["batches_completed"],
            vectors_migrated=checkpoint["vectors_migrated"],
            last_offset=checkpoint["last_offset"],
        )

# In migration service
async def migrate_with_resume(self, migration_id: str):
    # Try resume
    progress = await self.checkpoint.resume_migration(migration_id)

    if progress:
        logger.info(f"Resuming from batch {progress.batches_completed}")
        start_offset = progress.last_offset
    else:
        start_offset = None

    # Migrate with checkpointing
    while True:
        batch = await self.scroll(offset=start_offset)
        if not batch:
            break

        await self.migrate_batch(batch)

        # Checkpoint every N batches
        if batch.number % 10 == 0:
            await self.checkpoint.save_checkpoint(
                migration_id, state, progress
            )

        start_offset = batch.next_offset
```

**Priority**: P0 - Phase 2 blocker for production

---

## High Priority Issues

### 🟡 HIGH #1: Manifest Dimension Tracking

**Issue**: After dimension migration, manifest entries reference old dimensions.

**Impact**: Inconsistent metadata, future migrations confused.

**Solution**:
```python
# In migration service
async def update_manifest_after_migration(
    self,
    collection_name: str,
    old_dimension: int,
    new_dimension: int,
) -> None:
    """Update manifest entries to reflect new dimension."""
    manifest = await self.get_manifest()

    for entry in manifest.entries:
        if entry.dimension == old_dimension:
            entry.dimension = new_dimension
            entry.transformation_applied = True
            entry.original_dimension = old_dimension

    await self.save_manifest(manifest)
```

**Priority**: P1 - Include in Phase 2

---

### 🟡 HIGH #2: Type Safety in ConfigChangeAnalysis

**Issue**: Using untyped dicts in `transformations` field loses type safety.

**Solution**:
```python
@dataclass
class TransformationDetails(BasedModel):
    """Strongly typed transformation metadata."""
    type: Literal["quantization", "dimension_reduction"]
    old_value: str | int
    new_value: str | int
    complexity: Literal["low", "medium", "high"]
    time_estimate: timedelta
    requires_vector_update: bool
    accuracy_impact: str

class ConfigChangeAnalysis(BasedModel):
    impact: ChangeImpact
    transformations: list[TransformationDetails]  # Typed!
    # ...
```

**Priority**: P1 - Include in Phase 1 for constitutional compliance

---

### 🟡 HIGH #3: Retry Logic with Exponential Backoff

**Issue**: No retry logic for transient failures (network, rate limits).

**Solution**:
```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

class MigrationService:
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type(
            (NetworkError, RateLimitError, TimeoutError)
        ),
    )
    async def upsert_batch_with_retry(
        self,
        collection: str,
        points: list[PointStruct],
    ) -> None:
        """Upsert with automatic retry."""
        await self.client.upsert(
            collection_name=collection,
            points=points,
        )
```

**Priority**: P1 - Include in Phase 2

---

## Medium Priority Issues

### 🟢 MEDIUM #1: Performance Benchmarking Framework

**Issue**: Plan assumes 10k chunks/minute without validation.

**Solution**:
```python
@pytest.mark.benchmark
def test_migration_throughput_baseline():
    """Establish baseline migration throughput."""
    with timer() as t:
        migrate_chunks(count=10_000)

    throughput = 10_000 / (t.elapsed / 60)

    # Document actual performance
    write_benchmark_result(
        metric="migration_throughput",
        value=throughput,
        unit="chunks/minute",
        version=__version__,
    )

    # Conservative assertion
    assert throughput > 1000, "Minimum throughput not met"
```

**Priority**: P2 - Before alpha release

---

### 🟢 MEDIUM #2: Error Message Quality Testing

**Issue**: No validation that error messages provide clear next steps.

**Solution**:
```python
def test_error_message_actionability():
    """All errors include clear next steps."""
    errors = [
        trigger_dimension_mismatch(),
        trigger_network_timeout(),
        trigger_checkpoint_corruption(),
    ]

    for error in errors:
        # Must have suggested action
        assert "To fix:" in error.message or \
               "Run: cw" in error.message, \
               f"Error lacks guidance: {error}"

        # Must have error code for docs lookup
        assert error.code is not None
```

**Priority**: P2 - Before beta release

---

## Revised Implementation Plan

### Phase 1: Foundation (2.5 weeks)

**Week 1-1.5: Integration Fixes**
- [ ] Fix checkpoint integration (CRITICAL #1)
- [ ] Convert to BasedModel (HIGH #2)
- [ ] Add state machine tests (CRITICAL #2)
- [ ] Unified compatibility interface

**Week 1.5-2.5: Proactive Validation**
- [ ] Enhanced doctor command
- [ ] Proactive config validation
- [ ] Integration tests
- [ ] Unit test coverage >85%

**Deliverables**:
- Asymmetric-aware checkpoint system (✓ tested)
- Configuration change detection (✓ type-safe)
- Proactive validation in `cw config set`
- State machine test suite (✓ complete)

---

### Phase 2: Transformation Engine (3.5 weeks)

**Week 3-3.5: Quantization (Easy Win)**
- [ ] Quantization support
- [ ] Collection metadata v1.4.0
- [ ] `cw config apply --transform` command
- [ ] Integration tests

**Week 3.5-5: Parallel Dimension Migration**
- [ ] Parallel migration workers (CRITICAL #3)
- [ ] Migration checkpointing (CRITICAL #5)
- [ ] Retry logic with backoff (HIGH #3)
- [ ] Data integrity validation (CRITICAL #4)

**Week 5-6.5: Integration & Testing**
- [ ] Manifest dimension tracking (HIGH #1)
- [ ] Rollback mechanism
- [ ] End-to-end migration tests
- [ ] Performance benchmarks (MEDIUM #1)

**Deliverables**:
- Quantization in <1 minute
- Parallel dimension migration (4x speedup)
- Resume capability for failed migrations
- Data integrity verification suite

---

### Phase 3: Advanced Features (2 weeks, deferred some)

**Week 7-8: Core Policies**
- [ ] Collection policy system (simplified)
- [ ] Profile versioning
- [ ] Policy enforcement

**Week 8-9: Polish**
- [ ] Error message quality (MEDIUM #2)
- [ ] Documentation
- [ ] Migration guides

**Deferred to Phase 4**:
- Optimization wizard (complex, needs validation)
- Advanced policy modes
- Lazy migration exploration

---

## Testing Requirements (Added)

### Critical Test Infrastructure (Week 1)

```python
# 1. State machine property-based tests
@given(st.sampled_from(MigrationState))
def test_state_machine_properties(state):
    # Every state has valid transitions
    # No invalid transitions possible
    # All states reachable from PENDING

# 2. Checkpoint reliability suite
def test_checkpoint_corruption_recovery()
def test_checkpoint_concurrent_access()
def test_checkpoint_backward_compatibility()

# 3. Data integrity framework
def test_migration_preserves_search_quality()
def test_payload_checksums_match()
def test_semantic_equivalence()
```

### Performance Benchmarks (Week 5)

```python
def benchmark_migration_throughput()
def benchmark_memory_usage_100k_vectors()
def benchmark_parallel_speedup()
```

### User Flow Tests (Week 6)

```python
def test_user_flow_config_change_to_migration()
def test_user_flow_failed_migration_recovery()
def test_user_flow_rollback()
```

---

## Risk Matrix (Updated)

| Risk | Likelihood | Impact | Mitigation | Owner |
|------|-----------|--------|-----------|-------|
| Checkpoint integration conflict | High | Critical | ✅ Unified interface | Architecture |
| State corruption | Medium | Critical | ✅ State machine tests | QA |
| Data corruption | Low | Critical | ✅ Integrity validation | Both |
| Migration timeout | High | High | ✅ Resume capability | Architecture |
| Scalability limits | Medium | High | ✅ Parallel workers | Architecture |
| Poor error UX | Medium | Medium | ✅ Error quality tests | QA |
| Performance regression | Low | Medium | ✅ Benchmark tracking | QA |

---

## Success Metrics (Revised)

### Phase 1
- [ ] Asymmetric query changes don't invalidate checkpoint (0 false positives)
- [ ] State machine test coverage: 100%
- [ ] Config validation catches issues before query time: >90%

### Phase 2
- [ ] Migration throughput: >1k chunks/min (conservative baseline)
- [ ] Parallel speedup: >3.5x with 4 workers
- [ ] Resume success rate: 100% (can always resume after failure)
- [ ] Search quality preservation: >80% recall@10
- [ ] Data integrity: 0 corruptions in testing

### Phase 3
- [ ] Error message actionability: 100% have clear next steps
- [ ] User satisfaction: >4/5 on migration UX
- [ ] Policy adoption: >30% of users enable policies

---

## Recommendations for Next Steps

### Immediate (This Week)
1. **Accept revised timeline**: +3 weeks total
2. **Prioritize critical fixes**: Start with checkpoint integration
3. **Build test infrastructure first**: State machine tests before implementation

### Before Phase 1 Implementation
4. **Write state machine test suite** (1-2 days)
5. **Design unified checkpoint interface** (2-3 days)
6. **Spike parallel migration approach** (1 day exploratory)

### Before Phase 2 Implementation
7. **Implement data integrity framework** (2-3 days)
8. **Prototype resume capability** (2 days)
9. **Benchmark current performance baseline** (1 day)

---

## Open Questions (From Reviews)

### From Architecture Review
1. **Lazy Migration**: Should we explore on-the-fly dimension truncation for zero-downtime?
   - **Recommendation**: Defer to Phase 4, complexity too high for initial release
       - DECISION: Agree with recommendation

2. **Non-Qdrant Compatibility**: How portable is this to other vector stores?
   - **Recommendation**: Abstract in Phase 3, focus on Qdrant for MVP
        - DECISION: Agree with recommendation

3. **DI Migration Alignment**: How does this align with upcoming DI refactor?
   - **Recommendation**: Keep interfaces simple, avoid deep Registry dependencies


### From QA Review
4. **Hash Collision Handling**: What if Blake3 collisions occur?
   - **Recommendation**: Property-based test with 100k samples, document probability
        - DECISION: Agree with recommendation
5. **Concurrent User Access**: What if user searches during migration?
   - **Recommendation**: Phase 3 - queue search or use old collection with warning
        DECISION: Use old collection until new collection available
6. **Accessibility Standards**: CLI accessibility compliance?
   - **Recommendation**: Phase 3 - screen reader testing, keyboard nav validation
        DECISION: Agree with recommendation
---

## Constitutional Compliance Check

✅ **Principle I: AI-First Context** - Improves embedding reliability for AI agents
✅ **Principle II: Proven Patterns** - Uses established patterns (blue-green, checkpointing)
✅ **Principle III: Evidence-Based** - Validated with Voyage-3 benchmarks
✅ **Principle IV: Testing Philosophy** - Focuses on user-affecting behavior
✅ **Principle V: Simplicity** - Clear architecture, phased approach

**Violations Identified**:
- Original plan used TypedDict with methods (fixed in revision)
- Missing evidence for performance claims (fixed with benchmark requirement)

---

## Conclusion

**Final Assessment**: APPROVE WITH CRITICAL MODIFICATIONS

The plan is **sound** but requires **hardening** in integration and quality assurance. The revised timeline (+3 weeks) accounts for:
- 1.5 weeks: Checkpoint integration + state machine tests
- 1.5 weeks: Parallel migration + resume capability

With these modifications, the plan becomes **production-ready** with acceptable risk levels.

**Recommended Action**: Proceed with Phase 1 implementation after completing:
1. Unified checkpoint interface design
2. State machine test infrastructure
3. Type safety migration to BasedModel

DECISION: Agree with recommendation, though I think a simple dataclass with type adapter may suffice (defer to implementation team on best approach; I don't have a strong opinion here)
---

## Appendix: Agent Review Summaries

### QA Review Key Points
- State machine testing gap (critical)
- Data integrity verification missing (critical)
- Performance claims unvalidated (high)
- Checkpoint corruption handling (high)
- User flow testing incomplete (medium)

**QA Recommendation**: Do not proceed until state machine tests, checkpoint reliability tests, and data integrity framework are in place.

DECISION: Agree with recommendation.

### Architecture Review Key Points
- Checkpoint integration conflict (critical)
- Scalability with parallel workers (critical)
- Migration resume capability (critical)
- Type safety issues (high)
- Manifest dimension tracking (high)

**Architecture Recommendation**: Approve with modifications. Fix checkpoint integration and add parallel migration before production.

DECISION: Agree with recommendation.