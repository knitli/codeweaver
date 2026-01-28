<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Embedding Registry Alternative Architectures

**Date**: 2026-01-28
**Purpose**: Propose alternative architectures for the embedding registry/deduplication system
**Status**: Architecture Proposals - Ready for Review

---

## Executive Summary

This document proposes **three alternative architectures** to replace the current three-layer embedding registry system (`Provider._hash_store → Provider._store → EmbeddingRegistry`). Each architecture addresses the core issues:

1. **ClassVar state management** causing shared state between provider instances
2. **Async concurrent embedding generation** requiring proper coordination
3. **Deduplication across multiple providers** without race conditions
4. **Temporary batch storage** for error recovery/retry
5. **FastMCP dependency injection** integration

**Current Architecture Issues**:
- Three layers of storage (hash dedup, batch cache, final registry)
- ClassVar stores shared across instances
- Complex lifecycle management
- Difficult to reason about state

**Recommendation**: **Architecture 2 (Centralized Cache Manager)** provides the best balance of simplicity, async safety, and DI integration.

---

## Current Architecture (Baseline)

### Three-Layer Structure

```
┌─────────────────────────────────────────────────────────────┐
│ Provider Instance (ClassVar stores - shared!)               │
│                                                               │
│  _hash_store: BlakeStore[UUID7]                             │
│    Purpose: Deduplication by content hash                   │
│    Keys: blake3(chunk.content) → batch_id                   │
│    Size: 256KB                                               │
│                                                               │
│  _store: UUIDStore[list[CodeChunk]]                         │
│    Purpose: Temporary batch cache                           │
│    Keys: batch_id → list of chunks                          │
│    Size: 3MB                                                 │
│                                                               │
└───────────────────────────────────────┬─────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────┐
│ EmbeddingRegistry (DI Singleton)                            │
│                                                               │
│  store: dict[UUID7, ChunkEmbeddings]                        │
│    Purpose: Final embedding storage                         │
│    Keys: chunk_id → embeddings + metadata                  │
│    Size: 100MB                                               │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. embed_documents(chunks) called
2. _process_input():
   - Hash each chunk content
   - Check _hash_store for duplicates
   - Store new chunks in _store with batch_id
   - Add hashes to _hash_store
3. _embed_documents_with_retry():
   - Call provider API
   - Get embeddings back
4. _register_chunks():
   - Store in EmbeddingRegistry
   - Create ChunkEmbeddings objects
```

### Problems

1. **ClassVar Pollution**: `_hash_store` and `_store` are ClassVars, causing:
   - Shared state across all provider instances
   - Dense/sparse providers can collide
   - Testing requires manual cleanup
   - Thread safety concerns

2. **Complexity**: Three layers for what could be simpler:
   - Hard to trace data flow
   - Unclear ownership boundaries
   - Difficult error recovery

3. **Async Coordination**: No explicit async locking:
   - Concurrent embeddings may race
   - Deduplication can miss duplicates in flight

4. **DI Integration**: Manual instance creation, not DI-managed

---

## Architecture 1: Repository Pattern with Async Context Managers

### High-Level Architecture

```
┌────────────────────────────────────────────────────────────┐
│ EmbeddingRepository (DI Singleton, async-aware)            │
│                                                              │
│  Responsibilities:                                          │
│  - Deduplication (content hash → batch_id)                │
│  - Batch tracking (batch_id → chunks)                      │
│  - Final storage (chunk_id → embeddings)                   │
│  - Async locking per operation                             │
│                                                              │
│  Internal Structure:                                        │
│    _dedup: dict[BlakeHashKey, UUID7]  # hash → batch_id   │
│    _batches: dict[UUID7, list[CodeChunk]]  # batch cache  │
│    _embeddings: dict[UUID7, ChunkEmbeddings]  # final     │
│    _locks: dict[str, asyncio.Lock]  # per-operation       │
│                                                              │
└────────────────────────────────────────────────────────────┘
         ▲                           ▲
         │                           │
┌────────┴─────────┐    ┌───────────┴──────────┐
│ VoyageProvider    │    │ JinaProvider          │
│ (stateless)       │    │ (stateless)           │
│                   │    │                       │
│ Uses:             │    │ Uses:                 │
│ - repo.register() │    │ - repo.register()     │
│ - repo.batch()    │    │ - repo.batch()        │
│ - repo.dedupe()   │    │ - repo.dedupe()       │
└───────────────────┘    └───────────────────────┘
```

