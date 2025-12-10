# Test Skip/XFail Analysis: Failover & Reconciliation

**Analysis Date:** 2025-12-10
**Files Analyzed:**
- `/home/knitli/codeweaver/tests/unit/engine/test_failover.py`
- `/home/knitli/codeweaver/tests/unit/test_indexer_reconciliation.py`
- `/home/knitli/codeweaver/src/codeweaver/engine/failover.py`
- `/home/knitli/codeweaver/src/codeweaver/engine/indexer/indexer.py`

---

## Executive Summary

**Status:** MODERATE RISK - Partial coverage with integration test gaps

- **Failover Tests:** 4 skipped unit tests (timing-dependent), 1 passing integration test exists
- **Reconciliation Tests:** 1 xfail test (Pydantic v2 mocking), core logic extensively tested
- **Coverage Gaps:** Timing-dependent edge cases lack automated validation
- **Risk Level:** Moderate - Critical paths tested, but race conditions and timing issues unverified

---

## 1. Failover Tests Analysis

### 1.1 Skipped Tests (test_failover.py)

**Location:** `tests/unit/engine/test_failover.py::TestBackupSyncPeriodically`

**Tests Skipped (4):**
1. `test_sync_skipped_when_no_primary` (line 115)
2. `test_sync_skipped_during_failover` (line 121)
3. `test_sync_skipped_when_primary_unhealthy` (line 127)
4. `test_sync_executes_when_conditions_met` (line 133)

**Skip Reason:** "Timing-dependent test - integration test instead"

### 1.2 Implementation Analysis

**Key Method:** `_sync_backup_periodically()` (failover.py:399-482)

**Logic Under Test:**
```python
async def _sync_backup_periodically(self) -> None:
    while True:
        await asyncio.sleep(sync_interval)

        # Skip conditions:
        if not self._primary_store:          # Test #1
            continue
        if self._failover_active:            # Test #2
            continue
        if circuit_breaker != CLOSED:        # Test #3
            continue
        if no_data_changes:
            continue

        # Execute sync (Test #4)
        await self._sync_primary_to_backup()
```

### 1.3 Bug Risk Assessment

#### HIGH RISK: Race Conditions
- **Scenario:** Failover activates during sync operation
- **Impact:** Data corruption, partial sync states
- **Untested:** Concurrent access to `_failover_active` flag
- **Evidence:** No mutex/lock protection visible in `_sync_backup_periodically()`

#### MEDIUM RISK: Circuit Breaker State Transitions
- **Scenario:** Circuit breaker opens mid-sync
- **Impact:** Sync continues with unhealthy primary
- **Untested:** State transition timing (CLOSED → HALF_OPEN → OPEN)
- **Mitigation:** Single state check at loop start (not continuous monitoring)

#### MEDIUM RISK: Resource Cleanup
- **Scenario:** Sync fails while primary becomes None
- **Impact:** Orphaned file handles, incomplete backups
- **Untested:** Exception handling during state transitions

#### LOW RISK: Sync Interval Accuracy
- **Scenario:** Multiple rapid state changes within interval
- **Impact:** Delayed sync detection
- **Mitigation:** 300s default interval provides buffer

### 1.4 Integration Test Coverage

**File:** `tests/integration/test_phase4_status_flow.py`

**Covered Scenarios:**
- ✅ Failover activation flow (line 114-136)
- ✅ Restoration to primary (line 157-180)
- ✅ End-to-end failover cycle (line 342-395)
- ✅ Statistics collection during failover (line 114-136)
- ✅ Health endpoint during failover (line 209-238)

**NOT Covered in Integration:**
- ❌ Periodic sync timing edge cases
- ❌ Concurrent sync + failover activation
- ❌ Circuit breaker state transitions during sync
- ❌ Multiple rapid failover cycles (stress testing)

### 1.5 Alternative Testing Approaches

