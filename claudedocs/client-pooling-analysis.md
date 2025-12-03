<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Client Pooling Analysis & Implementation Strategy

## Executive Summary

CodeWeaver currently creates individual HTTP clients for each provider (Voyage AI, Cohere, Qdrant) without connection pooling. This leads to:
- **Connection overhead** from repeated TCP handshakes
- **Resource waste** from creating/destroying connections
- **Potential connection exhaustion** during high-load indexing
- **Qdrant timeout issues** (httpcore.ReadError) due to connection instability

**Recommendation**: Implement shared HTTP client pools at the application state level with configurable limits and proper lifecycle management.

---

## Current State Analysis

### Providers Using httpx

CodeWeaver already tracks which providers use httpx via `Provider.other_env_vars` (see `src/codeweaver/providers/provider.py:118-125`).

**Providers with httpx support** (have `httpx_env_vars` in their config):

| Provider | Use Case | httpx Support |
|----------|----------|---------------|
| **VOYAGE** | Embedding, Reranking | ✅ Direct |
| **COHERE** | Embedding, Reranking | ✅ Direct |
| **MISTRAL** | Embedding | ✅ Direct |
| **TAVILY** | Web Search | ✅ Direct |
| **GOOGLE** | Agent | ✅ Direct |
| **HUGGINGFACE_INFERENCE** | Various | ✅ Direct |
| **OpenAI-compatible** | Agent, Embedding | ✅ Direct |
| - OPENAI, FIREWORKS, GITHUB, X_AI | | |
| - GROQ, MOONSHOT, OLLAMA | | |
| - OPENROUTER, PERPLEXITY, CEREBRAS | | |
| **AZURE** | Multiple (OpenAI, Cohere on Azure) | ✅ Direct |
| **VERCEL** | Agent | ✅ Direct |
| **TOGETHER** | Agent | ✅ Direct |
| **HEROKU** | Agent | ✅ Direct |
| **DEEPSEEK** | Agent | ✅ Direct |

**Providers NOT using httpx**:
- **QDRANT**: Uses httpx internally via qdrant_client but doesn't expose `httpx_env_vars`
- **BEDROCK**: Uses boto3 (AWS SDK), not httpx
- **FASTEMBED, MEMORY, SENTENCE_TRANSFORMERS**: Local providers

### Client Instantiation Patterns

#### 1. **Voyage AI** (src/codeweaver/providers/embedding/providers/voyage.py)
```python
# Created per-provider instance, NO connection pooling
from voyageai.client_async import AsyncClient

client = AsyncClient(api_key=api_key)  # Line 120
```

#### 2. **Cohere** (src/codeweaver/providers/embedding/providers/cohere.py)
```python
# Created per-provider instance
from cohere import AsyncClientV2

client = CohereClient(api_key=api_key, **client_options)
```

#### 3. **Qdrant** (implicitly uses httpx via qdrant_client)
```python
# qdrant_client internally uses httpx but we don't control pooling
await self._client.upsert(collection_name=collection_name, points=points)
```

### Problems Identified

1. **No Connection Reuse**: Each provider creates fresh connections per request
2. **No Pool Limits**: Unbounded connection creation during batch operations
3. **No Shared Infrastructure**: Each provider manages its own HTTP client
4. **Connection Lifecycle**: Clients created at provider init, but no explicit cleanup
5. **Qdrant Instability**: Connection errors (httpcore.ReadError) suggest pool exhaustion or timeout issues

---

## Connection Pooling Architecture

### httpx Connection Pooling

Both `voyageai` and `cohere` use `httpx` internally, which DOES support connection pooling:

```python
import httpx

# httpx.AsyncClient has built-in connection pooling
limits = httpx.Limits(
    max_connections=100,      # Total connections across all hosts
    max_keepalive_connections=20,  # Persistent connections to keep alive
    keepalive_expiry=5.0,     # Seconds to keep connections alive
)

timeout = httpx.Timeout(
    connect=10.0,    # Connection timeout
    read=30.0,       # Read timeout
    write=10.0,      # Write timeout
    pool=5.0         # Pool acquire timeout
)

client = httpx.AsyncClient(limits=limits, timeout=timeout)
```

### Current Library Support

**Voyage AI**:
- `AsyncClient` accepts `max_retries` and timeout configs
- Internally uses `httpx` but doesn't expose pool configuration
- **Action**: Pass custom `httpx_client` to Voyage's AsyncClient

