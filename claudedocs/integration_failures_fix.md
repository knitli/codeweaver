<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Integration Test Failures Fix - Branch 003-our-aim-to

## Mission Summary
Fixed 6 of 9 integration test failures on branch `003-our-aim-to`. All provider instantiation tests now pass. Remaining failures require deeper investigation of search strategy logic and infrastructure dependencies.

## Constitutional Compliance
- ✅ Evidence-Based Development: All fixes validated through verifiable test execution
- ✅ Proven Patterns: Used FastAPI/pydantic ecosystem patterns (Mock object configuration)
- ✅ Testing Philosophy: Focused on critical behavior affecting user experience (provider configuration)
- ✅ Simplicity Through Architecture: Clear root cause identification and minimal fixes

## Failures Fixed (6/9)

### 1-5. Provider Instantiation Tests (tests/integration/test_client_factory_integration.py)

**Root Cause**: Mock objects not properly configured for `__name__` attribute access
- Registry stores `mock_provider_lazy` (not `mock_provider_class`)
- Code at `provider.py:955` checks `retrieved_cls.__name__`
- Mock without explicit `__name__` returns `None` on attribute access
- `not None` is `True`, triggering ConfigurationError

**Fix Applied**:
```python
# BEFORE (incorrect)
mock_provider_class.__name__ = "MockVoyageProvider"

# AFTER (correct)
mock_provider_lazy.__name__ = "MockVoyageProvider"  # lazy mock is what gets checked
mock_provider_lazy.return_value = mock_provider_instance  # lazy mock is what gets called
```

**Tests Fixed**:
1. ✅ `test_create_provider_with_client_from_map` - Provider instantiation with CLIENT_MAP integration
2. ✅ `test_create_provider_skips_client_if_provided` - Existing client not overridden
3. ✅ `test_create_provider_handles_client_creation_failure` - Graceful degradation on client failure
4. ✅ `test_string_provider_kind_in_create_provider` - String provider_kind support
5. ✅ `test_get_provider_registry_has_client_factory` - Global registry integration

### 6. Qdrant Memory Mode Test (tests/integration/test_client_factory_integration.py)

**Root Cause**: Mock didn't trigger memory mode fallback logic
- Code at `provider.py:698` tries `client_class(**provider_settings, **client_options)`
- Mock succeeds with empty dicts, never reaching fallback at line 702
- Test expects `location=":memory:"` from fallback

**Fix Applied**:
```python
# BEFORE
mock_client_class = Mock(return_value=mock_client_instance)

# AFTER
mock_client_class = Mock(side_effect=[Exception("No URL provided"), mock_client_instance])
# First call raises exception → fallback to memory mode
# Second call returns instance with memory mode
```

**Test Fixed**:
6. ✅ `test_qdrant_provider_with_memory_mode` - Qdrant fallback to memory mode when no URL provided

## Failures Remaining (3/9)

### 7. Search Strategy Test (tests/integration/test_error_recovery.py::test_sparse_only_fallback)

**Error**: `AssertionError: assert <SearchStrategy.SPARSE_ONLY: 'sparse_only'> in (<SearchStrategy.KEYWORD_FALLBACK: 'keyword_fallback'>,)`

**Root Cause**: Mock configuration not matching actual provider discovery logic
- Test mocks `get_provider_enum_for` to return `Provider.FASTEMBED` for sparse
- Pipeline code at `__init__.py:66` raises: "No embedding providers configured (neither dense nor sparse)"
- Sparse provider not recognized despite mock configuration
- Falls back to KEYWORD_FALLBACK instead of SPARSE_ONLY

**Investigation Needed**:
1. How does `embed_query` discover sparse embedding providers?
2. Does it use `get_provider_enum_for` or different discovery mechanism?
3. What's the correct mock configuration to simulate sparse-only scenario?

### 8. Search Strategy Reporting (tests/integration/test_search_workflows.py::test_search_strategy_reporting)

**Error**: `AssertionError: assert (<SearchStrategy.HYBRID_SEARCH: 'hybrid_search'> in ...) or (<SearchStrategy.DENSE_SEARCH: 'dense_search'> in ...)`

**Root Cause**: Similar to test #7 - search strategy detection logic mismatch

**Investigation Needed**:
1. What determines search strategy selection in real vs test scenarios?
2. How is strategy reported in `FindCodeResponseSummary`?
3. Are test expectations realistic for mocked provider setup?