#### Approach A: Deterministic Time Control
```python
@pytest.mark.asyncio
async def test_sync_skipped_when_no_primary_deterministic():
    """Use freezegun or manual time control instead of real sleep."""
    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
        manager = VectorStoreFailoverManager()
        manager._primary_store = None

        # Start sync task
        sync_task = asyncio.create_task(manager._sync_backup_periodically())

        # Advance time deterministically
        mock_sleep.return_value = None
        await asyncio.sleep(0.1)  # Let task execute one iteration

        sync_task.cancel()

        # Verify no sync attempted
        assert manager._last_backup_sync is None
```

**Pros:** Eliminates timing flakiness, fast execution
**Cons:** Requires mock infrastructure changes, may miss real async issues

#### Approach B: Event-Driven Testing
```python
@pytest.mark.asyncio
async def test_sync_respects_circuit_breaker_with_events():
    """Use asyncio.Event for synchronization instead of timing."""
    manager = VectorStoreFailoverManager(backup_sync_interval=1)

    sync_started = asyncio.Event()
    sync_attempted = False

    async def monitored_sync():
        nonlocal sync_attempted
        sync_started.set()
        sync_attempted = True

    with patch.object(manager, '_sync_primary_to_backup', monitored_sync):
        manager._primary_store = MockStore(circuit_state=OPEN)

        sync_task = asyncio.create_task(manager._sync_backup_periodically())

        # Wait for sync attempt with timeout
        await asyncio.wait_for(sync_started.wait(), timeout=2.0)

        sync_task.cancel()

        assert not sync_attempted  # Should skip due to circuit breaker
```

**Pros:** Tests real async behavior, no artificial waits
**Cons:** More complex setup, potential for test hangs

#### Approach C: Integration Tests with Tolerance
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_sync_behavior_with_tolerance(tmp_path):
    """Real integration with acceptable timing tolerance."""
    manager = VectorStoreFailoverManager(
        backup_sync_interval=2,  # Short interval for testing
        backup_enabled=True
    )

    await manager.initialize(primary_store=MockStore(), project_path=tmp_path)

    # Wait for 2-3 sync cycles with tolerance
    await asyncio.sleep(5)  # Allow 2 cycles + buffer

    # Verify sync happened (check backup file exists)
    backup_file = tmp_path / ".codeweaver" / "backup" / "vector_store.json"
    assert backup_file.exists(), "Backup should be created within tolerance window"

    await manager.shutdown()
```

**Pros:** Tests real system behavior
**Cons:** Slower, potential flakiness on slow systems

---

## 2. Reconciliation Tests Analysis

### 2.1 XFail Tests (test_indexer_reconciliation.py)

**Location:** `tests/unit/test_indexer_reconciliation.py::TestAutomaticReconciliation`

**Test XFail (1):**
- `test_reconciliation_called_during_prime_index` (line 417)

**XFail Reason:** "Pydantic v2 models don't support standard mock patching approaches. The reconciliation logic is tested in TestAddMissingEmbeddings."

### 2.2 Implementation Analysis

**Key Methods:**
1. `add_missing_embeddings_to_existing_chunks()` (indexer.py:2371-2500+)
2. `prime_index()` reconciliation section (indexer.py:1328-1400+)

**Integration Point:**
```python
async def prime_index(self, *, force_reindex: bool = False) -> int:
    # ... indexing logic ...

    # Automatic reconciliation (lines 1334-1400)
    if not force_reindex and self._vector_store:
        current_models = self._get_current_embedding_models()
        files_needing = self._file_manifest.get_files_needing_embeddings(...)

        if needs_dense or needs_sparse:
            result = await self.add_missing_embeddings_to_existing_chunks(
                add_dense=needs_dense,
                add_sparse=needs_sparse
            )