**Cohere**:
- `AsyncClientV2` accepts `httpx_client` parameter
- Full control over connection pooling
- **Action**: Create shared httpx client and pass to Cohere

**Qdrant**:
- Uses `httpx` internally via `qdrant_client`
- Provides `timeout` parameter but no direct pool control
- **Action**: May need to patch or configure at qdrant_client level

---

## Proposed Implementation

### 0. Helper Method for Provider Detection

Add a helper method to `Provider` enum to identify httpx-using providers:

**File**: `src/codeweaver/providers/provider.py`

```python
@property
def uses_httpx(self) -> bool:
    """Check if the provider uses httpx for HTTP connections.

    Providers that use httpx can benefit from connection pooling.
    Determined by checking if httpx_env_vars are present in other_env_vars.
    """
    if env_vars := self.other_env_vars:
        if isinstance(env_vars, tuple):
            # Check all env var dicts for httpx proxy or ssl settings
            return any(
                "http_proxy" in env_dict or "ssl_cert_file" in env_dict or
                (env_dict.get("other") and ("http_proxy" in env_dict["other"] or "ssl_cert_file" in env_dict["other"]))
                for env_dict in env_vars
            )
    return False
```

### 1. Centralized HTTP Client Pool Manager

Create a singleton HTTP client manager at application state level:

**File**: `src/codeweaver/common/http_pool.py`

```python
from __future__ import annotations

import httpx
import logging
from typing import ClassVar
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class PoolLimits:
    """HTTP connection pool limits configuration."""
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: float = 5.0

@dataclass(frozen=True)
class PoolTimeouts:
    """HTTP timeout configuration."""
    connect: float = 10.0
    read: float = 60.0  # Longer for embedding/vector operations
    write: float = 10.0
    pool: float = 5.0

class HttpClientPool:
    """Singleton HTTP client pool manager for provider connections."""

    _instance: ClassVar[HttpClientPool | None] = None
    _clients: dict[str, httpx.AsyncClient]
    _limits: PoolLimits
    _timeouts: PoolTimeouts

    def __init__(
        self,
        limits: PoolLimits | None = None,
        timeouts: PoolTimeouts | None = None
    ):
        self._clients = {}
        self._limits = limits or PoolLimits()
        self._timeouts = timeouts or PoolTimeouts()

    @classmethod
    def get_instance(cls) -> HttpClientPool:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_client(self, name: str, **overrides) -> httpx.AsyncClient:
        """Get or create a pooled HTTP client for a specific provider.

        Args:
            name: Provider name (e.g., 'voyage', 'cohere', 'qdrant')
            **overrides: Override default limits/timeouts for this client

        Returns:
            Configured httpx.AsyncClient with connection pooling
        """
        if name not in self._clients:
            limits = httpx.Limits(
                max_connections=overrides.get('max_connections', self._limits.max_connections),
                max_keepalive_connections=overrides.get(
                    'max_keepalive_connections',
                    self._limits.max_keepalive_connections
                ),
                keepalive_expiry=overrides.get('keepalive_expiry', self._limits.keepalive_expiry),
            )

            timeout = httpx.Timeout(
                connect=overrides.get('connect_timeout', self._timeouts.connect),
                read=overrides.get('read_timeout', self._timeouts.read),
                write=overrides.get('write_timeout', self._timeouts.write),
                pool=overrides.get('pool_timeout', self._timeouts.pool),
            )

            self._clients[name] = httpx.AsyncClient(
                limits=limits,
                timeout=timeout,
                http2=overrides.get('http2', True),  # Enable HTTP/2 for better multiplexing
            )

            logger.info(
                "Created HTTP client pool for %s: max_conn=%d, keepalive=%d",
                name, limits.max_connections, limits.max_keepalive_connections
            )

        return self._clients[name]

    async def close_all(self) -> None:
        """Close all pooled clients (cleanup on shutdown)."""
        for name, client in self._clients.items():
            try:
                await client.aclose()
                logger.info("Closed HTTP client pool for %s", name)
            except Exception:
                logger.exception("Error closing HTTP client pool for %s", name)
        self._clients.clear()

    async def __aenter__(self) -> HttpClientPool:
        return self

    async def __aexit__(self, *args) -> None:
        await self.close_all()
```

### 2. Integration into CodeWeaverState

**File**: `src/codeweaver/server/server.py`

