# Idiomatic Python Patterns for Embedding Registry/Deduplication

**Research Date**: 2026-01-28
**Context**: CodeWeaver embedding provider architecture optimization

## Executive Summary

This document analyzes 5 idiomatic Python patterns for managing embedding registry, deduplication, and async caching in CodeWeaver's embedding providers. Current architecture uses per-instance `UUIDStore` and `BlakeStore` objects. Research focuses on FastAPI/Pydantic ecosystem patterns suitable for async, multi-provider scenarios.

---

## Current Architecture Analysis

**Data Flow**:
```
CodeChunk → hash_store (dedup check) → _store (batch cache) → registry (final storage)
```

**Current Implementation**:
- Per-instance stores: Each `EmbeddingProvider` has `_store: UUIDStore[list]` (3MB) and `_hash_store: BlakeStore[UUID7]` (256KB)
- Global registry: `EmbeddingRegistry: UUIDStore[ChunkEmbeddings]` (100MB)
- WeakValueDictionary trash heap for LRU-style eviction
- Thread-safe with Lock primitives
- Size-based eviction (not time-based)

**Pain Points**:
- Memory duplication across provider instances
- No TTL/time-based expiration
- Manual lock management
- Limited async optimization
- Per-instance stores don't share deduplication data

---

## Pattern 1: FastAPI Dependency Injection with Singleton Lifespan

**Pattern Name**: Application-Scoped Singleton Registry with DI

**Description**: Use FastAPI's dependency injection system with singleton scope to create shared, application-lifetime registry instances. Leverage `contextlib.asynccontextmanager` for proper async initialization and cleanup.

**How It Applies**:
- Single `EmbeddingRegistry` instance shared across all provider instances
- Proper async initialization via `@asynccontextmanager` lifespan
- Type-safe dependency injection using `Annotated[EmbeddingRegistry, Depends()]`
- Natural integration with existing FastMCP/FastAPI architecture

**Code Example**:
```python
from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import Depends, FastAPI
from collections.abc import AsyncIterator

# Global state for singleton
_registry: EmbeddingRegistry | None = None
_hash_registry: BlakeStore[UUID7] | None = None

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, Any]]:
    """Manage embedding registry lifecycle."""
    global _registry, _hash_registry

    # Startup: Initialize registries
    _registry = EmbeddingRegistry(size_limit=100 * 1024 * 1024)
    _hash_registry = BlakeStore[UUID7](
        value_type=UUID7,
        size_limit=256 * 1024
    )

    yield {
        "registry": _registry,
        "hash_registry": _hash_registry,
    }

    # Shutdown: Cleanup (persist if needed)
    if _registry:
        await _registry.save_async()  # if we add async save
    _registry = None
    _hash_registry = None

app = FastAPI(lifespan=lifespan)

# Dependency provider
async def get_embedding_registry() -> EmbeddingRegistry:
    """Get the singleton embedding registry."""
    if _registry is None:
        raise RuntimeError("Registry not initialized")
    return _registry

async def get_hash_store() -> BlakeStore[UUID7]:
    """Get the singleton hash store for deduplication."""
    if _hash_registry is None:
        raise RuntimeError("Hash store not initialized")
    return _hash_registry

# Type aliases for cleaner signatures
EmbeddingRegistryDep = Annotated[EmbeddingRegistry, Depends(get_embedding_registry)]
HashStoreDep = Annotated[BlakeStore[UUID7], Depends(get_hash_store)]

# Usage in provider
class EmbeddingProvider:
    def __init__(
        self,
        registry: EmbeddingRegistryDep,
        hash_store: HashStoreDep,
    ):
        self.registry = registry
        self.hash_store = hash_store
```

**Pros**:
- Natural fit with existing FastAPI/FastMCP architecture
- Singleton pattern enforced by framework
- Clean async initialization and teardown
- Type-safe with Depends() and Annotated
- Shared state across all provider instances (solves duplication)
- Framework handles lifecycle management

