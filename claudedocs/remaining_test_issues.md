<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Remaining Integration Test Issues - Detailed Analysis

## Overview
After fixing critical import and initialization errors, 65 out of 90 integration tests are now passing (72%). This document details the remaining failures and recommended fixes.

## Category 1: Tests Requiring External Services (6 tests) - EXPECTED FAILURES
These tests are marked with `pytest.mark.external_api` and require a running Qdrant instance:

1. `test_hybrid_storage.py::test_store_hybrid_embeddings`
2. `test_hybrid_ranking.py::test_hybrid_search_ranking`
3. `test_incremental_updates.py::test_incremental_updates`
4. `test_partial_embeddings.py::test_partial_embeddings`
5. `test_persistence.py::test_persistence_across_restarts`
6. `test_provider_switch.py::test_provider_switch_detection`

**Error**: `qdrant_client.http.exceptions.ResponseHandlingException: All connection attempts failed`

**Recommendation**: 
- Document Qdrant as a test prerequisite in test README
- Or: Create mock Qdrant responses for these tests
- Or: Use in-memory vector store for test fixtures

## Category 2: Provider Configuration Issues (7 tests) - FIXABLE
All tests in `test_server_indexing.py` fail with: `ConfigurationError: No embedding providers configured`

Affected tests:
1. `test_server_starts_without_errors`
2. `test_auto_indexing_on_startup`
3. `test_indexing_progress_via_health`
4. `test_indexing_completes_successfully`
5. `test_file_change_indexing`
6. `test_indexing_performance`
7. `test_indexing_error_recovery`

**Root Cause**: Tests need fixtures that properly configure embedding and vector store providers before starting the server.

**Recommended Fix**:
```python
@pytest.fixture
def configured_providers(tmp_path):
    """Configure test providers for server tests."""
    # Set up minimal FastEmbed provider (no API key needed)
    config = {
        "provider": {
            "embedding": {
                "provider": "fastembed",
                "model": "BAAI/bge-small-en-v1.5"
            },
            "vector_store": {
                "provider": "memory",
                "collection_name": "test_collection"
            }
        }
    }
    # Apply configuration before server startup
    return config
```

## Category 3: Mock Setup Issues (1 test) - FIXABLE

### test_error_recovery.py::test_sparse_only_fallback

**Error**: Returns `KEYWORD_FALLBACK` instead of `SPARSE_ONLY`

**Root Cause**: The mock registry doesn't properly implement all required methods:
- `get_embedding_provider(sparse=False)` needs to return None (dense provider missing)
- `get_embedding_provider(sparse=True)` needs to return a valid provider enum
- `get_embedding_provider_instance()` needs to work with the enum

**Current Mock** (incomplete):
```python
mock_reg.get_embedding_provider_instance.return_value = mock_dense_provider
```

**Recommended Fix**:
```python
# Mock the registry methods properly
mock_reg.get_embedding_provider.side_effect = lambda sparse=False: (
    Provider.FASTEMBED if sparse else None  # Dense provider missing
)
mock_reg.get_embedding_provider_instance.side_effect = lambda provider, **kwargs: (
    mock_sparse_provider if provider == Provider.FASTEMBED else None
)
```

## Category 4: Test Logic Issues (3 tests) - NEED INVESTIGATION

### test_error_recovery.py::test_indexing_continues_on_file_errors
**Error**: `assert 2 >= 4`
**Issue**: Test expects at least 4 files to be discovered, but only 2 are found.
**Recommendation**: Check if test fixture is creating enough files or adjust expectations.

### test_error_recovery.py::test_health_shows_degraded_status
**Error**: `AttributeError: 'dict' object has no attribute 'get_timing_statistics'`
**Issue**: Code is calling a method on what should be a SessionStatistics object but is receiving a dict.
**Recommendation**: Check that the statistics fixture is properly initialized.

### test_error_recovery.py::test_error_logging_structured
**Error**: `Failed: DID NOT RAISE <class 'Exception'>`
**Issue**: Test expects an exception to be raised but none is raised.
**Recommendation**: Review test logic - the code may have been updated to handle errors gracefully instead of raising.

## Category 5: Reference Query Tests (2 tests) - REQUIRES FULL SYSTEM

### test_reference_queries.py::test_reference_queries_comprehensive
**Error**: `Precision@3 (0.00%) below target (70%)`
**Issue**: Search returns no results because there's no indexed codebase with embeddings.

### test_reference_queries.py::test_query_diversity_metrics
**Error**: `Need at least 10 P@5 queries for valid metrics`
**Issue**: Only 8 queries available for testing.

**Recommendation**: These tests require:
1. A fully configured embedding provider
2. A populated vector store with indexed code
3. Real embeddings generated
4. Either: Run against live CodeWeaver codebase, or create comprehensive test fixtures

## Actionable Next Steps

### Quick Wins (1-2 hours):
1. ✅ Add provider configuration fixture for test_server_indexing.py tests
2. ✅ Fix mock setup in test_sparse_only_fallback
3. ✅ Investigate and fix test_indexing_continues_on_file_errors

### Medium Effort (2-4 hours):
4. Debug test_health_shows_degraded_status (statistics fixture issue)
5. Review test_error_logging_structured expectations
6. Add more reference queries to meet minimum count

### Longer Term (consider for v0.2):
7. Create mock Qdrant responses or use in-memory store for external_api tests
8. Build comprehensive test fixture with pre-generated embeddings
9. Set up CI environment with Qdrant for full integration testing

## Test Priority Matrix

| Priority | Tests | Effort | Blocks |
|----------|-------|--------|--------|
| P0 | Provider config (7) | Medium | Server functionality |
| P1 | Mock setup (1) | Low | Error recovery validation |
| P2 | Test logic (3) | Medium | Test suite integrity |
| P3 | Reference queries (2) | High | Quality metrics |
| P4 | Qdrant tests (6) | High | Full integration |

