<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Reconciliation Test Coverage Analysis & Fix Plan

## Executive Summary

**Current State**: 4 unit tests marked `xfail` due to Pydantic v2 mocking incompatibility
**Root Cause**: Tests attempt to patch methods on Pydantic BaseModel instances, which doesn't work reliably in Pydantic v2
**Coverage Gap**: Integration between `prime_index()` and reconciliation needs testing
**Recommendation**: Refactor tests to integration tests OR redesign mocking strategy

---

## Test Inventory

### ✅ Passing Tests (Excellent Coverage)

#### TestAddMissingEmbeddings (Unit Tests)
**Location**: `tests/unit/test_indexer_reconciliation.py:22-381`
**Status**: All passing ✓
**Coverage**:
1. `test_only_adds_sparse_when_dense_exists` - Validates selective sparse embedding generation
2. `test_only_adds_dense_when_sparse_exists` - Validates selective dense embedding generation
3. `test_adds_both_when_both_missing` - Validates dual embedding generation
4. `test_skips_when_both_exist` - Validates skip logic when complete
5. `test_handles_multiple_chunks_in_file` - Validates multi-chunk processing
6. `test_handles_mixed_vector_states` - Validates mixed state reconciliation

**What They Test**:
- Direct calls to `add_missing_embeddings_to_existing_chunks()`
- All major code paths within the reconciliation method
- Edge cases for vector detection and embedding generation
- Manifest updates after successful reconciliation

**Mocking Strategy**:
- Mock at the provider level (embedding providers, vector store)
- Direct instantiation of `Indexer` with `auto_initialize_providers=False`
- Works perfectly because no Pydantic instance method patching required

#### TestEdgeCases (Unit Tests)
**Location**: `tests/unit/test_indexer_reconciliation.py:520-791`
**Status**: All passing ✓
**Coverage**:
1. `test_handles_list_vector_type` - Non-dict vector representations
2. `test_handles_empty_retrieve_results` - Empty vector store returns
3. `test_handles_missing_payload_text` - Missing payload data
4. `test_handles_none_payload` - Null payload handling
5. `test_single_dense_provider_only` - Dense-only configuration
6. `test_single_sparse_provider_only` - Sparse-only configuration

**What They Test**:
- Robustness against various vector store response formats
- Graceful degradation with missing/malformed data
- Single-provider configurations

#### Integration Tests
**Location**: `tests/integration/test_reconciliation_integration.py`
**Status**: All passing ✓
**Coverage**:
1. `test_prime_index_reconciliation_without_force_reindex` - Full reconciliation workflow
2. `test_reconciliation_with_add_dense_flag` - Dense embedding addition
3. `test_reconciliation_with_add_sparse_flag` - Sparse embedding addition
4. `test_reconciliation_skipped_when_no_files_need_embeddings` - Skip logic

**What They Test**:
- Real Qdrant vector store integration
- End-to-end reconciliation through `prime_index()`
- Actual provider initialization and embedding generation
- Manifest state changes across reconciliation

**Mocking Strategy**:
- Use real Qdrant (via qdrant_test_manager)
- Mock at embedding provider level only
- Track method calls by wrapping, not patching

---

### ❌ Failing Tests (xfail)

#### TestAutomaticReconciliation
**Location**: `tests/unit/test_indexer_reconciliation.py:383-518`
**Status**: 1 test marked xfail

##### Test 1: test_reconciliation_called_during_prime_index
**Lines**: 417-474
**Goal**: Verify reconciliation is called during `prime_index()` when `force_reindex=False`
**Failure Reason**: "Pydantic v2 models don't support standard mock patching approaches"

**What It Tries to Do**:
```python
with patch("codeweaver.engine.indexer.indexer.Indexer._initialize_providers_async", AsyncMock()),
     patch("codeweaver.engine.indexer.indexer.Indexer._perform_batch_indexing_async", AsyncMock()),
     patch("codeweaver.engine.indexer.indexer.Indexer._get_current_embedding_models", MagicMock(...)),
     patch("codeweaver.engine.indexer.indexer.Indexer.add_missing_embeddings_to_existing_chunks", mock_reconciliation):
    await indexer.prime_index(force_reindex=False)
    mock_reconciliation.assert_called_once()
```

**Why It Fails**:
- Pydantic v2 BaseModel instances don't support `patch.object()` reliably
- Class-level patching (`patch("path.to.Class.method")`) conflicts with Pydantic's descriptor system
- Method assignment directly on instances is blocked by Pydantic's `__setattr__` validation