**Cons**:
- Requires refactoring from per-instance to singleton model
- Global state management (though controlled by framework)
- Slightly more complex initialization sequence
- Need to ensure thread-safety for any non-async access

**Async Compatibility**: ✅ Excellent
- Native async context manager support
- Async dependencies fully supported
- Can add async `save()` methods for persistence
- Event loop aware by design

---

## Pattern 2: AsyncIO Lock with TTL-Based asyncio.Cache

**Pattern Name**: Async TTL Cache with Content Addressing

**Description**: Use `asyncio` primitives (`asyncio.Lock`) for async-safe locking combined with a TTL-based cache implementation. Content-addressed deduplication using Blake3 hashes as cache keys.

**How It Applies**:
- Replace thread locks with `asyncio.Lock` for async safety
- Add TTL expiration to complement size-based eviction
- Use Blake3 hash as primary cache key (content addressing)
- Batch cache expires after N minutes, dedup cache persists longer

**Code Example**:
```python
import asyncio
from datetime import datetime, timedelta
from typing import Generic, TypeVar
from dataclasses import dataclass

T = TypeVar('T')

@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with TTL support."""
    value: T
    expires_at: datetime
    access_count: int = 0

    def is_expired(self) -> bool:
        return datetime.now() >= self.expires_at

class AsyncTTLCache(Generic[T]):
    """Async-safe TTL cache with size limits."""

    def __init__(
        self,
        max_size: int,
        default_ttl: timedelta = timedelta(minutes=30)
    ):
        self._cache: dict[str, CacheEntry[T]] = {}
        self._lock = asyncio.Lock()
        self._max_size = max_size
        self._default_ttl = default_ttl

    async def get(self, key: str) -> T | None:
        """Get value from cache, return None if expired or missing."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None

            if entry.is_expired():
                del self._cache[key]
                return None

            entry.access_count += 1
            return entry.value

    async def set(
        self,
        key: str,
        value: T,
        ttl: timedelta | None = None
    ) -> None:
        """Set value in cache with TTL."""
        async with self._lock:
            expires_at = datetime.now() + (ttl or self._default_ttl)

            # Make room if needed (LRU eviction)
            if len(self._cache) >= self._max_size and key not in self._cache:
                await self._evict_one()

            self._cache[key] = CacheEntry(
                value=value,
                expires_at=expires_at
            )

    async def _evict_one(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return

        # Find entry with lowest access count
        lru_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].access_count
        )
        del self._cache[lru_key]

    async def cleanup_expired(self) -> int:
        """Remove expired entries, return count removed."""
        async with self._lock:
            before = len(self._cache)
            self._cache = {
                k: v for k, v in self._cache.items()
                if not v.is_expired()
            }
            return before - len(self._cache)

# Usage in embedding provider
class AsyncEmbeddingProvider:
    def __init__(self):
        # Short TTL for batch cache (working memory)
        self.batch_cache = AsyncTTLCache[list[CodeChunk]](
            max_size=100,
            default_ttl=timedelta(minutes=10)
        )

        # Long TTL for deduplication (persistence)
        self.dedup_cache = AsyncTTLCache[UUID7](
            max_size=10000,
            default_ttl=timedelta(hours=24)
        )

    async def embed_chunks(
        self,
        chunks: Sequence[CodeChunk]
    ) -> list[ChunkEmbeddings]:
        """Embed chunks with deduplication."""
        results = []

        for chunk in chunks:
            # Check dedup cache
            content_hash = get_blake_hash(chunk.content.encode()).hexdigest()
            cached_id = await self.dedup_cache.get(content_hash)

            if cached_id:
                # Already embedded, reuse
                results.append(await self.registry.get(cached_id))
            else:
                # New content, embed it
                embedding = await self._embed_single(chunk)
                results.append(embedding)

                # Cache for deduplication
                await self.dedup_cache.set(content_hash, embedding.chunk_id)

        return results
```