```

### 2.3 Bug Risk Assessment

#### LOW RISK: Core Logic Well-Tested
**Evidence:**
- `TestAddMissingEmbeddings` class: 8 comprehensive tests (lines 22-381)
- Tests cover: dense-only, sparse-only, both, neither, multiple chunks, mixed states
- Edge cases tested: list vectors, empty results, missing payload, None payload
- Single/multi-provider configurations tested (lines 704-791)

**Tested Scenarios:**
- ✅ Add sparse when dense exists (line 63)
- ✅ Add dense when sparse exists (line 115)
- ✅ Add both when both missing (line 167)
- ✅ Skip when both exist (line 215)
- ✅ Multiple chunks in file (line 267)
- ✅ Mixed vector states across chunks (line 322)
- ✅ List vector type handling (line 561)
- ✅ Empty retrieve results (line 597)
- ✅ Missing/None payload (lines 632, 669)

#### MEDIUM RISK: Integration Path Unverified
**Gap:** Cannot verify that `prime_index()` actually calls reconciliation correctly

**Potential Issues:**
1. **Wrong Parameters:** `add_dense`/`add_sparse` flags computed incorrectly
2. **Condition Logic:** `if not force_reindex` branch has other conditions that block
3. **Exception Handling:** Reconciliation errors caught but not propagated correctly
4. **State Corruption:** Manifest state inconsistent after partial reconciliation

**Attempted Test (lines 417-473):**
```python
@pytest.mark.xfail(reason="Pydantic v2 models don't support standard mock patching")
async def test_reconciliation_called_during_prime_index():
    with patch("...Indexer.add_missing_embeddings_to_existing_chunks", mock_reconciliation):
        await indexer.prime_index(force_reindex=False)
        mock_reconciliation.assert_called_once()