```python
from codeweaver.common.http_pool import HttpClientPool

@dataclass(...)
class CodeWeaverState(DataclassSerializationMixin):
    # ... existing fields ...

    http_pool: Annotated[
        HttpClientPool,
        Field(
            default_factory=HttpClientPool.get_instance,
            description="Shared HTTP client pool for provider connections",
            exclude=True,
        ),
    ] = None
```

**Cleanup in lifespan**:

```python
async def _cleanup_state(
    state: CodeWeaverState,
    indexing_task: asyncio.Task | None,
    status_display: Any,
    *,
    verbose: bool = False,
) -> None:
    """Clean up application state and shutdown services."""
    # ... existing cleanup ...

    # Close HTTP client pools
    if state.http_pool:
        try:
            await state.http_pool.close_all()
            if verbose:
                _logger.info("Closed HTTP client pools")
        except Exception:
            _logger.exception("Error closing HTTP client pools")
```

### 3. Provider Integration

#### Voyage AI Provider

**File**: `src/codeweaver/providers/embedding/providers/voyage.py`

```python
def __init__(
    self,
    client: AsyncClient | None = None,
    caps: EmbeddingModelCapabilities | None = None,
    **kwargs: Any,
) -> None:
    # ... validation logic ...

    if client is None:
        from codeweaver.common.http_pool import HttpClientPool
        from codeweaver.server.server import get_state

        # Get shared HTTP client from pool
        try:
            state = get_state()
            httpx_client = state.http_pool.get_client(
                'voyage',
                max_connections=50,  # Voyage-specific limits
                read_timeout=90.0,   # Longer for embedding operations
            )
        except Exception:
            # Fallback if state not initialized (e.g., during testing)
            httpx_client = None

        if api_key := kwargs.pop("api_key", None) or os.getenv("VOYAGE_API_KEY"):
            if isinstance(api_key, SecretStr):
                api_key = api_key.get_secret_value()
            client = AsyncClient(
                api_key=api_key,
                httpx_client=httpx_client  # Use pooled client
            )
        else:
            client = AsyncClient(httpx_client=httpx_client)

    # ... rest of initialization ...
```

#### Cohere Provider

**File**: `src/codeweaver/providers/embedding/providers/cohere.py`

```python
def __init__(
    self,
    client: CohereClient | None = None,
    caps: EmbeddingModelCapabilities | None = None,
    **kwargs: Any,
) -> None:
    # ... validation ...

    if not client:
        from codeweaver.common.http_pool import HttpClientPool
        from codeweaver.server.server import get_state

        try:
            state = get_state()
            httpx_client = state.http_pool.get_client(
                'cohere',
                max_connections=50,
                read_timeout=90.0,
            )
        except Exception:
            httpx_client = None

        client_options = kwargs.get("client_options", {})
        client_options['httpx_client'] = httpx_client

        api_key = # ... existing API key logic ...
        client = CohereClient(api_key=api_key, **client_options)

    # ... rest of initialization ...
```

#### Qdrant Provider

**File**: `src/codeweaver/providers/vector_stores/qdrant_base.py`

```python
def __post_init__(self) -> None:
    """Initialize the Qdrant client with connection pooling."""
    from codeweaver.common.http_pool import HttpClientPool
    from codeweaver.server.server import get_state

    # Get pooled HTTP client for Qdrant
    try:
        state = get_state()
        httpx_client = state.http_pool.get_client(
            'qdrant',
            max_connections=30,  # Conservative for vector store
            read_timeout=120.0,  # Very long for large upserts
            keepalive_expiry=30.0,  # Longer keepalive for Qdrant
        )
    except Exception:
        httpx_client = None

    # qdrant_client doesn't expose httpx_client parameter directly
    # We need to pass timeout configs instead
    timeout_config = {
        'timeout': 120.0,  # Overall timeout
    }

    self._client = AsyncQdrantClient(
        **self._get_client_kwargs(),
        **timeout_config,
    )
```

---

## Configuration

Add HTTP pool settings to configuration:

**File**: `src/codeweaver/config/settings.py`

```python
@dataclass
class HttpPoolSettings:
    """HTTP client pool configuration."""
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: float = 5.0
    connect_timeout: float = 10.0
    read_timeout: float = 60.0
    write_timeout: float = 10.0
    pool_timeout: float = 5.0
    enable_http2: bool = True

class CodeWeaverSettings(BasedModel):
    # ... existing fields ...
    http_pool: HttpPoolSettings = Field(default_factory=HttpPoolSettings)
```

---

## Benefits