#### TestReconciliationExceptionHandling
**Location**: `tests/unit/test_indexer_reconciliation.py:794-989`
**Status**: 3 tests marked xfail

##### Test 2: test_prime_index_handles_provider_error
**Lines**: 829-879
**Goal**: Verify `ProviderError` during reconciliation is caught and logged
**Same patching issue as Test 1**

##### Test 3: test_prime_index_handles_indexing_error
**Lines**: 888-935
**Goal**: Verify `IndexingError` during reconciliation is caught and logged
**Same patching issue as Test 1**

##### Test 4: test_prime_index_handles_connection_error
**Lines**: 944-989
**Goal**: Verify `ConnectionError` during reconciliation is caught and logged
**Same patching issue as Test 1**

**Common Pattern**:
All three exception tests try to:
1. Mock `add_missing_embeddings_to_existing_chunks` to raise specific exceptions
2. Verify `prime_index()` handles errors gracefully
3. Check that reconciliation was called despite failure

**Why They All Fail**: Same Pydantic v2 patching incompatibility

---

## Root Cause Analysis

### Pydantic v2 Changes

**Pydantic v1 → v2 Breaking Change**:
```python
# Pydantic v1: This worked
indexer = Indexer(...)
indexer.some_method = MagicMock()  # ✓ Worked

# Pydantic v2: This fails
indexer = Indexer(...)
indexer.some_method = MagicMock()  # ✗ ValidationError or ignored
```

**Technical Explanation**:
- Pydantic v2 uses Rust-based core (`pydantic-core`)
- Model attributes are validated through descriptors
- `__setattr__` is heavily customized for field validation
- Methods are not "fields" but Pydantic's validation still interferes
- Class-level patching creates proxy objects that confuse Pydantic's MRO

**Why Integration Tests Work**:
- They don't patch Indexer methods at all
- They mock at the provider level (before Pydantic gets involved)
- They track calls by wrapping methods, not replacing them

---

## Coverage Gap Analysis

### What's Actually Untested

#### 1. Reconciliation Call Path in prime_index()
**Code Location**: `indexer.py:1334-1400`

```python
if not force_reindex and self._vector_store and (self._embedding_provider or self._sparse_provider):
    try:
        # ... reconciliation logic ...
        reconciliation_result = await self.add_missing_embeddings_to_existing_chunks(
            add_dense=needs_dense, add_sparse=needs_sparse
        )
    except (ProviderError, IndexingError) as e:
        logger.warning(...)  # Error handling
    except (ConnectionError, TimeoutError, OSError) as e:
        logger.warning(...)  # Error handling
```

**Current Coverage**:
- ✓ `add_missing_embeddings_to_existing_chunks()` itself is fully tested
- ✓ Integration test verifies reconciliation runs during `prime_index()`
- ✗ Exception handling paths are not unit tested
- ✗ Conditional logic (when to call reconciliation) is not unit tested

#### 2. Exception Handling Verification
**Scenarios**:
- ProviderError during reconciliation → logged, prime_index continues
- IndexingError during reconciliation → logged, prime_index continues
- ConnectionError during reconciliation → logged, prime_index continues
- All other exceptions → should they crash or be caught?

**Current Coverage**:
- ✗ No unit tests verify exception handling
- ? Integration tests may indirectly cover this (not verified)
- ✗ Error message formatting and logging is not tested

#### 3. Reconciliation Skipping Logic
**Code**: `if not force_reindex and self._vector_store and (...)`

**Current Coverage**:
- ✓ Integration test verifies skipping when `force_reindex=True`
- ✗ Unit test verification of conditional logic is missing

---

## Testing Strategy Options

### Option 1: Convert to Integration Tests ✅ RECOMMENDED

**Approach**: Move all xfail tests to integration test suite

**Pros**:
- Matches the pattern that's already working
- Tests real behavior, not mocked behavior
- No Pydantic patching issues
- Tests the actual code path users will exercise

**Cons**:
- Slower test execution (requires Qdrant)
- More complex test setup
- Harder to test edge cases

**Implementation**:
```python
# tests/integration/test_reconciliation_integration.py

@pytest.mark.integration
async def test_reconciliation_handles_provider_error(qdrant_test_manager, tmp_path):
    """Verify ProviderError during reconciliation is handled gracefully."""
    # Setup: Create indexer with real Qdrant
    # Mock embedding provider to raise ProviderError
    # Call prime_index(force_reindex=False)
    # Verify: prime_index completes without crashing
    # Verify: Error is logged (use caplog)
```