### Key Components

```python
# src/codeweaver/providers/embedding/repository.py

from asyncio import Lock
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Self

from pydantic import UUID7
from codeweaver.core import BlakeHashKey, CodeChunk, ChunkEmbeddings, uuid7, get_blake_hash

class EmbeddingBatch:
    """Context manager for batch operations with automatic cleanup."""

    def __init__(self, repo: EmbeddingRepository, chunks: list[CodeChunk]):
        self.repo = repo
        self.chunks = chunks
        self.batch_id = uuid7()
        self._deduplicated: list[CodeChunk] = []

    async def __aenter__(self) -> tuple[UUID7, list[CodeChunk]]:
        """Enter batch context: deduplicate and register chunks."""
        async with self.repo._get_lock("dedup"):
            for chunk in self.chunks:
                hash_key = get_blake_hash(chunk.content.encode("utf-8"))
                if hash_key not in self.repo._dedup:
                    self.repo._dedup[hash_key] = self.batch_id
                    self._deduplicated.append(chunk)

        # Store batch for recovery
        async with self.repo._get_lock(f"batch:{self.batch_id.hex}"):
            self.repo._batches[self.batch_id] = self._deduplicated

        return self.batch_id, self._deduplicated

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit batch context: cleanup or preserve based on success."""
        if exc_type is None:
            # Success: can remove batch cache (already in final registry)
            async with self.repo._get_lock(f"batch:{self.batch_id.hex}"):
                self.repo._batches.pop(self.batch_id, None)
        else:
            # Error: keep batch for retry
            pass


class EmbeddingRepository(BasedModel):
    """Centralized repository for embedding storage and deduplication.

    Replaces three-layer architecture with single coordinated repository.
    Async-safe with per-operation locking.
    """

    # Storage layers (all instance attributes, not ClassVar)
    _dedup: dict[BlakeHashKey, UUID7] = PrivateAttr(default_factory=dict)
    _batches: dict[UUID7, list[CodeChunk]] = PrivateAttr(default_factory=dict)
    _embeddings: dict[UUID7, ChunkEmbeddings] = PrivateAttr(default_factory=dict)

    # Async coordination
    _locks: dict[str, Lock] = PrivateAttr(default_factory=dict)
    _lock_lock: Lock = PrivateAttr(default_factory=Lock)  # Lock for getting locks!

    # Size limits
    dedup_limit: int = 256 * 1024  # 256KB for dedup hashes
    batch_limit: int = 3 * 1024 * 1024  # 3MB for batch cache
    embedding_limit: int = 100 * 1024 * 1024  # 100MB for embeddings

    async def _get_lock(self, key: str) -> Lock:
        """Get or create a lock for a specific operation key."""
        async with self._lock_lock:
            if key not in self._locks:
                self._locks[key] = Lock()
            return self._locks[key]

    @asynccontextmanager
    async def batch(self, chunks: list[CodeChunk]) -> AsyncIterator[tuple[UUID7, list[CodeChunk]]]:
        """Create a batch context for embedding operations.

        Usage:
            async with repo.batch(chunks) as (batch_id, deduplicated):
                embeddings = await provider.embed(deduplicated)
                await repo.register(batch_id, deduplicated, embeddings)
        """
        batch = EmbeddingBatch(self, chunks)
        async with batch as result:
            yield result

    async def register(
        self,
        batch_id: UUID7,
        chunks: list[CodeChunk],
        embeddings: list[list[float]],
        *,
        model: str,
        kind: str,
    ) -> None:
        """Register embeddings in final storage."""
        async with self._get_lock("embeddings"):
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
                if chunk.chunk_id not in self._embeddings:
                    self._embeddings[chunk.chunk_id] = ChunkEmbeddings(chunk=chunk)

                batch_info = EmbeddingBatchInfo(
                    batch_id=batch_id,
                    batch_index=i,
                    chunk_id=chunk.chunk_id,
                    model=model,
                    embeddings=embedding,
                    kind=kind,
                )
                self._embeddings[chunk.chunk_id] = self._embeddings[chunk.chunk_id].add(batch_info)

    async def get(self, chunk_id: UUID7) -> ChunkEmbeddings | None:
        """Get embeddings for a chunk."""
        async with self._get_lock("embeddings"):
            return self._embeddings.get(chunk_id)

    def clear_provider_caches(self) -> None:
        """Clear dedup and batch caches (for testing)."""
        self._dedup.clear()
        self._batches.clear()


# DI registration
@dependency_provider(EmbeddingRepository, scope="singleton")
def get_embedding_repository() -> EmbeddingRepository:
    return EmbeddingRepository()
```