### 1. **Performance Improvements**
- ✅ **Reduced Latency**: Reuse existing connections (save ~100-300ms per request)
- ✅ **Better Throughput**: HTTP/2 multiplexing allows multiple requests over single connection
- ✅ **Lower CPU**: Avoid repeated TLS handshakes

### 2. **Reliability Improvements**
- ✅ **Fixes Qdrant Errors**: Connection pool prevents httpcore.ReadError from exhaustion
- ✅ **Predictable Resource Usage**: Bounded connection limits prevent resource exhaustion
- ✅ **Graceful Degradation**: Pool timeouts prevent cascading failures

### 3. **Operational Benefits**
- ✅ **Centralized Control**: Single point for HTTP configuration
- ✅ **Observable**: Can add metrics on pool usage
- ✅ **Configurable**: Per-provider tuning based on API characteristics

---

## Migration Strategy

### Phase 1: Infrastructure (Week 1)
1. Create `HttpClientPool` class
2. Add to `CodeWeaverState`
3. Add cleanup to lifespan
4. Add configuration settings

### Phase 2: Provider Integration (Week 2)
1. Update Voyage AI provider
2. Update Cohere provider
3. Update Qdrant provider (if possible)
4. Fallback handling for standalone usage

### Phase 3: Testing & Tuning (Week 3)
1. Load testing with large repos
2. Monitor connection pool metrics
3. Tune limits per provider
4. Document performance improvements

### Phase 4: Advanced Features (Future)
1. Add pool metrics endpoint
2. Dynamic pool sizing based on load
3. Per-operation timeout overrides
4. Connection health monitoring

---

## Testing Plan

### Unit Tests
```python
async def test_http_pool_singleton():
    pool1 = HttpClientPool.get_instance()
    pool2 = HttpClientPool.get_instance()
    assert pool1 is pool2

async def test_client_reuse():
    pool = HttpClientPool()
    client1 = pool.get_client('test')
    client2 = pool.get_client('test')
    assert client1 is client2

async def test_cleanup():
    pool = HttpClientPool()
    client = pool.get_client('test')
    await pool.close_all()
    # Verify client is closed
```

### Integration Tests
```python
async def test_voyage_with_pooling():
    # Index large repo and verify connection reuse
    # Monitor metrics for connection count
    pass

async def test_qdrant_stability():
    # Run prolonged indexing
    # Verify no httpcore.ReadError occurs
    pass
```

### Load Tests
- Index 10K+ files concurrently
- Monitor connection pool metrics
- Verify no connection exhaustion
- Measure latency improvements

---

## Monitoring & Metrics

### Pool Metrics to Track
```python
class PoolMetrics:
    active_connections: int
    idle_connections: int
    total_requests: int
    connection_timeouts: int
    pool_exhaustions: int
```

### Health Endpoint Integration
Add to `/health` endpoint:
```json
{
  "http_pools": {
    "voyage": {
      "active": 5,
      "idle": 15,
      "total_requests": 1523,
      "timeouts": 0
    },
    "cohere": {...},
    "qdrant": {...}
  }
}
```

---

## Risks & Mitigations

### Risk 1: Breaking Changes
**Impact**: Providers might not work with pooled clients
**Mitigation**:
- Fallback to non-pooled clients if state unavailable
- Extensive testing before rollout
- Feature flag for gradual rollout

### Risk 2: Connection Leaks
**Impact**: Connections not properly closed
**Mitigation**:
- Explicit cleanup in lifespan
- Context manager pattern
- Connection leak detection in tests

### Risk 3: Provider API Changes
**Impact**: New versions might change client APIs
**Mitigation**:
- Pin library versions
- Version compatibility testing
- Graceful degradation

---

## Alternative Approaches Considered

### 1. **Per-Provider Pools** (Rejected)
Each provider manages its own pool - lacks centralization

### 2. **Global httpx Client** (Rejected)
Single client for all providers - loses per-provider tuning

### 3. **Connection Pool Proxy** (Overkill)
Dedicated connection pooling service - too complex for current needs

---

## References

- **httpx Pooling**: https://www.python-httpx.org/advanced/#pool-limit-configuration
- **Voyage AI Client**: https://github.com/voyage-ai/voyage-python-client
- **Cohere SDK**: https://github.com/cohere-ai/cohere-python
- **Qdrant Client**: https://github.com/qdrant/qdrant-client

---

## Next Steps

1. Review this document with team
2. Create implementation issues
3. Set up development branch
4. Begin Phase 1 implementation
5. Set up monitoring infrastructure
