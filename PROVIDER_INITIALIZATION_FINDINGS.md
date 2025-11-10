# Provider Initialization Issues - Test Results

## Executive Summary

Testing revealed **two critical initialization bugs** that prevent ALL embedding and reranking providers from functioning correctly across the codebase. These issues affect every provider implementation (Voyage, Cohere, Bedrock, etc.) and explain why clients aren't initializing properly.

## Issue #1: EmbeddingProvider.__init__() Pydantic Conflict

### Location
`src/codeweaver/providers/embedding/providers/base.py`, lines 209-210

### The Problem
```python
# Line 209-210 in __init__
self.doc_kwargs = type(self)._doc_kwargs.copy() or {}
self.query_kwargs = type(self)._query_kwargs.copy() or {}
```

When these lines execute:
1. Pydantic tries to handle the attribute assignment
2. Since `doc_kwargs`/`query_kwargs` are not defined Pydantic fields
3. And model has `extra="allow"` config
4. Pydantic tries to store them in `__pydantic_extra__`
5. But `__pydantic_extra__` is overridden as a classmethod returning `{}` (line 235)
6. **CRASH**: `TypeError: 'method' object does not support item assignment`

### Error Message
```
TypeError: 'method' object does not support item assignment
  at .venv/lib/python3.12/site-packages/pydantic/main.py:1082: TypeError
```

### Impact
- **100% failure rate** for embedding provider initialization
- Affects: VoyageEmbeddingProvider, CohereEmbeddingProvider, BedrockEmbeddingProvider, and ALL others
- **All 32 embedding provider tests fail** with this error

### Root Cause Analysis
The code attempts to set instance variables before calling `super().__init__()`, which conflicts with Pydantic's field validation system. The pattern of:
1. Set instance attributes (lines 209-210, 217-219)
2. Call _initialize() (line 222)
3. Finally call super().__init__() (line 224)

This order is incompatible with Pydantic's validation flow.

## Issue #2: RerankingProvider Missing _telemetry_keys

### Location
`src/codeweaver/providers/reranking/providers/base.py`

### The Problem
The `RerankingProvider` class inherits from `BasedModel` which expects a `_telemetry_keys` method for privacy/anonymity handling (similar to `EmbeddingProvider`), but:
- The abstract method is not defined in `RerankingProvider` base class
- Concrete implementations don't override it
- Python ABC system prevents instantiation

### Error Message
```
TypeError: Can't instantiate abstract class VoyageRerankingProvider without 
an implementation for abstract method '_telemetry_keys'
```

### Impact
- **100% failure rate** for reranking provider instantiation
- Affects: VoyageRerankingProvider, CohereRerankingProvider, BedrockRerankingProvider, and ALL others
- **All 29 reranking provider tests fail** with this error

### Root Cause Analysis
`EmbeddingProvider` has a `_telemetry_keys` method (line 810-821 in base.py) that returns filtering rules for telemetry/privacy. This same pattern is needed in `RerankingProvider` but was never implemented.

## Test Results Summary

### Tests Created
- **52 comprehensive unit tests** covering:
  - Provider initialization patterns
  - Client creation with/without API keys
  - Capability configuration
  - Basic embed/rerank operations
  - Error handling and retry logic
  - Circuit breaker functionality
  - Property access

### Test Failures
- **Embedding providers**: 32/32 tests fail (100%)
  - All fail on initialization with Pydantic TypeError
- **Reranking providers**: 29/29 tests fail (100%)
  - All fail on instantiation with missing abstract method
- **Total**: 61/62 tests fail (98.4% failure rate)
  - Only 1 test passed (a Cohere error test that expected ConfigurationError)

## Recommended Fixes

### Fix #1: EmbeddingProvider Initialization

**Option A** (Recommended): Use object.__setattr__ for pre-super assignments
```python
def __init__(self, client, caps, kwargs):
    object.__setattr__(self, 'doc_kwargs', type(self)._doc_kwargs.copy() or {})
    object.__setattr__(self, 'query_kwargs', type(self)._query_kwargs.copy() or {})
    object.__setattr__(self, '_circuit_state', CircuitBreakerState.CLOSED)
    # ... other pre-init setup
    
    self._initialize(caps)
    super().__init__(client=client, caps=caps)
```

**Option B**: Move instance variable setup to after super().__init__()
```python
def __init__(self, client, caps, kwargs):
    super().__init__(client=client, caps=caps)
    
    self.doc_kwargs = type(self)._doc_kwargs.copy() or {}
    self.query_kwargs = type(self)._query_kwargs.copy() or {}
    # ... rest of setup
    self._initialize(caps)
```

### Fix #2: RerankingProvider _telemetry_keys

Add the method to RerankingProvider base class:
```python
def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
    from codeweaver.core.types import AnonymityConversion, FilteredKey
    
    return {
        FilteredKey("_client"): AnonymityConversion.FORBIDDEN,
        FilteredKey("_input_transformer"): AnonymityConversion.FORBIDDEN,
        FilteredKey("_output_transformer"): AnonymityConversion.FORBIDDEN,
        FilteredKey("_rerank_kwargs"): AnonymityConversion.COUNT,
        FilteredKey("_chunk_store"): AnonymityConversion.COUNT,
    }
```

## Files Affected

### Test Files (New)
- `tests/unit/providers/__init__.py`
- `tests/unit/providers/embedding/__init__.py`
- `tests/unit/providers/embedding/test_voyage.py` (23 tests)
- `tests/unit/providers/embedding/test_cohere.py` (9 tests)
- `tests/unit/providers/reranking/__init__.py`
- `tests/unit/providers/reranking/test_voyage.py` (16 tests)
- `tests/unit/providers/reranking/test_cohere.py` (13 tests)

### Source Files (Need Fixes)
- `src/codeweaver/providers/embedding/providers/base.py`
- `src/codeweaver/providers/reranking/providers/base.py`

## Additional Observations

1. **Initialization Pattern Issues**: Both provider types use a pattern of setting attributes before calling super().__init__(), which is anti-pattern with Pydantic v2's validation system.

2. **ClassVar Usage**: The codebase uses ClassVars for default values (_doc_kwargs, _query_kwargs, _rerank_kwargs) then tries to copy them to instance variables, but the timing conflicts with Pydantic.

3. **Lack of Symmetry**: EmbeddingProvider and RerankingProvider should have similar structures since they serve parallel purposes, but they diverge in key areas (telemetry handling, initialization flow).

4. **Testing Gap**: These are fundamental issues that would have been caught by basic unit tests. The lack of provider-level unit tests allowed these bugs to persist.

## Verification Plan

After implementing fixes:
1. Run the new test suite: `pytest tests/unit/providers/ -v`
2. Verify all 62 tests pass
3. Run integration tests to ensure end-to-end functionality
4. Test with actual API keys (if available) for Voyage and Cohere

## Related Issues

This explains the problem mentioned in PR #60 where "clients aren't initializing across the embedders and rerankers". The initialization bugs prevent proper client setup and usage.