**Pros**:
- Async-native locking (no blocking)
- TTL adds time-based eviction to complement size limits
- Content addressing via Blake3 enables true deduplication
- Can have different TTLs for different cache types
- Background cleanup task can run periodically
- More predictable memory usage with TTL

**Cons**:
- Requires refactoring from sync to async locks
- Additional complexity with TTL management
- Need background task for cleanup
- DateTime comparisons have overhead
- Loss of WeakValueDictionary benefits

**Async Compatibility**: ✅ Excellent
- Built on `asyncio.Lock` primitives
- No blocking operations
- Can integrate with async background tasks
- Natural async/await patterns throughout

---

## Pattern 3: Decorator-Based Caching with functools.cache/lru_cache

**Pattern Name**: Async LRU Cache Decorator with Content Hashing

**Description**: Use Python's standard library caching decorators, extended for async support. Combine with content hashing for deduplication. This is the most "Pythonic" approach using stdlib patterns.

**How It Applies**:
- Decorator pattern for embedding methods
- Content hash as cache key (hashable)
- Automatic cache invalidation via LRU
- Can extend `functools.lru_cache` for async

**Code Example**:
```python
import functools
import asyncio
from typing import Callable, TypeVar, ParamSpec, Awaitable
from collections.abc import Sequence

P = ParamSpec('P')
R = TypeVar('R')

def async_lru_cache(maxsize: int = 128):
    """Async version of functools.lru_cache."""
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        cache: dict[tuple, asyncio.Task[R]] = {}
        lock = asyncio.Lock()

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Create cache key from args (must be hashable)
            key = (args, tuple(sorted(kwargs.items())))

            async with lock:
                # Check if we have a cached task
                if key in cache:
                    task = cache[key]
                    # If task is done, return result
                    if task.done():
                        return task.result()
                    # If task is running, await it
                    return await task

                # Create new task for this call
                task = asyncio.create_task(func(*args, **kwargs))

                # Apply LRU eviction if needed
                if len(cache) >= maxsize:
                    # Remove oldest entry (first key)
                    first_key = next(iter(cache))
                    del cache[first_key]

                cache[key] = task

            return await task

        wrapper.cache_info = lambda: {
            "size": len(cache),
            "maxsize": maxsize,
        }
        wrapper.cache_clear = lambda: cache.clear()

        return wrapper
    return decorator

# Content-hash based deduplication decorator
def deduplicate_by_content(
    hash_func: Callable[[str], str] = lambda s: get_blake_hash(s.encode()).hexdigest()
):
    """Decorator that deduplicates function calls by content hash."""
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        cache: dict[str, R] = {}
        lock = asyncio.Lock()

        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # Assume first arg is content string
            content = args[0] if args else ""
            content_hash = hash_func(str(content))

            async with lock:
                if content_hash in cache:
                    return cache[content_hash]

                result = await func(*args, **kwargs)
                cache[content_hash] = result
                return result

        wrapper.cache_clear = lambda: cache.clear()
        return wrapper
    return decorator

# Usage in embedding provider
class DecoratedEmbeddingProvider:

    @async_lru_cache(maxsize=100)
    @deduplicate_by_content()
    async def embed_text(self, text: str) -> list[float]:
        """Embed text with automatic caching and deduplication."""
        # Actual embedding logic
        response = await self.client.embed([text])
        return response[0]

    async def embed_chunks(
        self,
        chunks: Sequence[CodeChunk]
    ) -> list[ChunkEmbeddings]:
        """Embed chunks using decorated method."""
        results = []

        # Each call to embed_text is automatically cached/deduped
        for chunk in chunks:
            vector = await self.embed_text(chunk.content)
            embedding = ChunkEmbeddings(
                chunk_id=chunk.id,
                dense_vector=vector,
                dense_model=self.config.model
            )
            results.append(embedding)

        return results
```

**Pros**:
- Most "Pythonic" approach using stdlib patterns
- Clean, declarative API via decorators
- Familiar to Python developers
- Minimal boilerplate
- Standard `cache_info()` and `cache_clear()` methods
- Can compose multiple decorators for layered caching

