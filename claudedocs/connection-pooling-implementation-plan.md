<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Claude AI Assistant

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Connection Pooling Implementation Plan

**Status**: ✅ Implemented
**Priority**: High
**Branch**: `claude/plan-connection-pooling-011nqd3xSBSn6a1FQdjnf8Qg`
**Based on**: `claudedocs/client-pooling-analysis.md`

---

## Overview

This document outlines the immediate implementation plan for HTTP connection pooling across CodeWeaver's HTTP-based providers. The implementation will be phased, starting with core infrastructure and progressing to provider integration.

## Phase 1: Infrastructure (Core Implementation)

### Task 1.1: Create HttpClientPool Class

**File**: `src/codeweaver/common/http_pool.py`

Create a centralized HTTP client pool manager with:
- Singleton pattern for application-wide access
- Configurable connection limits and timeouts
- Per-provider client management
- HTTP/2 support for better multiplexing
- Proper async cleanup

**Key Components**:
```python
@dataclass(frozen=True)
class PoolLimits:
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: float = 5.0

@dataclass(frozen=True)
class PoolTimeouts:
    connect: float = 10.0
    read: float = 60.0
    write: float = 10.0
    pool: float = 5.0

class HttpClientPool:
    # Singleton instance
    # Per-provider client dict
    # get_client(name, **overrides) method
    # close_all() cleanup method
```

### Task 1.2: Add Configuration Settings

**File**: `src/codeweaver/config/settings.py`

Add `HttpPoolSettings` TypedDict for configuration:
```python
class HttpPoolSettings(TypedDict, total=False):
    max_connections: int
    max_keepalive_connections: int
    keepalive_expiry: float
    connect_timeout: float
    read_timeout: float
    write_timeout: float
    pool_timeout: float
    enable_http2: bool
```

### Task 1.3: Integrate into CodeWeaverState

**File**: `src/codeweaver/server/server.py`

Add `http_pool` field to `CodeWeaverState`:
```python
http_pool: Annotated[
    HttpClientPool | None,
    Field(
        default=None,
        description="Shared HTTP client pool for provider connections",
        exclude=True,
    ),
] = None
```

Initialize in `_initialize_cw_state()` function.

### Task 1.4: Add Cleanup to Lifespan

**File**: `src/codeweaver/server/server.py`

Update `_cleanup_state()` to close HTTP pools:
```python
# Close HTTP client pools
if state.http_pool:
    try:
        await state.http_pool.close_all()
    except Exception:
        _logger.exception("Error closing HTTP client pools")
```

---

## Phase 2: Provider Integration

### Task 2.1: Update Voyage AI Provider

**File**: `src/codeweaver/providers/embedding/providers/voyage.py`

The Voyage AI `AsyncClient` accepts an `httpx_client` parameter. We'll modify initialization to use the pooled client.

**Current Flow**:
```python
client = AsyncClient(api_key=api_key)
```

**New Flow**:
```python
def _get_pooled_httpx_client() -> httpx.AsyncClient | None:
    """Get pooled HTTP client for Voyage AI."""
    try:
        from codeweaver.server.server import get_state
        state = get_state()
        if state.http_pool:
            return state.http_pool.get_client(
                'voyage',
                max_connections=50,
                read_timeout=90.0,
            )
    except Exception:
        pass  # Fallback to default client
    return None

# In provider initialization
httpx_client = _get_pooled_httpx_client()
client = AsyncClient(api_key=api_key, httpx_client=httpx_client)
```

### Task 2.2: Update Cohere Provider

**File**: `src/codeweaver/providers/embedding/providers/cohere.py`

The Cohere `AsyncClientV2` accepts an `httpx_client` parameter in `client_options`.

**Current Flow** (line 123):
```python
known_client_options = {
    "api_key", "base_url", "timeout", "max_retries", "httpx_client",
}
```

**New Flow**: Add pooled client to options:
```python
def _get_pooled_httpx_client() -> httpx.AsyncClient | None:
    """Get pooled HTTP client for Cohere."""
    try:
        from codeweaver.server.server import get_state
        state = get_state()
        if state.http_pool:
            return state.http_pool.get_client(
                'cohere',
                max_connections=50,
                read_timeout=90.0,
            )
    except Exception:
        pass
    return None

# In __init__ before creating client:
if not client_options.get("httpx_client"):
    client_options["httpx_client"] = _get_pooled_httpx_client()
```