### Provider Integration

```python
# src/codeweaver/providers/embedding/providers/base.py

class EmbeddingProvider[EmbeddingClient](BasedModel, ABC):
    """Stateless provider using centralized repository."""

    # Injected dependency (no ClassVar stores!)
    repository: Annotated[EmbeddingRepository, depends(get_embedding_repository)]

    async def embed_documents(
        self,
        documents: Sequence[CodeChunk],
        **kwargs: Any,
    ) -> list[list[float]] | EmbeddingErrorInfo:
        """Embed documents using repository for coordination."""

        # Use repository batch context
        async with self.repository.batch(list(documents)) as (batch_id, deduplicated):
            if not deduplicated:
                return []  # All duplicates

            try:
                # Call provider API
                results = await self._embed_documents_with_retry(deduplicated, **kwargs)

                # Register in repository
                await self.repository.register(
                    batch_id=batch_id,
                    chunks=deduplicated,
                    embeddings=results,
                    model=self.model_name,
                    kind="dense",
                )

                return results
            except Exception as e:
                # Batch preserved in repository for retry
                return self._handle_embedding_error(e, batch_id, deduplicated, None)
```

### Data Flow

```
1. Provider.embed_documents(chunks) called
2. async with repo.batch(chunks):
   a. Enter: Deduplicate via _dedup dict
   b. Enter: Store batch in _batches dict
   c. Yield: (batch_id, deduplicated_chunks)
3. Provider calls API with deduplicated chunks
4. Provider calls repo.register(batch_id, chunks, embeddings)
   a. Async lock on _embeddings
   b. Store ChunkEmbeddings objects
5. Exit batch context:
   a. Success: Remove from _batches
   b. Error: Keep in _batches for retry
```

### Migration Path

1. **Phase 1**: Create `EmbeddingRepository` with DI registration
2. **Phase 2**: Update `EmbeddingProvider` base class to inject repository
3. **Phase 3**: Remove ClassVar `_store` and `_hash_store` from providers
4. **Phase 4**: Update tests to use repository fixture

### Pros

✅ **Single source of truth**: One repository, clear ownership
✅ **Async-safe**: Explicit locking per operation
✅ **Stateless providers**: No ClassVar pollution
✅ **Clean context managers**: Automatic batch lifecycle
✅ **DI integration**: Repository is singleton, providers are instances
✅ **Clear error recovery**: Batches preserved on failure

### Cons

❌ **More boilerplate**: Context manager usage in every provider
❌ **Lock contention**: Could bottleneck on high concurrency
❌ **No weak references**: Lost `_trash_heap` recovery mechanism

---

## Architecture 2: Centralized Cache Manager (RECOMMENDED)

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ EmbeddingCacheManager (DI Singleton)                        │
│                                                               │
│  Namespaced caches per provider:                            │
│                                                               │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ voyage:dedup     │  │ jina:dedup       │                │
│  │ voyage:batches   │  │ jina:batches     │                │
│  └──────────────────┘  └──────────────────┘                │
│                                                               │
│  Shared final storage:                                      │
│  ┌──────────────────────────────────────┐                  │
│  │ embeddings: dict[UUID7, ChunkEmbed]  │                  │
│  └──────────────────────────────────────┘                  │
│                                                               │
│  Async coordination:                                        │
│    _namespace_locks: dict[str, asyncio.Lock]               │
│    _embedding_lock: asyncio.Lock                           │
│                                                               │
└─────────────────────────────────────────────────────────────┘
         ▲                           ▲
         │                           │
┌────────┴─────────┐    ┌───────────┴──────────┐
│ VoyageProvider    │    │ JinaProvider          │
│ (stateless)       │    │ (stateless)           │
│                   │    │                       │
│ namespace:        │    │ namespace:            │
│   "voyage"        │    │   "jina"              │
└───────────────────┘    └───────────────────────┘
```

### Key Components

```python
# src/codeweaver/providers/embedding/cache_manager.py