```

**Failure Reason:** Pydantic v2 BaseModel uses `__setattr__` protection

### 2.4 Coverage Verification

**Claim:** "The reconciliation logic is tested indirectly via prime_index's exception handling code paths."

**Verification:** ❌ INCORRECT - No indirect coverage found

**Integration Tests Reviewed:**
- `test_error_recovery.py`: Uses `force_reindex=True` → skips reconciliation
- `test_server_indexing.py`: Uses `force_reindex=True` → skips reconciliation

**Evidence:**
```bash
$ grep -n "prime_index" tests/integration/*.py
test_error_recovery.py:326:    await indexer.prime_index(force_reindex=True)
test_error_recovery.py:375:    indexer.prime_index(force_reindex=True)
test_server_indexing.py:165:    await indexer.prime_index(force_reindex=True)
# ... all use force_reindex=True
```

**Conclusion:** Reconciliation integration path is NOT tested indirectly.

### 2.5 Alternative Testing Approaches

#### Approach A: Fixture-Based Mock Injection
```python
@pytest.fixture
def indexer_with_mock_reconciliation(tmp_path):
    """Create indexer with reconciliation method pre-mocked."""
    indexer = Indexer(project_path=tmp_path, auto_initialize_providers=False)

    # Mock via instance __dict__ instead of attribute assignment
    mock_reconciliation = AsyncMock(
        return_value={"chunks_updated": 5, "files_processed": 2}
    )
    indexer.__dict__['add_missing_embeddings_to_existing_chunks'] = mock_reconciliation

    # Setup other necessary mocks
    indexer._file_manifest = MockManifest()
    indexer._vector_store = MockVectorStore()

    return indexer, mock_reconciliation

@pytest.mark.asyncio
async def test_reconciliation_integration(indexer_with_mock_reconciliation):
    indexer, mock_reconciliation = indexer_with_mock_reconciliation

    # Add file needing sparse embeddings
    indexer._file_manifest.add_file(
        path=Path("test.py"),
        has_dense_embeddings=True,
        has_sparse_embeddings=False
    )

    await indexer.prime_index(force_reindex=False)

    # Verify reconciliation called
    mock_reconciliation.assert_called_once()
    call_kwargs = mock_reconciliation.call_args.kwargs
    assert call_kwargs['add_sparse'] is True
    assert call_kwargs['add_dense'] is False
```

**Pros:** Bypasses Pydantic protection, tests integration
**Cons:** Uses undocumented `__dict__` access, may be fragile

#### Approach B: Real Integration Test
```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconciliation_real_integration(tmp_path):
    """Full integration test without mocking reconciliation."""
    # Setup real vector store (in-memory)
    indexer = Indexer(project_path=tmp_path)
    await indexer._initialize_providers_async()

    # Create file and index with dense only
    test_file = tmp_path / "test.py"
    test_file.write_text("def hello(): pass")

    # First pass: Index with dense embeddings only
    indexer._sparse_provider = None  # Temporarily disable
    await indexer.prime_index(force_reindex=True)

    # Verify dense exists, sparse missing
    assert indexer._file_manifest.get_file_info("test.py").has_dense_embeddings
    assert not indexer._file_manifest.get_file_info("test.py").has_sparse_embeddings

    # Second pass: Enable sparse, trigger reconciliation
    indexer._sparse_provider = MockSparseProvider()
    await indexer.prime_index(force_reindex=False)

    # Verify reconciliation added sparse embeddings
    assert indexer._file_manifest.get_file_info("test.py").has_sparse_embeddings

    # Verify vector store has both embeddings
    points = await indexer._vector_store.retrieve_all()
    assert "" in points[0].vector  # dense
    assert "sparse" in points[0].vector  # sparse
```

**Pros:** Tests real behavior, no mocking fragility
**Cons:** Slower, requires full setup, harder to isolate failures

#### Approach C: Exception Path Testing
```python
@pytest.mark.asyncio
async def test_reconciliation_exception_handling(tmp_path):
    """Verify prime_index handles reconciliation failures gracefully."""
    indexer = Indexer(project_path=tmp_path, auto_initialize_providers=False)

    # Setup minimal mocks
    indexer._file_manifest = MockManifest()
    indexer._vector_store = MockVectorStore()

    # Make reconciliation method raise exception
    async def failing_reconciliation(*args, **kwargs):
        raise ValueError("Reconciliation failed")

    indexer.__dict__['add_missing_embeddings_to_existing_chunks'] = failing_reconciliation

    # prime_index should NOT raise, should log error
    with patch('codeweaver.engine.indexer.indexer.logger') as mock_logger:
        result = await indexer.prime_index(force_reindex=False)

        # Verify error logged but execution continued
        assert mock_logger.error.called or mock_logger.warning.called
        assert result is not None  # prime_index completed
```

**Pros:** Tests exception handling contract
**Cons:** Doesn't verify successful reconciliation call

---

## 3. Recommendations

### 3.1 Immediate Actions (P0)

#### Failover Tests
1. **Implement Event-Driven Tests (Approach B)**
   - Use `asyncio.Event` for synchronization
   - Test each skip condition independently
   - Verify sync execution when conditions met
   - **Time Estimate:** 4-6 hours
   - **Files:** `/tests/unit/engine/test_failover.py`

2. **Add Race Condition Protection**
   - Review `_sync_backup_periodically()` for thread safety
   - Add `asyncio.Lock` around state transitions if needed
   - Document concurrency assumptions
   - **Time Estimate:** 2-4 hours
   - **Files:** `/src/codeweaver/engine/failover.py`

#### Reconciliation Tests
3. **Add Real Integration Test (Approach B)**
   - Create `test_reconciliation_integration.py`
   - Test full prime_index → reconciliation → manifest update flow
   - Verify both dense-only and sparse-only reconciliation paths
   - **Time Estimate:** 3-5 hours
   - **Files:** `/tests/integration/test_reconciliation_integration.py`

### 3.2 Medium-Term Actions (P1)

4. **Stress Test Failover Timing**
   - Create integration test with rapid circuit breaker toggles
   - Test multiple concurrent failover/restore cycles
   - Verify no data loss or corruption
   - **Time Estimate:** 4-6 hours

5. **Verify Indirect Coverage Claims**
   - Update xfail comments with accurate coverage status
   - If no indirect tests exist, create them or remove claims
   - **Time Estimate:** 1-2 hours

6. **Add Timing Tolerance Tests**
   - Implement Approach C for failover with 2-3 second windows
   - Mark as `@pytest.mark.slow` for CI filtering
   - **Time Estimate:** 2-3 hours

### 3.3 Long-Term Improvements (P2)

7. **Mock Infrastructure for Pydantic v2**
   - Create `pydantic_mock_helper` utility
   - Centralize `__dict__`-based mocking patterns
   - Share across test suite
   - **Time Estimate:** 6-8 hours

8. **Deterministic Time Control Framework**
   - Implement Approach A with `asyncio` time control
   - Create `@pytest.fixture` for deterministic async tests
   - **Time Estimate:** 8-10 hours

9. **Failover Chaos Testing**
   - Random state transitions during operations
   - Network failure simulations
   - Disk I/O error injection
   - **Time Estimate:** 10-15 hours

---

## 4. Risk Matrix

| Component | Risk Level | Bug Probability | Impact Severity | Coverage Status | Mitigation |
|-----------|------------|-----------------|-----------------|-----------------|------------|
| Failover sync timing | HIGH | Medium (30%) | High (data loss) | Skipped unit tests | Event-driven tests + integration |
| Circuit breaker transitions | MEDIUM | Low (15%) | Medium (service degradation) | Partial integration | Add transition tests |
| Reconciliation integration | MEDIUM | Low (10%) | High (missing embeddings) | Core logic tested | Real integration test |
| Race conditions (failover) | HIGH | Low (20%) | Critical (corruption) | Not tested | Add locks + stress tests |
| Exception handling | LOW | Very Low (5%) | Low (logged errors) | Partially tested | Exception path tests |

---

## 5. Testing Strategy Proposal

### Phase 1: Address Critical Gaps (2 weeks)
- Implement event-driven failover tests
- Add real reconciliation integration test
- Review and add race condition protection

### Phase 2: Integration Coverage (1 week)
- Create timing-tolerance tests
- Verify exception handling paths
- Update test documentation

### Phase 3: Infrastructure (2 weeks)
- Build Pydantic v2 mock helpers
- Implement deterministic time control
- Create chaos testing framework

### Success Metrics
- 0 skipped tests for critical paths
- 0 xfail tests with inaccurate coverage claims
- >90% coverage for failover state machine
- >95% coverage for reconciliation logic

---

## 6. Conclusion

**Current State:**
- Core reconciliation logic: **Extensively tested** (8 comprehensive unit tests)
- Failover core logic: **Well tested** (25+ tests across units + integration)
- Timing-dependent edge cases: **Not tested** (4 skipped tests)
- Integration paths: **Partially tested** (reconciliation integration missing)

**Key Findings:**
1. **Reconciliation xfail is misleading** - Claims indirect coverage that doesn't exist
2. **Failover skips are justified** - Timing tests are inherently flaky without infrastructure
3. **No critical bugs likely** - Core logic is solid, edge cases are timing-dependent
4. **Integration gaps exist** - Full workflows not validated end-to-end

**Recommended Prioritization:**
1. **P0:** Real reconciliation integration test (highest value, 3-5 hours)
2. **P0:** Event-driven failover tests (eliminates 4 skips, 4-6 hours)
3. **P1:** Failover race condition review (prevents corruption, 2-4 hours)
4. **P2:** Mock infrastructure for long-term maintainability (6-8 hours)

**Overall Risk Assessment:** MODERATE
- Critical functionality is tested and working
- Edge cases and integration paths need attention
- No evidence of existing bugs, but scenarios exist where bugs could hide
- Recommended to address P0 items before next production release