**Cons**:
- No built-in async LRU cache in stdlib (need custom implementation)
- Function arguments must be hashable (can't cache by complex objects)
- Less control over eviction policy
- Harder to share cache across multiple methods/instances
- No size-based limits (only item count)
- WeakValueDictionary not easily integrated

**Async Compatibility**: ⚠️ Moderate
- Requires custom async implementation (stdlib `lru_cache` is sync only)
- Can wrap async functions but needs careful task management
- Must handle concurrent cache access
- Community libraries exist (e.g., `aiocache`, `async-lru`)

---

## Pattern 4: Context Manager Pattern for Cache Transactions

**Pattern Name**: Async Context Manager with Rollback Support

**Description**: Use context managers to provide transactional semantics for cache operations. Enables batch operations with rollback on failure and automatic cleanup.

**How It Applies**:
- Batch embedding operations within context
- Automatic rollback on failure
- Cleanup temporary batch storage
- Transaction-like semantics for multi-step operations

**Code Example**:
```python
from contextlib import asynccontextmanager
from typing import AsyncIterator
from dataclasses import dataclass, field

@dataclass
class CacheTransaction:
    """Represents a cache transaction with rollback support."""
    cache: 'EmbeddingCache'
    pending: dict[str, Any] = field(default_factory=dict)
    committed: list[str] = field(default_factory=list)

    async def add(self, key: str, value: Any) -> None:
        """Add item to transaction (not yet committed)."""
        self.pending[key] = value

    async def commit(self) -> None:
        """Commit all pending items to cache."""
        async with self.cache._lock:
            for key, value in self.pending.items():
                await self.cache._unsafe_set(key, value)
                self.committed.append(key)
            self.pending.clear()

    async def rollback(self) -> None:
        """Rollback transaction, remove committed items."""
        async with self.cache._lock:
            for key in self.committed:
                await self.cache._unsafe_delete(key)
            self.committed.clear()
            self.pending.clear()

class EmbeddingCache:
    """Async cache with transaction support."""

    def __init__(self):
        self._cache: dict[str, Any] = {}
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[CacheTransaction]:
        """Create a cache transaction with automatic rollback on error."""
        txn = CacheTransaction(cache=self)
        try:
            yield txn
            await txn.commit()
        except Exception:
            await txn.rollback()
            raise

    async def _unsafe_set(self, key: str, value: Any) -> None:
        """Set value without lock (for internal use)."""
        self._cache[key] = value

    async def _unsafe_delete(self, key: str) -> None:
        """Delete value without lock (for internal use)."""
        if key in self._cache:
            del self._cache[key]

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        async with self._lock:
            return self._cache.get(key)

# Usage in embedding provider
class TransactionalEmbeddingProvider:
    def __init__(self):
        self.cache = EmbeddingCache()
        self.registry = EmbeddingRegistry()

    async def embed_batch_transactional(
        self,
        chunks: Sequence[CodeChunk]
    ) -> list[ChunkEmbeddings]:
        """Embed batch with transactional cache semantics."""
        results = []

        async with self.cache.transaction() as txn:
            # Process batch
            for chunk in chunks:
                content_hash = get_blake_hash(chunk.content.encode()).hexdigest()

                # Try cache first
                cached = await self.cache.get(content_hash)
                if cached:
                    results.append(cached)
                    continue

                # Embed new content
                embedding = await self._embed_single(chunk)
                results.append(embedding)

                # Add to transaction (will commit at end)
                await txn.add(content_hash, embedding)

            # Validate all embeddings
            if not self._validate_embeddings(results):
                raise ValueError("Invalid embeddings detected")

            # Context manager commits here
            # If validation failed, rollback is automatic

        return results

    async def embed_batch_with_cleanup(
        self,
        chunks: Sequence[CodeChunk]
    ) -> list[ChunkEmbeddings]:
        """Embed batch with automatic temporary storage cleanup."""
        batch_id = uuid7()

        async with self._batch_context(batch_id) as batch_store:
            # Store batch temporarily
            await batch_store.add(batch_id, chunks)

            # Process embeddings
            results = await self._process_batch(chunks)

            # Register results
            for result in results:
                await self.registry.add(result.chunk_id, result)

            # Cleanup happens automatically on context exit

        return results

    @asynccontextmanager
    async def _batch_context(
        self,
        batch_id: UUID7
    ) -> AsyncIterator[dict]:
        """Context manager for temporary batch storage."""
        temp_store = {}
        try:
            yield temp_store
        finally:
            # Cleanup temporary storage
            temp_store.clear()
```

**Pros**:
- Transactional semantics (all-or-nothing)
- Automatic cleanup on success or failure
- Clear resource lifecycle boundaries
- Natural error handling via context manager
- Familiar Python pattern
- Can nest contexts for complex operations

**Cons**:
- More complex than simple cache get/set
- Transaction overhead for simple operations
- Need to carefully design transaction boundaries
- Rollback can be expensive for large batches
- Lock contention during long transactions

**Async Compatibility**: ✅ Excellent
- Native async context manager support (`@asynccontextmanager`)
- Clean async/await patterns
- Can integrate with other async primitives
- Proper exception handling with async

---

## Pattern 5: Pydantic BaseModel with Computed Fields for Cache

**Pattern Name**: Pydantic-Native Cache with Validation

**Description**: Leverage Pydantic's `BaseModel` with `computed_field` and validators to create type-safe, self-validating cache structures. Uses Pydantic's ecosystem patterns naturally.

**How It Applies**:
- Cache is a Pydantic model with validation
- Computed fields for derived values (hit rate, etc.)
- Type-safe with Pydantic v2 features
- JSON serialization built-in for persistence

**Code Example**:
```python
from pydantic import BaseModel, Field, computed_field, field_validator
from typing import Generic, TypeVar
from datetime import datetime
from collections import OrderedDict

T = TypeVar('T')

class CacheEntry(BaseModel, Generic[T]):
    """Type-safe cache entry with Pydantic validation."""
    key: str
    value: T
    created_at: datetime = Field(default_factory=datetime.now)
    access_count: int = 0
    last_accessed: datetime = Field(default_factory=datetime.now)

    model_config = {"arbitrary_types_allowed": True}

    def touch(self) -> None:
        """Update access metadata."""
        self.access_count += 1
        self.last_accessed = datetime.now()

class PydanticCache(BaseModel, Generic[T]):
    """Type-safe async cache using Pydantic models."""

    entries: OrderedDict[str, CacheEntry[T]] = Field(
        default_factory=OrderedDict
    )
    max_size: int = Field(default=1000, gt=0)
    hits: int = Field(default=0, ge=0)
    misses: int = Field(default=0, ge=0)

    model_config = {
        "arbitrary_types_allowed": True,
        "validate_assignment": True
    }

    _lock: asyncio.Lock = None  # Set in __init__

    def __init__(self, **data):
        super().__init__(**data)
        object.__setattr__(self, '_lock', asyncio.Lock())

    @computed_field
    @property
    def hit_rate(self) -> float:
        """Compute cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @computed_field
    @property
    def size(self) -> int:
        """Current cache size."""
        return len(self.entries)

    @computed_field
    @property
    def is_full(self) -> bool:
        """Check if cache is at capacity."""
        return len(self.entries) >= self.max_size

    @field_validator('max_size')
    @classmethod
    def validate_max_size(cls, v: int) -> int:
        """Ensure max_size is reasonable."""
        if v > 100_000:
            raise ValueError("max_size too large")
        return v

    async def get(self, key: str) -> T | None:
        """Get value from cache with stats tracking."""
        async with self._lock:
            entry = self.entries.get(key)

            if entry is None:
                self.misses += 1
                return None

            entry.touch()
            self.hits += 1

            # Move to end (LRU)
            self.entries.move_to_end(key)

            return entry.value

    async def set(self, key: str, value: T) -> None:
        """Set value in cache with LRU eviction."""
        async with self._lock:
            # Remove oldest if full
            if self.is_full and key not in self.entries:
                self.entries.popitem(last=False)

            # Add/update entry
            entry = CacheEntry(key=key, value=value)
            self.entries[key] = entry
            self.entries.move_to_end(key)

    async def clear(self) -> None:
        """Clear cache and reset stats."""
        async with self._lock:
            self.entries.clear()
            self.hits = 0
            self.misses = 0

    def save(self, path: str) -> None:
        """Save cache to JSON file."""
        with open(path, 'w') as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, path: str) -> 'PydanticCache[T]':
        """Load cache from JSON file."""
        with open(path, 'r') as f:
            return cls.model_validate_json(f.read())

# Usage with CodeWeaver's existing Pydantic patterns
class EmbeddingCacheManager(BaseModel):
    """Manages multiple caches for embeddings."""

    dedup_cache: PydanticCache[UUID7] = Field(
        default_factory=lambda: PydanticCache[UUID7](max_size=10000)
    )
    batch_cache: PydanticCache[list] = Field(
        default_factory=lambda: PydanticCache[list](max_size=100)
    )

    model_config = {"arbitrary_types_allowed": True}

    @computed_field
    @property
    def overall_hit_rate(self) -> float:
        """Compute overall hit rate across all caches."""
        total_hits = self.dedup_cache.hits + self.batch_cache.hits
        total_ops = (
            self.dedup_cache.hits + self.dedup_cache.misses +
            self.batch_cache.hits + self.batch_cache.misses
        )
        return total_hits / total_ops if total_ops > 0 else 0.0

    async def check_deduplication(
        self,
        content_hash: str
    ) -> UUID7 | None:
        """Check if content has been embedded before."""
        return await self.dedup_cache.get(content_hash)

    async def register_embedding(
        self,
        content_hash: str,
        embedding_id: UUID7
    ) -> None:
        """Register embedding for deduplication."""
        await self.dedup_cache.set(content_hash, embedding_id)
```

**Pros**:
- Perfect fit with CodeWeaver's Pydantic ecosystem
- Type-safe with Pydantic v2 validation
- Built-in JSON serialization for persistence
- Computed fields for metrics (hit rate, etc.)
- Validation ensures data integrity
- Natural integration with existing `BasedModel` patterns
- Can use Pydantic's `ConfigDict` for customization

**Cons**:
- Pydantic overhead for validation (may be unnecessary for cache)
- OrderedDict not as efficient as pure dict for very large caches
- Need to mark `_lock` as private (not serialized)
- Validation on every assignment can be slow
- Generic typing with Pydantic can be tricky

**Async Compatibility**: ✅ Good
- Pydantic models are sync but methods can be async
- Can integrate with async locks
- Serialization is sync (but fast)
- Works well with async application patterns

---

## Comparison Matrix

| Pattern | Async Support | Memory Efficiency | Code Complexity | FastAPI Integration | Pydantic Integration |
|---------|--------------|-------------------|-----------------|---------------------|---------------------|
| **1. DI Singleton** | ✅ Excellent | ⭐⭐⭐⭐ | ⭐⭐⭐ | ✅ Native | ✅ Natural |
| **2. Async TTL Cache** | ✅ Excellent | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⚠️ Manual | ⚠️ Manual |
| **3. Decorator Cache** | ⚠️ Moderate | ⭐⭐⭐ | ⭐⭐ | ⚠️ Manual | ⚠️ Manual |
| **4. Context Manager** | ✅ Excellent | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⚠️ Manual | ⚠️ Manual |
| **5. Pydantic Cache** | ✅ Good | ⭐⭐⭐ | ⭐⭐⭐ | ✅ Natural | ✅ Perfect |

---

## Recommendation for CodeWeaver

**Primary Recommendation: Hybrid Pattern 1 + Pattern 5**

Combine FastAPI dependency injection (Pattern 1) with Pydantic-based cache (Pattern 5):

```python
# Pydantic cache implementation
class EmbeddingCache(BaseModel):
    dedup_store: PydanticCache[UUID7]
    batch_store: PydanticCache[list]

    @computed_field
    @property
    def statistics(self) -> dict:
        return {
            "dedup_hit_rate": self.dedup_store.hit_rate,
            "batch_hit_rate": self.batch_store.hit_rate,
        }

# FastAPI lifespan with DI
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cache
    _cache = EmbeddingCache(
        dedup_store=PydanticCache[UUID7](max_size=10000),
        batch_store=PydanticCache[list](max_size=100)
    )
    yield {"cache": _cache}
    await _cache.save_async()

# Dependency provider
async def get_cache() -> EmbeddingCache:
    return _cache

CacheDep = Annotated[EmbeddingCache, Depends(get_cache)]

# Provider uses injected cache
class EmbeddingProvider:
    def __init__(self, cache: CacheDep):
        self.cache = cache
```

**Why This Combination?**
1. **Perfect ecosystem fit**: FastAPI + Pydantic = CodeWeaver's stack
2. **Type safety**: Full Pydantic validation and type checking
3. **Singleton pattern**: Shared cache across all providers
4. **Observable**: Computed fields provide metrics
5. **Serializable**: Built-in JSON persistence
6. **Async-safe**: Native async support with locks

**Secondary Recommendation: Pattern 2 for Advanced Scenarios**

If TTL-based expiration is needed:
- Add TTL support to Pattern 5 (Pydantic cache)
- Use Pattern 2's TTL logic within Pydantic models
- Background task for cleanup

---

## Implementation Roadmap

**Phase 1: Refactor to Singleton**
- Move per-instance stores to singleton pattern
- Implement FastAPI lifespan management
- Add dependency injection for cache

**Phase 2: Add Pydantic Cache**
- Create `PydanticCache[T]` base class
- Implement `EmbeddingCache` with dedup + batch stores
- Add computed fields for metrics

**Phase 3: Enhance with TTL (Optional)**
- Add TTL support to `CacheEntry`
- Implement background cleanup task
- Add TTL configuration per cache type

**Phase 4: Optimize for Async**
- Profile lock contention
- Consider read-write locks for high concurrency
- Add async save/load methods

---

## Additional Resources

### Libraries to Consider
- **`aiocache`**: Async caching library with multiple backends
- **`async-lru`**: Async LRU cache decorator
- **`cachetools`**: TTL and LRU caches (sync, but patterns applicable)
- **`cashews`**: Async cache with decorators and TTL

### FastAPI Patterns
- Official docs: [Advanced Dependencies](https://fastapi.tiangolo.com/advanced/advanced-dependencies/)
- Singleton pattern: [Application State](https://fastapi.tiangolo.com/deployment/concepts/)
- Lifespan events: [Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)

### Pydantic Patterns
- Computed fields: [Pydantic v2 Computed Fields](https://docs.pydantic.dev/latest/concepts/fields/#computed-fields)
- Generic models: [Generic Models](https://docs.pydantic.dev/latest/concepts/models/#generic-models)
- Validators: [Field Validators](https://docs.pydantic.dev/latest/concepts/validators/)

---

## Conclusion

The recommended hybrid approach (Pattern 1 + 5) provides:
- **Idiomatic Python**: Uses FastAPI and Pydantic ecosystem patterns
- **Async-first**: Native async support throughout
- **Type-safe**: Full Pydantic validation
- **Observable**: Built-in metrics and monitoring
- **Maintainable**: Clear separation of concerns
- **Performant**: Singleton eliminates duplication, LRU provides efficiency

This approach requires moderate refactoring but provides significant benefits in memory efficiency, observability, and maintainability while staying true to CodeWeaver's architectural principles and Python best practices.