from asyncio import Lock
from collections.abc import Sequence
from typing import Literal

from pydantic import UUID7, PrivateAttr
from codeweaver.core import BasedModel, BlakeHashKey, CodeChunk, ChunkEmbeddings


class ProviderCache:
    """Namespaced cache for a specific provider."""

    def __init__(self, namespace: str):
        self.namespace = namespace
        self.dedup: dict[BlakeHashKey, UUID7] = {}
        self.batches: dict[UUID7, list[CodeChunk]] = {}

    def clear(self) -> None:
        """Clear this provider's caches."""
        self.dedup.clear()
        self.batches.clear()


class EmbeddingCacheManager(BasedModel):
    """Centralized cache manager with provider namespacing.

    Provides:
    - Deduplication per provider (prevents dense/sparse collisions)
    - Batch caching for error recovery
    - Shared final embedding storage
    - Async-safe operations with namespace locking
    """

    # Provider-specific caches (namespaced)
    _caches: dict[str, ProviderCache] = PrivateAttr(default_factory=dict)

    # Shared final storage
    _embeddings: dict[UUID7, ChunkEmbeddings] = PrivateAttr(default_factory=dict)

    # Async coordination
    _namespace_locks: dict[str, Lock] = PrivateAttr(default_factory=dict)
    _embedding_lock: Lock = PrivateAttr(default_factory=Lock)
    _meta_lock: Lock = PrivateAttr(default_factory=Lock)  # For creating locks/caches

    async def _get_namespace_lock(self, namespace: str) -> Lock:
        """Get or create lock for a provider namespace."""
        async with self._meta_lock:
            if namespace not in self._namespace_locks:
                self._namespace_locks[namespace] = Lock()
            return self._namespace_locks[namespace]

    async def _get_cache(self, namespace: str) -> ProviderCache:
        """Get or create cache for a provider namespace."""
        async with self._meta_lock:
            if namespace not in self._caches:
                self._caches[namespace] = ProviderCache(namespace)
            return self._caches[namespace]

    async def deduplicate(
        self,
        namespace: str,
        chunks: Sequence[CodeChunk],
        batch_id: UUID7,
    ) -> list[CodeChunk]:
        """Deduplicate chunks for a specific provider namespace.

        Returns only chunks that haven't been seen before in this namespace.
        Stores batch for potential recovery.
        """
        cache = await self._get_cache(namespace)
        lock = await self._get_namespace_lock(namespace)

        deduplicated: list[CodeChunk] = []

        async with lock:
            for chunk in chunks:
                hash_key = get_blake_hash(chunk.content.encode("utf-8"))

                if hash_key not in cache.dedup:
                    cache.dedup[hash_key] = batch_id
                    deduplicated.append(chunk)

            # Store batch for recovery
            if deduplicated:
                cache.batches[batch_id] = deduplicated

        return deduplicated

    async def register_embeddings(
        self,
        namespace: str,
        batch_id: UUID7,
        chunks: Sequence[CodeChunk],
        embeddings: Sequence[Sequence[float]],
        *,
        model: str,
        kind: Literal["dense", "sparse"],
    ) -> None:
        """Register embeddings in final storage.

        After successful registration, removes batch from cache.
        """
        async with self._embedding_lock:
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
                # Create or update ChunkEmbeddings
                if chunk.chunk_id not in self._embeddings:
                    self._embeddings[chunk.chunk_id] = ChunkEmbeddings(chunk=chunk)

                batch_info = EmbeddingBatchInfo(
                    batch_id=batch_id,
                    batch_index=i,
                    chunk_id=chunk.chunk_id,
                    model=model,
                    embeddings=embedding,
                    kind=kind,
                )

                self._embeddings[chunk.chunk_id] = self._embeddings[chunk.chunk_id].add(batch_info)

        # Remove batch from cache (success)
        cache = await self._get_cache(namespace)
        lock = await self._get_namespace_lock(namespace)
        async with lock:
            cache.batches.pop(batch_id, None)

    async def get_embeddings(self, chunk_id: UUID7) -> ChunkEmbeddings | None:
        """Get embeddings for a chunk."""
        async with self._embedding_lock:
            return self._embeddings.get(chunk_id)

    async def get_batch(self, namespace: str, batch_id: UUID7) -> list[CodeChunk] | None:
        """Retrieve cached batch for retry (error recovery)."""
        cache = await self._get_cache(namespace)
        lock = await self._get_namespace_lock(namespace)
        async with lock:
            return cache.batches.get(batch_id)

    async def clear_namespace(self, namespace: str) -> None:
        """Clear caches for a specific provider (testing)."""
        cache = await self._get_cache(namespace)
        lock = await self._get_namespace_lock(namespace)
        async with lock:
            cache.clear()

    def clear_all(self) -> None:
        """Clear all caches (testing)."""
        self._caches.clear()
        self._embeddings.clear()
        self._namespace_locks.clear()