**Effort**: Low (copy existing integration test pattern)
**Reliability**: High (no patching issues)

---

### Option 2: Redesign Mocking Strategy 🔧 MODERATE COMPLEXITY

**Approach**: Use Pydantic-compatible mocking techniques

**Technique 1: Dependency Injection**
```python
# Refactor Indexer to accept reconciliation handler
class Indexer(BasedModel):
    _reconciliation_handler: Callable = PrivateAttr(default=None)

    async def prime_index(self, ...):
        handler = self._reconciliation_handler or self.add_missing_embeddings_to_existing_chunks
        result = await handler(...)

# In tests:
async def mock_reconciliation(*args, **kwargs):
    raise ProviderError("Test error")

indexer._reconciliation_handler = mock_reconciliation
await indexer.prime_index(force_reindex=False)
```

**Technique 2: Subclass for Testing**
```python
class TestableIndexer(Indexer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._reconciliation_called = False
        self._reconciliation_error = None

    async def add_missing_embeddings_to_existing_chunks(self, *args, **kwargs):
        self._reconciliation_called = True
        if self._reconciliation_error:
            raise self._reconciliation_error
        return await super().add_missing_embeddings_to_existing_chunks(*args, **kwargs)

# In tests:
indexer = TestableIndexer(...)
indexer._reconciliation_error = ProviderError("Test")
await indexer.prime_index(force_reindex=False)
assert indexer._reconciliation_called
```

**Pros**:
- Unit test speed (no Qdrant required)
- Full control over behavior
- Tests stay in unit test suite

**Cons**:
- Requires code changes
- More complex test setup
- May not match real behavior

**Effort**: Moderate (requires Indexer refactoring)
**Reliability**: Moderate (custom mocking adds complexity)

---

### Option 3: Extract Reconciliation Logic 🏗️ ARCHITECTURAL CHANGE

**Approach**: Move reconciliation out of Indexer into separate service

**Design**:
```python
class ReconciliationService:
    """Handles embedding reconciliation logic."""

    async def reconcile_embeddings(
        self,
        vector_store: VectorStore,
        file_manifest: IndexFileManifest,
        embedding_provider: EmbeddingProvider | None,
        sparse_provider: SparseEmbeddingProvider | None,
        *,
        add_dense: bool,
        add_sparse: bool,
    ) -> dict[str, Any]:
        # Current add_missing_embeddings_to_existing_chunks logic here
        pass

class Indexer(BasedModel):
    _reconciliation_service: ReconciliationService = PrivateAttr(default_factory=ReconciliationService)

    async def prime_index(self, ...):
        result = await self._reconciliation_service.reconcile_embeddings(
            vector_store=self._vector_store,
            file_manifest=self._file_manifest,
            embedding_provider=self._embedding_provider,
            sparse_provider=self._sparse_provider,
            add_dense=needs_dense,
            add_sparse=needs_sparse,
        )
```

**Testing**:
```python
# Unit tests for ReconciliationService (not a Pydantic model)
def test_reconciliation_service_handles_errors():
    service = ReconciliationService()
    mock_vector_store = MagicMock()
    mock_vector_store.client.retrieve.side_effect = ProviderError("Test")

    with pytest.raises(ProviderError):
        await service.reconcile_embeddings(...)

# Unit tests for Indexer just mock the service
async def test_prime_index_calls_reconciliation():
    mock_service = AsyncMock()
    indexer = Indexer(...)
    indexer._reconciliation_service = mock_service

    await indexer.prime_index(force_reindex=False)
    mock_service.reconcile_embeddings.assert_called_once()
```

**Pros**:
- Clean separation of concerns
- Easy to test both components
- No Pydantic mocking issues
- Better architecture overall

**Cons**:
- Significant refactoring required
- Changes production code
- May introduce new bugs

**Effort**: High (major refactoring)
**Reliability**: High (proper separation)

---

### Option 4: Accept Integration-Only Coverage ✅ PRAGMATIC

**Approach**: Delete the 4 xfail tests, rely on integration tests

**Rationale**:
- Integration tests already cover the behavior
- `add_missing_embeddings_to_existing_chunks()` is fully unit tested
- The 4 xfail tests are testing integration concerns, not unit logic
- Trying to force unit tests through Pydantic mocking is anti-pattern

**Action Items**:
1. Delete tests marked xfail
2. Enhance integration tests to explicitly verify:
   - Reconciliation is called when expected
   - Errors are handled gracefully
   - Logging occurs correctly