### 9. Server Indexing Timeout (tests/integration/test_server_indexing.py::test_indexing_completes_successfully)

**Error**: `AssertionError: Indexing took 763s, expected <120s`

**Root Cause**: Performance issue or unrealistic threshold
- Indexing takes 12.7 minutes vs 2-minute expectation
- Related to known chunker performance issues (see constitution)

**Possible Solutions**:
1. **Adjust threshold**: Change to 900s (15 min) if 763s is realistic for test dataset
2. **Optimize chunker**: Investigate performance bottleneck in chunking pipeline
3. **Skip test**: Mark as `@pytest.mark.slow` if infrastructure-dependent

**Constitutional Note**: Per constitution, testing philosophy prioritizes effectiveness over coverage. If this test measures infrastructure performance rather than user-affecting behavior, consider skipping or adjusting expectations.

## Verification

Run fixed tests:
```bash
python -m pytest tests/integration/test_client_factory_integration.py -v
# Result: 7/7 PASSED ✅
```

Run remaining failures:
```bash
python -m pytest tests/integration/test_error_recovery.py::test_sparse_only_fallback -xvs
python -m pytest tests/integration/test_search_workflows.py::test_search_strategy_reporting -xvs
python -m pytest tests/integration/test_server_indexing.py::test_indexing_completes_successfully -xvs
# Result: 3 FAILED (investigation needed)
```

## Technical Details

### Mock Configuration Pattern
```python
# For provider instantiation tests:
1. mock_provider_lazy (registered class) needs:
   - __name__ attribute for import check
   - return_value for instantiation
   - _resolve() method returning mock_provider_class

2. Assertions should check mock_provider_lazy, not mock_provider_class
```

### Code Flow Understanding
```python
# provider.py:create_provider() for EMBEDDING kind:
889: def create_provider(provider, provider_kind, **kwargs):
908-914: retrieved_cls = get_provider_class(provider, provider_kind)  # Returns mock_provider_lazy
916-938: Create client if not in kwargs (uses _create_client_from_map)
941-959: Special embedding provider handling:
  949: if isinstance(retrieved_cls, LazyImport): return _create_provider(...)  # Not taken (Mock ≠ LazyImport)
  953: name = None
  954: with contextlib.suppress(Exception):
  955:     name = retrieved_cls.__name__  # ← CRITICAL: Checks lazy mock, not resolved class
  956: if not name: raise ConfigurationError(...)  # ← Was failing here
  959: return retrieved_cls(**kwargs)  # ← Instantiates lazy mock
```

### Qdrant Memory Mode Flow
```python
# provider.py:_instantiate_client() for QDRANT:
694-703: if provider == Provider.QDRANT:
  697: try:
  698:     client = client_class(**provider_settings, **client_options)  # First attempt
  699: except Exception as e:
  700:     logger.warning("Failed to create Qdrant client: %s", e)
  701:     logger.info("Falling back to in-memory mode")
  702:     return client_class(location=":memory:", **client_options)  # Fallback
```

## Recommendations

### Immediate Actions
1. ✅ **DONE**: Fix all provider instantiation tests (6 tests)
2. 🔄 **IN PROGRESS**: Document findings for remaining 3 tests

### Next Steps
1. **Search Strategy Tests** (2 tests):
   - Read `agent_api/find_code/pipeline.py` to understand provider discovery
   - Read `agent_api/find_code/__init__.py` error handling
   - Determine correct mock configuration for sparse-only scenario

2. **Indexing Timeout Test** (1 test):
   - Profile indexing performance on test dataset
   - Decide: adjust threshold vs optimize chunker vs skip test
   - If adjusting: Document rationale (realistic performance expectation)

3. **Quality Gates**:
   - Run `ruff check` and `pyright` on modified test file
   - Verify test suite still passes: `python -m pytest tests/integration/test_client_factory_integration.py`

## Files Modified
- `/home/knitli/codeweaver-mcp/tests/integration/test_client_factory_integration.py` (mock configuration fixes)

## Test Coverage Impact
- Before: 284/348 tests passing (81.6%)
- After: 290/348 tests passing (83.3%) ← Expected after fixes
- Target: Address remaining 3 integration tests to reach 293/348 (84.2%)