# DI registration
@dependency_provider(EmbeddingCacheManager, scope="singleton")
def get_embedding_cache_manager() -> EmbeddingCacheManager:
    return EmbeddingCacheManager()
```

### Provider Integration

```python
# src/codeweaver/providers/embedding/providers/base.py

class EmbeddingProvider[EmbeddingClient](BasedModel, ABC):
    """Stateless provider using centralized cache manager."""

    # Injected dependency
    cache_manager: Annotated[
        EmbeddingCacheManager,
        depends(get_embedding_cache_manager)
    ]

    # Provider namespace (generated from provider name)
    @property
    def namespace(self) -> str:
        """Get provider namespace for cache isolation."""
        return f"{self._provider.variable}:{self.model_name}"

    async def embed_documents(
        self,
        documents: Sequence[CodeChunk],
        *,
        batch_id: UUID7 | None = None,
        skip_deduplication: bool = False,
        **kwargs: Any,
    ) -> list[list[float]] | EmbeddingErrorInfo:
        """Embed documents using cache manager for coordination."""

        # Retry logic: fetch batch from cache
        if batch_id:
            cached_batch = await self.cache_manager.get_batch(self.namespace, batch_id)
            if cached_batch:
                documents = cached_batch

        # Generate batch ID
        batch_id = batch_id or uuid7()

        # Deduplicate
        if skip_deduplication:
            deduplicated = list(documents)
        else:
            deduplicated = await self.cache_manager.deduplicate(
                namespace=self.namespace,
                chunks=list(documents),
                batch_id=batch_id,
            )

        if not deduplicated:
            return []  # All duplicates

        try:
            # Call provider API
            results = await self._embed_documents_with_retry(deduplicated, **kwargs)

            # Register in cache manager
            await self.cache_manager.register_embeddings(
                namespace=self.namespace,
                batch_id=batch_id,
                chunks=deduplicated,
                embeddings=results,
                model=self.model_name,
                kind="dense" if not self._is_sparse else "sparse",
            )

            return results

        except Exception as e:
            # Batch preserved in cache for retry
            return self._handle_embedding_error(e, batch_id, deduplicated, None)
```

### Data Flow

```
1. Provider.embed_documents(chunks) called
2. cache_manager.deduplicate(namespace, chunks, batch_id)
   - Async lock on namespace
   - Check provider-specific dedup dict
   - Store batch in provider-specific batch cache
   - Return deduplicated chunks
3. Provider calls API with deduplicated chunks
4. cache_manager.register_embeddings(namespace, batch_id, chunks, embeddings)
   - Async lock on shared embeddings
   - Store ChunkEmbeddings objects
   - Remove batch from provider cache (success)
5. On error: batch remains in cache for retry
```

### Migration Path

1. **Phase 1**: Create `EmbeddingCacheManager` with DI registration
2. **Phase 2**: Add `cache_manager` dependency to `EmbeddingProvider.__init__`
3. **Phase 3**: Replace `_process_input()` with `cache_manager.deduplicate()`
4. **Phase 4**: Replace `_register_chunks()` with `cache_manager.register_embeddings()`
5. **Phase 5**: Remove ClassVar `_store` and `_hash_store` from providers
6. **Phase 6**: Update tests to use cache manager fixture

### Pros

✅ **Namespace isolation**: Dense/sparse providers don't collide
✅ **Simple provider code**: Just call cache manager methods
✅ **Async-safe**: Explicit namespace locking
✅ **Stateless providers**: No ClassVar pollution
✅ **DI integration**: Cache manager is singleton
✅ **Error recovery**: Batches preserved per namespace
✅ **Minimal API**: 3 methods (deduplicate, register, get_batch)
✅ **Easy testing**: Clear namespace per test

### Cons

❌ **No weak references**: Lost `_trash_heap` recovery
❌ **Namespace explosion**: One cache per provider+model combo

---

## Architecture 3: Event-Driven with Pub/Sub

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ EmbeddingEventBus (DI Singleton)                            │
│                                                               │
│  Events:                                                    │
│    - EmbeddingRequested(chunks, provider, batch_id)        │
│    - EmbeddingCompleted(batch_id, embeddings)              │
│    - EmbeddingFailed(batch_id, error)                       │
│                                                               │
│  Subscribers:                                               │
│    - DeduplicationService (listens to Requested)           │
│    - RegistryService (listens to Completed)                │
│    - RetryService (listens to Failed)                       │
│                                                               │
└─────────────────────────────────────────────────────────────┘
         ▲
         │ publishes events
         │
┌────────┴─────────┐    ┌───────────────────┐
│ VoyageProvider    │    │ JinaProvider       │
│ (stateless)       │    │ (stateless)        │
│                   │    │                    │
│ Publishes:        │    │ Publishes:         │
│ - Requested       │    │ - Requested        │
│ - Completed       │    │ - Completed        │
│ - Failed          │    │ - Failed           │
└───────────────────┘    └────────────────────┘
```