### Task 2.3: Qdrant Considerations

**File**: `src/codeweaver/providers/vector_stores/qdrant_base.py`

The `qdrant_client` library uses httpx internally but doesn't expose an `httpx_client` parameter. We have two options:

1. **Use timeout configuration** (recommended for now):
   - Configure longer timeouts via `qdrant_client` parameters
   - This addresses the httpcore.ReadError issues

2. **Future enhancement**:
   - Investigate if newer qdrant_client versions expose httpx configuration
   - Consider contributing upstream if needed

---

## Implementation Order

```
1. Create http_pool.py module
2. Add HttpPoolSettings to config
3. Add http_pool to CodeWeaverState
4. Add cleanup to _cleanup_state()
5. Update Voyage AI provider
6. Update Cohere provider
7. Add unit tests
8. Integration testing
```

---

## Provider-Specific Settings

| Provider | max_connections | read_timeout | keepalive_expiry | HTTP/2 | Parameter Name |
|----------|----------------|--------------|------------------|--------|----------------|
| Voyage   | 50             | 90s          | 5s               | Yes    | `httpx_client` |
| Cohere   | 50             | 90s          | 5s               | Yes    | `httpx_client` |
| OpenAI   | 50             | 90s          | 5s               | Yes    | `http_client`  |
| Azure    | 50             | 90s          | 5s               | Yes    | `http_client`  |
| Fireworks| 50             | 90s          | 5s               | Yes    | `http_client`  |
| Groq     | 50             | 90s          | 5s               | Yes    | `http_client`  |
| Together | 50             | 90s          | 5s               | Yes    | `http_client`  |
| Ollama   | 50             | 90s          | 5s               | Yes    | `http_client`  |
| Cerebras | 50             | 90s          | 5s               | Yes    | `http_client`  |
| Heroku   | 50             | 90s          | 5s               | Yes    | `http_client`  |
| Mistral  | 50             | 90s          | 5s               | Yes    | `httpx_client` |
| Qdrant   | N/A            | N/A          | N/A              | N/A    | Not supported  |

**Note**: Qdrant uses httpx internally but doesn't expose a client injection parameter.

---

## Testing Strategy

### Unit Tests
- `test_http_pool_singleton()` - Verify singleton behavior
- `test_client_reuse()` - Verify client caching
- `test_cleanup()` - Verify proper cleanup
- `test_provider_overrides()` - Verify per-provider settings

### Integration Tests
- Test Voyage AI with pooled client
- Test Cohere with pooled client
- Verify connection reuse (check logs)

### Manual Verification
- Run `cw index` on a large repo
- Monitor for httpcore.ReadError (should be eliminated)
- Check connection reuse in debug logs

---

## Rollback Plan

The implementation includes fallbacks:
1. If `get_state()` fails, providers fall back to default clients
2. If `http_pool` is None, providers create their own clients
3. No breaking changes to existing interfaces

---

## Success Metrics

1. **No httpcore.ReadError** during indexing operations
2. **Reduced connection overhead** (visible in debug logs)
3. **All existing tests pass** without modification
4. **Memory usage stable** during long indexing operations

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/codeweaver/common/http_pool.py` | **Create** | HTTP client pool manager |
| `src/codeweaver/config/settings.py` | Modify | Add HttpPoolSettings |
| `src/codeweaver/server/server.py` | Modify | Add http_pool to state, cleanup |
| `src/codeweaver/providers/embedding/providers/voyage.py` | Modify | Use pooled client |
| `src/codeweaver/providers/embedding/providers/cohere.py` | Modify | Use pooled client |
| `tests/unit/common/test_http_pool.py` | **Create** | Unit tests |

---

## Notes

- The implementation prioritizes backward compatibility
- Fallbacks ensure the system works without pooling if needed
- HTTP/2 is enabled by default for better multiplexing on modern APIs
- Qdrant integration may require upstream changes to qdrant_client