3. Document in test file why integration tests are sufficient

**Pros**:
- Zero code changes required
- Focuses tests on actual behavior
- Eliminates brittle mocking
- Fast implementation

**Cons**:
- Loses unit test coverage for integration logic
- Slower test execution for these scenarios
- May miss edge cases easier to test in unit tests

**Effort**: Very Low (delete + enhance integration tests)
**Reliability**: High (tests real behavior)

---

## Recommendations

### 🥇 Primary Recommendation: Option 1 + Option 4 Hybrid

**Strategy**: Convert xfail tests to integration tests AND enhance existing integration tests

**Implementation Plan**:

#### Phase 1: Enhance Integration Tests (Immediate - Low Effort)
Add to `test_reconciliation_integration.py`:

1. **Test: Reconciliation Error Handling**
   ```python
   @pytest.mark.integration
   async def test_reconciliation_with_provider_error_continues_gracefully(
       qdrant_test_manager, tmp_path, caplog
   ):
       """Verify prime_index continues when reconciliation fails with ProviderError."""
       # Setup indexer with mock provider that raises ProviderError
       # Call prime_index(force_reindex=False)
       # Assert: prime_index completes successfully
       # Assert: Error is logged with specific message
       # Assert: Reconciliation failure doesn't crash indexing
   ```

2. **Test: Reconciliation with Different Error Types**
   ```python
   @pytest.mark.integration
   @pytest.mark.parametrize("error_type", [
       ProviderError("Provider failed"),
       IndexingError("Indexing failed"),
       ConnectionError("Connection failed"),
   ])
   async def test_reconciliation_error_handling(error_type, ...):
       # Test that all error types are handled gracefully
   ```

3. **Test: Reconciliation Skipping Conditions**
   ```python
   @pytest.mark.integration
   async def test_reconciliation_skipped_when_no_vector_store(...):
       # Verify reconciliation is skipped when conditions aren't met

   @pytest.mark.integration
   async def test_reconciliation_skipped_when_no_providers(...):
       # Verify reconciliation is skipped when no providers configured
   ```

#### Phase 2: Remove xfail Tests (Immediate - Low Effort)
1. Delete `TestAutomaticReconciliation` class (lines 383-518)
2. Delete `TestReconciliationExceptionHandling` class (lines 794-989)
3. Add comment explaining why integration tests are sufficient:
   ```python
   # NOTE: Integration tests for prime_index reconciliation are in
   # tests/integration/test_reconciliation_integration.py
   #
   # These tests use real Qdrant and exercise the actual code path,
   # avoiding Pydantic v2 mocking issues while providing better coverage.
   ```

#### Phase 3: Documentation (Immediate - Low Effort)
Update `test_indexer_reconciliation.py` docstring:
```python
"""Tests for automatic embedding reconciliation in the indexer.

Unit Tests (this file):
- TestAddMissingEmbeddings: Direct testing of add_missing_embeddings_to_existing_chunks()
- TestEdgeCases: Edge case handling in reconciliation logic

Integration Tests (test_reconciliation_integration.py):
- Full prime_index() workflow with reconciliation
- Error handling during reconciliation
- Provider integration and manifest updates

Design Note:
We use integration tests for prime_index() reconciliation behavior because:
1. Indexer is a Pydantic v2 BaseModel (method patching incompatible)
2. Integration tests exercise real behavior without brittle mocking
3. The reconciliation method itself has comprehensive unit test coverage
"""
```

**Total Effort**: 1-2 days
**Risk**: Very Low
**Benefits**:
- Eliminates 4 failing tests
- Improves actual test coverage
- No production code changes
- Uses proven integration test pattern

---

### 🥈 Secondary Recommendation: Option 3 (Long-term)

**For Future Refactoring**:
- Extract `ReconciliationService` for better architecture
- Makes testing significantly easier
- Improves separation of concerns
- Consider during next major refactor

**Timing**: Next architectural improvement cycle
**Effort**: 3-5 days (includes tests, docs, review)

---

## Implementation Roadmap

### Week 1: Fix Immediate Issues

**Day 1-2: Integration Test Enhancement**
- [ ] Add error handling integration tests
- [ ] Add reconciliation skipping condition tests
- [ ] Add explicit logging verification tests
- [ ] Use `caplog` fixture to verify error messages

**Day 3: Cleanup**
- [ ] Remove xfail tests from unit test file
- [ ] Add documentation explaining test strategy
- [ ] Update test file docstrings
- [ ] Run full test suite to verify