### Key Components

```python
# src/codeweaver/providers/embedding/events.py

from dataclasses import dataclass
from typing import Literal
from pydantic import UUID7
from codeweaver.core import CodeChunk


@dataclass
class EmbeddingEvent:
    """Base event for embedding operations."""
    batch_id: UUID7
    provider: str
    timestamp: float


@dataclass
class EmbeddingRequested(EmbeddingEvent):
    """Event published when embeddings are requested."""
    chunks: list[CodeChunk]
    kind: Literal["dense", "sparse"]


@dataclass
class EmbeddingCompleted(EmbeddingEvent):
    """Event published when embeddings are completed."""
    chunks: list[CodeChunk]
    embeddings: list[list[float]]
    model: str
    kind: Literal["dense", "sparse"]


@dataclass
class EmbeddingFailed(EmbeddingEvent):
    """Event published when embedding fails."""
    chunks: list[CodeChunk]
    error: Exception


# src/codeweaver/providers/embedding/event_bus.py

from asyncio import Queue, create_task
from collections.abc import Callable, Awaitable
from typing import TypeVar

EventT = TypeVar("EventT", bound=EmbeddingEvent)


class EmbeddingEventBus(BasedModel):
    """Async event bus for embedding operations.

    Decouples providers from caching/registry logic.
    """

    _subscribers: dict[type[EmbeddingEvent], list[Callable[[EmbeddingEvent], Awaitable[None]]]] = (
        PrivateAttr(default_factory=dict)
    )
    _event_queue: Queue[EmbeddingEvent] = PrivateAttr(default_factory=Queue)
    _running: bool = PrivateAttr(default=False)

    def subscribe(
        self,
        event_type: type[EventT],
        handler: Callable[[EventT], Awaitable[None]],
    ) -> None:
        """Subscribe to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    async def publish(self, event: EmbeddingEvent) -> None:
        """Publish an event to all subscribers."""
        await self._event_queue.put(event)

    async def start(self) -> None:
        """Start event processing loop."""
        self._running = True
        while self._running:
            event = await self._event_queue.get()
            handlers = self._subscribers.get(type(event), [])

            # Fire all handlers concurrently
            tasks = [create_task(handler(event)) for handler in handlers]
            await asyncio.gather(*tasks, return_exceptions=True)

    async def stop(self) -> None:
        """Stop event processing."""
        self._running = False


# Service: Deduplication
class DeduplicationService:
    """Subscribes to EmbeddingRequested, performs deduplication."""

    def __init__(self, bus: EmbeddingEventBus):
        self.cache: dict[str, dict[BlakeHashKey, UUID7]] = {}  # namespace → dedup
        bus.subscribe(EmbeddingRequested, self.handle_request)

    async def handle_request(self, event: EmbeddingRequested) -> None:
        """Deduplicate chunks before embedding."""
        namespace = event.provider
        if namespace not in self.cache:
            self.cache[namespace] = {}

        deduplicated = []
        for chunk in event.chunks:
            hash_key = get_blake_hash(chunk.content.encode("utf-8"))
            if hash_key not in self.cache[namespace]:
                self.cache[namespace][hash_key] = event.batch_id
                deduplicated.append(chunk)

        # Update event (mutation - notify other subscribers)
        event.chunks = deduplicated


# Service: Registry
class RegistryService:
    """Subscribes to EmbeddingCompleted, stores embeddings."""

    def __init__(self, bus: EmbeddingEventBus):
        self.embeddings: dict[UUID7, ChunkEmbeddings] = {}
        bus.subscribe(EmbeddingCompleted, self.handle_completion)

    async def handle_completion(self, event: EmbeddingCompleted) -> None:
        """Store completed embeddings."""
        for i, (chunk, embedding) in enumerate(zip(event.chunks, event.embeddings, strict=True)):
            if chunk.chunk_id not in self.embeddings:
                self.embeddings[chunk.chunk_id] = ChunkEmbeddings(chunk=chunk)

            batch_info = EmbeddingBatchInfo(
                batch_id=event.batch_id,
                batch_index=i,
                chunk_id=chunk.chunk_id,
                model=event.model,
                embeddings=embedding,
                kind=event.kind,
            )

            self.embeddings[chunk.chunk_id] = self.embeddings[chunk.chunk_id].add(batch_info)


# DI registration
@dependency_provider(EmbeddingEventBus, scope="singleton")
def get_event_bus() -> EmbeddingEventBus:
    bus = EmbeddingEventBus()

    # Register services
    DeduplicationService(bus)
    RegistryService(bus)
    # RetryService(bus)  # Future

    return bus
```

### Provider Integration

```python
class EmbeddingProvider[EmbeddingClient](BasedModel, ABC):
    """Stateless provider using event bus."""

    event_bus: Annotated[EmbeddingEventBus, depends(get_event_bus)]

    async def embed_documents(
        self,
        documents: Sequence[CodeChunk],
        **kwargs: Any,
    ) -> list[list[float]] | EmbeddingErrorInfo:
        """Embed documents using event-driven architecture."""

        batch_id = uuid7()

        # Publish request event (deduplication service handles it)
        request_event = EmbeddingRequested(
            batch_id=batch_id,
            provider=self.namespace,
            chunks=list(documents),
            kind="dense",
            timestamp=time.time(),
        )
        await self.event_bus.publish(request_event)

        # Wait for deduplication (event processed synchronously here)
        # In real impl, would await on a future or use callback
        deduplicated = request_event.chunks  # Modified by dedup service

        if not deduplicated:
            return []

        try:
            # Call provider API
            results = await self._embed_documents_with_retry(deduplicated, **kwargs)

            # Publish completion event (registry service handles it)
            completion_event = EmbeddingCompleted(
                batch_id=batch_id,
                provider=self.namespace,
                chunks=deduplicated,
                embeddings=results,
                model=self.model_name,
                kind="dense",
                timestamp=time.time(),
            )
            await self.event_bus.publish(completion_event)

            return results

        except Exception as e:
            # Publish failure event
            failure_event = EmbeddingFailed(
                batch_id=batch_id,
                provider=self.namespace,
                chunks=deduplicated,
                error=e,
                timestamp=time.time(),
            )
            await self.event_bus.publish(failure_event)
            return self._handle_embedding_error(e, batch_id, deduplicated, None)
```

### Data Flow

```
1. Provider.embed_documents(chunks)
2. Publish EmbeddingRequested event
3. DeduplicationService handles event:
   - Deduplicates chunks
   - Mutates event.chunks in place
4. Provider calls API with deduplicated chunks
5. Publish EmbeddingCompleted event
6. RegistryService handles event:
   - Stores ChunkEmbeddings
7. On error: Publish EmbeddingFailed event
   - RetryService (future) handles retry
```

### Migration Path

1. **Phase 1**: Create event types and `EmbeddingEventBus`
2. **Phase 2**: Create `DeduplicationService` and `RegistryService`
3. **Phase 3**: Update `EmbeddingProvider` to publish events
4. **Phase 4**: Start event bus in server initialization
5. **Phase 5**: Remove ClassVar stores from providers
6. **Phase 6**: Add retry/monitoring services as subscribers

### Pros

✅ **Decoupled**: Providers don't know about caching/registry
✅ **Extensible**: Add services without changing providers
✅ **Observable**: All operations are events (telemetry, logging)
✅ **Async-native**: Event queue handles coordination
✅ **Testable**: Mock event bus, assert on events

### Cons