**Day 4: Verification**
- [ ] Review test coverage report
- [ ] Verify all reconciliation paths are tested
- [ ] Check for any remaining gaps
- [ ] Document findings

### Future: Architectural Improvement

**When refactoring indexer architecture**:
- [ ] Extract ReconciliationService
- [ ] Move logic from add_missing_embeddings_to_existing_chunks
- [ ] Create unit tests for ReconciliationService
- [ ] Simplify Indexer tests

---

## Test Coverage Matrix

### Current State (After Implementing Primary Recommendation)

| Concern | Unit Tests | Integration Tests | Coverage Level |
|---------|-----------|-------------------|----------------|
| Reconciliation core logic | ✅ TestAddMissingEmbeddings | ✅ Multiple scenarios | 🟢 Excellent |
| Edge case handling | ✅ TestEdgeCases | ✅ Real Qdrant scenarios | 🟢 Excellent |
| prime_index integration | ❌ (removed) | ✅ Full workflow | 🟢 Good |
| Error handling | ❌ (removed) | ✅ Multiple error types | 🟢 Good |
| Conditional logic | ❌ (removed) | ✅ Skip conditions | 🟡 Adequate |
| Logging verification | ❌ (removed) | ✅ caplog checks | 🟡 Adequate |

**Overall Assessment**: Good coverage with pragmatic test strategy

---

## Appendix: Code References

### Key Files
- `src/codeweaver/engine/indexer/indexer.py` - Indexer implementation
  - Line 2371: `add_missing_embeddings_to_existing_chunks` method
  - Line 1264: `prime_index` method
  - Line 1334-1400: Reconciliation call site and error handling
- `tests/unit/test_indexer_reconciliation.py` - Unit tests
  - Line 22-381: TestAddMissingEmbeddings (passing)
  - Line 383-518: TestAutomaticReconciliation (xfail)
  - Line 520-791: TestEdgeCases (passing)
  - Line 794-989: TestReconciliationExceptionHandling (xfail)
- `tests/integration/test_reconciliation_integration.py` - Integration tests (all passing)

### Reconciliation Workflow
1. **Entry Point**: `prime_index(force_reindex=False)` at line 1264
2. **Condition Check**: Lines 1334-1338
3. **Embedding Check**: Lines 1346-1351 (`get_files_needing_embeddings`)
4. **Reconciliation Call**: Line 1365 (`add_missing_embeddings_to_existing_chunks`)
5. **Error Handling**: Lines 1377-1396 (ProviderError, IndexingError, ConnectionError)

### Testing Patterns
- **Working Unit Test Pattern**: Direct Indexer instantiation with mocked providers
- **Working Integration Test Pattern**: Real Qdrant + mocked embedding providers + call wrapping
- **Failing Pattern**: Class-level patching of Pydantic BaseModel methods

---

## Questions for Stakeholders

1. **Priority**: Is reconciliation error handling critical enough to require unit tests, or are integration tests sufficient?

2. **Architecture**: Are we planning any major Indexer refactoring in the next 6 months?
   - If yes: Consider Option 3 (ReconciliationService extraction) now
   - If no: Proceed with Option 1 (integration tests only)

3. **Test Suite Performance**: How important is test execution speed for this specific area?
   - If critical: Consider Option 2 (Pydantic-compatible mocking)
   - If acceptable: Option 1 is fine (integration tests are still fast)

4. **Coverage Standards**: What's the minimum acceptable test coverage for error handling paths?
   - Integration only: Accept current approach
   - Unit required: Need architectural change (Option 3)

---

## Conclusion

**Recommended Path Forward**:
1. ✅ Implement Primary Recommendation (Option 1 + 4 Hybrid)
2. ⏱️ Consider Option 3 during next refactoring cycle
3. 📊 Monitor test coverage and execution time
4. 🔄 Reassess if Pydantic v3 changes mocking compatibility

**Expected Outcome**:
- All tests passing (no xfail)
- Comprehensive reconciliation coverage via integration tests
- Maintained unit test coverage for core reconciliation logic
- Clean, maintainable test suite
- No production code changes required

**Success Metrics**:
- 0 failing/xfail tests in reconciliation suite
- >90% code coverage for `add_missing_embeddings_to_existing_chunks`
- >80% coverage for reconciliation call path in `prime_index`
- All error handling paths explicitly tested
- Test suite execution time <5min for reconciliation tests