❌ **Complexity**: Event-driven patterns harder to debug
❌ **Ordering**: Event processing order not guaranteed
❌ **Synchronization**: Need futures/callbacks for request→response flow
❌ **Overhead**: Event serialization/deserialization cost
❌ **Learning curve**: Team needs to understand pub/sub

---

## Comparison Matrix

| Criterion | Arch 1: Repository | Arch 2: Cache Manager | Arch 3: Event Bus |
|-----------|-------------------|----------------------|-------------------|
| **Simplicity** | Medium | High | Low |
| **Async Safety** | High | High | High |
| **DI Integration** | High | High | High |
| **Provider Code** | Complex (context mgr) | Simple (method calls) | Simple (event publish) |
| **Namespace Isolation** | Manual | Built-in | Built-in |
| **Error Recovery** | Built-in | Built-in | Requires service |
| **Extensibility** | Low | Medium | High |
| **Debuggability** | High | High | Low |
| **Migration Effort** | Medium | Low | High |
| **Testing Complexity** | Medium | Low | Medium |
| **Performance** | Good | Good | Overhead |

---

## Recommendation: Architecture 2 (Cache Manager)

### Rationale

1. **Simplest provider integration**: Just call 3 methods
2. **Namespace isolation**: Solves dense/sparse collision problem
3. **Async-safe**: Explicit locking per namespace
4. **Low migration effort**: Drop-in replacement for ClassVar stores
5. **Easy testing**: Clear namespace per test case
6. **Good performance**: Minimal overhead vs current system

### Implementation Plan

**Week 1: Core Infrastructure**
- Day 1-2: Create `EmbeddingCacheManager` class with tests
- Day 3-4: Add DI registration and integration tests
- Day 5: Update `EmbeddingProvider` base class

**Week 2: Provider Migration**
- Day 1-2: Migrate concrete providers (Voyage, Jina, etc.)
- Day 3-4: Remove ClassVar stores, update tests
- Day 5: Integration testing and benchmarks

**Week 3: Polish & Optimize**
- Day 1-2: Performance tuning, lock optimization
- Day 3-4: Documentation and examples
- Day 5: Code review and merge

### Success Criteria

✅ No ClassVar stores in providers
✅ All tests passing with cache manager
✅ Dense/sparse providers isolated
✅ Async-safe concurrent embedding
✅ <5% performance overhead
✅ Clear error recovery path

---

## Future Enhancements

### For All Architectures

1. **Weak reference recovery**: Add `_trash_heap` to cache manager
2. **TTL expiration**: Auto-expire old batches
3. **Metrics collection**: Track cache hits, dedup rate
4. **Persistent caching**: Save to disk for server restart
5. **Distributed caching**: Redis backend for multi-instance

### Architecture-Specific

**Repository Pattern**:
- Add transaction support with rollback
- Implement query interface for batch introspection

**Cache Manager**:
- Add cache warming on startup
- Implement namespace quotas
- Add cache eviction policies (LRU, LFU)

**Event Bus**:
- Add event replay for debugging
- Implement saga pattern for complex workflows
- Add event sourcing for audit trail

---

## Appendices

### A. Code Size Comparison

| Architecture | New Lines | Removed Lines | Net Change |
|--------------|-----------|---------------|------------|
| Repository   | ~300      | ~200          | +100       |
| Cache Manager| ~250      | ~200          | +50        |
| Event Bus    | ~400      | ~200          | +200       |

### B. Performance Estimates

Based on current architecture baseline:

| Operation | Current | Repository | Cache Mgr | Event Bus |
|-----------|---------|------------|-----------|-----------|
| Dedup check | 50ns | 60ns (+20%) | 55ns (+10%) | 100ns (+100%) |
| Batch store | 100ns | 120ns (+20%) | 110ns (+10%) | 150ns (+50%) |
| Final register | 200ns | 220ns (+10%) | 210ns (+5%) | 250ns (+25%) |

### C. Testing Strategy

**Unit Tests**:
- Cache manager namespace isolation
- Async lock coordination
- Deduplication logic
- Batch lifecycle

**Integration Tests**:
- Provider → cache manager flow
- Concurrent embedding from multiple providers
- Error recovery and retry
- DI container resolution

**Performance Tests**:
- Benchmark dedup throughput
- Measure lock contention under load
- Profile memory usage
- Compare to baseline

---

**Analysis Complete** - Ready for implementation decision and execution.
