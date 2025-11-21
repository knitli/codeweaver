<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Dependency Injection Architecture Plan for CodeWeaver v0.2/v0.3

**Status**: Planning / Analysis  
**Created**: 2025-10-31  
**Target**: 2nd or 3rd alpha feature release

## Executive Summary

This document provides a comprehensive analysis of CodeWeaver's current dependency management approach and proposes a FastAPI-inspired dependency injection (DI) architecture for v0.2/v0.3. The goal is to create a clean, extensible system that can elegantly handle the growing complexity of providers (embedding, reranking, vector stores, agents, data sources) while maintaining constitutional principles.

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [Problem Statement](#problem-statement)
3. [Design Goals](#design-goals)
4. [Proposed Architecture](#proposed-architecture)
5. [Implementation Phases](#implementation-phases)
6. [Migration Strategy](#migration-strategy)
7. [Risk Analysis](#risk-analysis)
8. [Success Criteria](#success-criteria)

---

## Current State Analysis

### Existing Architecture

CodeWeaver currently uses a **registry pattern** with three main components:

#### 1. Provider Registry (`common/registry/provider.py`)
- Global singleton managing provider class registration and instantiation
- Lazy loading via `LazyImport` for performance
- Provider types: EMBEDDING, SPARSE_EMBEDDING, RERANKING, VECTOR_STORE, AGENT, DATA
- Manual instantiation with explicit `**kwargs` passing

**Current instantiation pattern:**
```python
# Example from indexer.py
def _get_embedding_instance(*, sparse: bool = False) -> EmbeddingProvider[Any] | None:
    from codeweaver.common.registry import get_provider_registry
    
    registry = get_provider_registry()
    if provider := registry.get_embedding_provider(sparse=sparse):
        if sparse:
            return registry.get_sparse_embedding_provider_instance(
                provider=provider, singleton=True
            )
        return registry.get_embedding_provider_instance(provider=provider, singleton=True)
    return None
```

**Issues:**
- Manual retrieval functions scattered throughout codebase
- No declarative dependency management
- Settings resolution happens at call time
- Difficult to inject test doubles
- No lifecycle management hooks
- Circular dependency risks

#### 2. Model Registry (`common/registry/models.py`)
- Manages model capabilities metadata
- Provider -> Model -> Capabilities mapping
- Built-in capabilities auto-registration
- Agent profile resolution

#### 3. Settings Management (`config/providers.py`)
- `pydantic-settings` based configuration
- Hierarchical: env vars > config files > defaults
- TypedDict definitions for provider settings
- Provider-specific settings (AWS, Azure, etc.)

### Provider Types Inventory

| Provider Type | Count | Examples | Integration Status |
|--------------|-------|----------|-------------------|
| **Embedding (Dense)** | 10+ | VoyageAI, OpenAI, Bedrock, Cohere, Google, Mistral, Fastembed | ✅ Integrated |
| **Embedding (Sparse)** | 2 | Fastembed, Sentence-Transformers | ✅ Integrated |
| **Reranking** | 5 | Voyage, Bedrock, Cohere, Fastembed, Sentence-Transformers | ✅ Integrated |
| **Vector Stores** | 2 | Qdrant, In-Memory | ✅ Integrated |
| **Agent (pydantic-ai)** | 18+ | Anthropic, OpenAI, Azure, Bedrock, Cohere, Cerebras, etc. | 🚧 Wired but not integrated |
| **Data Sources** | 2 | Tavily, DuckDuckGo (pydantic-ai) | 🚧 Wired but not integrated |

**Total**: ~40 provider implementations across 6 provider types

### Key Observations

1. **Registry pattern works but is verbose**: Every service needs boilerplate to fetch dependencies
2. **No DI framework**: Manual wiring everywhere
3. **pydantic-ai providers separate**: Different instantiation pattern (by design in pydantic-ai)
4. **Growing complexity**: More provider types = more manual wiring
5. **Test doubles hard to inject**: No clean dependency override mechanism
6. **Lifecycle management missing**: No startup/shutdown hooks, health checks scattered

---

## Problem Statement

### Core Problems

#### 1. **Manual Dependency Wiring**
Services manually fetch dependencies from registries, leading to:
- Verbose boilerplate in every service
- No declarative dependency declaration
- Hard to trace dependency graphs
- Difficult to test with mocks

#### 2. **Provider Instantiation Complexity**
Different provider types have different instantiation patterns:
- Embedding providers: registry + settings + capabilities lookup
- pydantic-ai agents: model string-based instantiation
- Vector stores: different config shapes
- No unified instantiation interface

#### 3. **Settings Resolution Scattered**
Settings resolution happens in multiple places:
- `common/registry/utils.py` - helper functions
- Provider constructors
- Service initialization code
- No single source of truth

#### 4. **No Lifecycle Management**
Missing features:
- Startup/shutdown hooks for providers
- Health check coordination
- Resource cleanup (connections, caches)
- Graceful degradation

#### 5. **Testing Challenges**
- No dependency override mechanism
- Hard to inject test doubles
- Global singletons complicate test isolation
- Manual setup/teardown required

#### 6. **Future Integration Challenges**
Upcoming provider types will compound these issues:
- More pydantic-ai tools (Context7, web search, etc.)
- Custom user providers
- Plugin system expansion
- Multi-tenant scenarios

---

## Design Goals

### Constitutional Alignment

Our DI architecture must satisfy these constitutional principles:

#### ✅ **Proven Patterns** (Principle II)
- Channel FastAPI's dependency injection system
- Use patterns from successful pydantic ecosystem projects
- Avoid reinventing wheels

#### ✅ **Evidence-Based Development** (Principle III)
- No placeholders or mock implementations
- All features backed by tests
- Incremental, verifiable progress

#### ✅ **Simplicity Through Architecture** (Principle V)
- Transform complexity into clarity
- Obvious purpose and usage
- Flat structure, minimal nesting

#### ✅ **AI-First Context** (Principle I)
- Self-documenting dependency declarations
- Clear type annotations
- Easy to understand for both humans and AI

### Functional Requirements

1. **Declarative Dependencies**: Services declare what they need, not how to get it
2. **Type Safety**: Full type inference and checking
3. **Lazy Initialization**: Create providers only when needed
4. **Singleton Support**: Configurable singleton vs. per-request instances
5. **Lifecycle Hooks**: Startup, shutdown, health checks
6. **Override Mechanism**: Easy testing with dependency substitution
7. **Settings Integration**: Seamless pydantic-settings integration
8. **Provider Agnostic**: Works uniformly across all provider types
9. **Async First**: Native async/await support
10. **Minimal Breaking Changes**: Phase in without disrupting v0.1

---

## Proposed Architecture

### Core Design: Inspired by FastAPI's `Depends()`

FastAPI's DI system is elegant because it:
- Uses function signatures as dependency declarations
- Supports nested dependencies
- Provides clean override mechanism for testing
- Handles both sync and async
- Integrates naturally with type system

**Our adaptation for CodeWeaver:**

#### 1. **Dependency Container**

```python
# codeweaver/di/container.py
from collections.abc import Callable, Awaitable
from typing import TypeVar, Protocol, Any, ParamSpec
from contextlib import asynccontextmanager

T = TypeVar('T')
P = ParamSpec('P')

class DependencyProvider(Protocol[T]):
    """Protocol for dependency providers."""
    
    async def __call__(self) -> T:
        """Resolve the dependency."""
        ...

class Container:
    """Central dependency container for CodeWeaver.
    
    Inspired by FastAPI's dependency injection but adapted for 
    CodeWeaver's provider ecosystem.
    """
    
    def __init__(self):
        self._providers: dict[type, DependencyProvider] = {}
        self._singletons: dict[type, Any] = {}
        self._overrides: dict[type, DependencyProvider] = {}
        self._lifecycle_hooks: dict[str, list[Callable]] = {
            'startup': [],
            'shutdown': [],
        }
    
    def register(
        self,
        interface: type[T],
        factory: Callable[[], Awaitable[T]] | Callable[[], T],
        *,
        singleton: bool = True,
        lifecycle: bool = False,
    ) -> None:
        """Register a dependency provider.
        
        Args:
            interface: The interface/type to register
            factory: Factory function to create instances
            singleton: Whether to cache the instance
            lifecycle: Whether the provider has startup/shutdown hooks
        """
        ...
    
    def override(self, interface: type[T], override: T | Callable[[], T]) -> None:
        """Override a dependency (primarily for testing)."""
        ...
    
    async def resolve(self, interface: type[T]) -> T:
        """Resolve a dependency by type."""
        ...
    
    @asynccontextmanager
    async def lifespan(self):
        """Manage container lifecycle (startup/shutdown)."""
        try:
            # Run startup hooks
            for hook in self._lifecycle_hooks['startup']:
                await hook() if asyncio.iscoroutinefunction(hook) else hook()
            yield self
        finally:
            # Run shutdown hooks
            for hook in self._lifecycle_hooks['shutdown']:
                await hook() if asyncio.iscoroutinefunction(hook) else hook()
```

#### 2. **Depends() Function**

```python
# codeweaver/di/depends.py
from typing import TypeVar, Callable, Any
from dataclasses import dataclass

T = TypeVar('T')

@dataclass
class Depends:
    """Dependency marker, similar to FastAPI's Depends.
    
    Usage:
        async def my_service(
            embedding: EmbeddingProvider = Depends(get_embedding_provider)
        ):
            ...
    """
    
    dependency: Callable[..., Any]
    use_cache: bool = True
    
    def __init__(
        self,
        dependency: Callable[..., T] | None = None,
        *,
        use_cache: bool = True,
    ):
        self.dependency = dependency
        self.use_cache = use_cache
```

#### 3. **Provider Factories**

```python
# codeweaver/di/providers.py
from typing import Annotated
from codeweaver.providers.embedding.providers.base import EmbeddingProvider
from codeweaver.providers.vector_stores.base import VectorStoreProvider
from codeweaver.di.depends import Depends

async def get_embedding_provider() -> EmbeddingProvider:
    """Factory for embedding provider.
    
    Resolves from settings and registry automatically.
    """
    from codeweaver.common.registry import get_provider_registry
    from codeweaver.common.registry.utils import get_model_config
    
    registry = get_provider_registry()
    config = get_model_config("embedding")
    
    if not config:
        raise ConfigurationError("No embedding provider configured")
    
    provider_enum = config["provider"]
    model_settings = config["model_settings"]
    provider_settings = config.get("provider_settings")
    
    # Get capabilities to determine proper initialization
    capabilities = registry.get_model_registry().get_embedding_capabilities(
        provider_enum, model_settings["model"]
    )
    
    return registry.get_embedding_provider_instance(
        provider_enum,
        singleton=True,
        capabilities=capabilities,
        model_settings=model_settings,
        provider_settings=provider_settings,
    )

async def get_vector_store() -> VectorStoreProvider:
    """Factory for vector store provider."""
    ...

# Type aliases for cleaner service signatures
EmbeddingDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
VectorStoreDep = Annotated[VectorStoreProvider, Depends(get_vector_store)]
```

#### 4. **Service Signature Example**

```python
# codeweaver/engine/indexer.py (refactored)
from codeweaver.di.providers import EmbeddingDep, VectorStoreDep

class Indexer:
    """Document indexer with dependency injection."""
    
    def __init__(
        self,
        embedding_provider: EmbeddingDep,
        vector_store: VectorStoreDep,
        chunking_service: ChunkingService,  # Can also be injected
    ):
        self.embedding = embedding_provider
        self.vector_store = vector_store
        self.chunking = chunking_service
    
    async def index_file(self, file_path: Path) -> None:
        """Index a file using injected dependencies."""
        chunks = await self.chunking.chunk_file(file_path)
        embeddings = await self.embedding.embed_documents(chunks)
        await self.vector_store.upsert(chunks, embeddings)
```

### Key Architectural Decisions

#### Decision 1: Container-Based vs. Function-Based DI

**Options:**
1. Pure function-based (like FastAPI - inspect signatures)
2. Container-based registration (like dependency-injector)
3. Hybrid approach

**Choice**: **Hybrid** - Container for registration, function signatures for declaration

**Rationale:**
- Container provides centralized provider management
- Function signatures remain declarative and type-safe
- Hybrid gives us flexibility for both paradigms
- Easier to implement than pure signature inspection
- Aligns with Constitutional Principle II (Proven Patterns)

#### Decision 2: Singleton Management

**Options:**
1. All providers are singletons (current approach)
2. All providers are per-request
3. Configurable per provider type

**Choice**: **Configurable per provider type** (default singleton)

**Rationale:**
- Embedding/vector providers: singleton (expensive to initialize)
- Data source providers: per-request (stateless, cheap)
- Agents: configurable (depends on use case)
- Flexibility for future needs

#### Decision 3: Settings Integration

**Options:**
1. Settings passed explicitly to factories
2. Settings auto-resolved in factories
3. Settings as separate injectable dependency

**Choice**: **Settings auto-resolved in factories** with override option

**Rationale:**
- Simplifies service signatures (no settings boilerplate)
- Maintains existing pydantic-settings integration
- Can still override for testing
- Constitutional Principle V (Simplicity)

#### Decision 4: pydantic-ai Provider Integration

**Challenge**: pydantic-ai has its own provider system

**Options:**
1. Wrap pydantic-ai providers in CodeWeaver interface
2. Expose pydantic-ai providers directly
3. Dual approach - both available

**Choice**: **Expose pydantic-ai providers directly** via our DI system

**Rationale:**
- Don't fight pydantic-ai's design (Constitutional Principle II)
- Factory pattern can handle different instantiation logic
- Users familiar with pydantic-ai get expected interface
- Less maintenance burden (don't duplicate their work)

**Implementation:**
```python
# codeweaver/di/providers.py
from pydantic_ai import Agent

async def get_pydantic_agent() -> Agent:
    """Factory for pydantic-ai agent.
    
    Uses pydantic-ai's instantiation pattern but fits into our DI system.
    """
    from codeweaver.common.registry.utils import get_model_config
    
    config = get_model_config("agent")
    model_name = config["model"]  # e.g., "openai:gpt-4"
    settings = config.get("model_settings")
    
    # Use pydantic-ai's model instantiation
    return Agent(model_name, settings=settings)
```

---

## Implementation Phases

### Phase 1: Foundation (v0.2 Early)

**Goal**: Core DI infrastructure without breaking existing code

**Tasks:**
1. ✅ Create `codeweaver/di/` package
   - `container.py` - Container implementation
   - `depends.py` - Depends marker
   - `providers.py` - Provider factories
   - `__init__.py` - Public API

2. ✅ Implement Container class
   - Registration mechanism
   - Resolution with caching
   - Override support
   - Basic lifecycle hooks

3. ✅ Create provider factories for existing types
   - `get_embedding_provider()`
   - `get_sparse_embedding_provider()`
   - `get_reranking_provider()`
   - `get_vector_store()`

4. ✅ Add comprehensive tests
   - Container registration/resolution
   - Override mechanism
   - Singleton behavior
   - Lifecycle hooks

**Deliverable**: Working DI system, no production usage yet

**Risk**: Low (isolated new code, no changes to existing)

### Phase 2: Integration (v0.2 Mid)

**Goal**: Migrate core services to use DI

**Tasks:**
1. ✅ Migrate `Indexer` to use DI
   - Constructor injection
   - Remove manual provider fetching
   - Update tests to use overrides

2. ✅ Migrate search services
   - Semantic search
   - Hybrid search
   - Query processing

3. ✅ Update server initialization
   - Use container lifespan
   - Register all providers at startup
   - Health checks via DI

4. ✅ Integration tests
   - End-to-end with real providers
   - End-to-end with test doubles

**Deliverable**: Core services using DI, old pattern still available

**Risk**: Medium (changing production code, need careful testing)

### Phase 3: pydantic-ai Integration (v0.2 Late / v0.3 Early)

**Goal**: Integrate pydantic-ai providers into DI system

**Tasks:**
1. ✅ Create pydantic-ai agent factory
   - Handle model string parsing
   - Settings resolution
   - Provider-specific configurations

2. ✅ Create data source factories
   - Tavily
   - DuckDuckGo
   - Future: Context7, web search

3. ✅ Update agent API to use DI
   - Inject agents into tools
   - Inject data sources into agents

4. ✅ Documentation
   - How to configure agents
   - How to add custom data sources
   - Testing agent-based features

**Deliverable**: Full pydantic-ai integration via DI

**Risk**: Medium (new territory, need to understand pydantic-ai patterns)

### Phase 4: Advanced Features (v0.3)

**Goal**: Leverage DI for advanced capabilities

**Tasks:**
1. ✅ Health check system
   - Provider health checks via DI
   - Aggregated health endpoint
   - Circuit breaker integration

2. ✅ Telemetry integration
   - Inject telemetry into providers
   - Centralized metrics collection
   - Distributed tracing setup

3. ✅ Plugin system enhancement
   - Custom providers via DI
   - User-defined factories
   - Plugin discovery and registration

4. ✅ Multi-tenant support (if needed)
   - Scoped containers per tenant
   - Isolated provider instances
   - Tenant-specific overrides

**Deliverable**: Production-ready DI system with advanced features

**Risk**: Low (building on proven foundation)

### Phase 5: Cleanup (v0.3 Late)

**Goal**: Remove old patterns, finalize API

**Tasks:**
1. ✅ Deprecate manual registry access
   - Add deprecation warnings
   - Update all remaining usages
   - Provide migration guide

2. ✅ Clean up registry code
   - Simplify now that DI handles complexity
   - Registry becomes thin layer over DI

3. ✅ Documentation overhaul
   - Architecture docs
   - Migration guide
   - Best practices

4. ✅ Performance optimization
   - Benchmark DI overhead
   - Optimize hot paths
   - Profile memory usage

**Deliverable**: Clean, DI-first codebase

**Risk**: Low (cleanup work)

---

## Migration Strategy

### Backward Compatibility

**Goal**: No breaking changes in v0.2, deprecated in v0.3, removed in v0.4

#### v0.2: Co-existence
- Old pattern still works
- New pattern available
- Documentation shows both
- New features use DI

#### v0.3: Migration
- Old pattern deprecated (warnings)
- All core code uses DI
- Migration guide published
- Support for questions

#### v0.4: Removal
- Old pattern removed
- DI is the only way
- Breaking change properly communicated

### Migration Examples

#### Before (v0.1)
```python
def _get_embedding_instance() -> EmbeddingProvider:
    from codeweaver.common.registry import get_provider_registry
    registry = get_provider_registry()
    provider = registry.get_embedding_provider()
    return registry.get_embedding_provider_instance(provider, singleton=True)

class Indexer:
    def __init__(self):
        self.embedding = _get_embedding_instance()
        self.vector_store = _get_vector_store_instance()
```

#### After (v0.2+)
```python
from codeweaver.di.providers import EmbeddingDep, VectorStoreDep

class Indexer:
    def __init__(
        self,
        embedding: EmbeddingDep,
        vector_store: VectorStoreDep,
    ):
        self.embedding = embedding
        self.vector_store = vector_store
```

### Testing Migration

#### Before
```python
def test_indexer():
    # Manual mocking
    indexer = Indexer()
    indexer.embedding = MockEmbeddingProvider()
    indexer.vector_store = MockVectorStore()
    # test...
```

#### After
```python
def test_indexer(container):
    # Clean dependency override
    container.override(EmbeddingProvider, MockEmbeddingProvider())
    container.override(VectorStoreProvider, MockVectorStore())
    
    indexer = container.resolve(Indexer)
    # test...
```

---

## Risk Analysis

### Technical Risks

#### Risk 1: Performance Overhead
**Likelihood**: Medium  
**Impact**: Low  
**Mitigation**:
- Benchmark early and often
- Lazy initialization by default
- Singleton caching for expensive providers
- Profile in production-like scenarios

#### Risk 2: Complexity for Contributors
**Likelihood**: Medium  
**Impact**: Medium  
**Mitigation**:
- Comprehensive documentation
- Clear examples
- Migration guide
- Constitutional Principle V (Simplicity)

#### Risk 3: Edge Cases in Provider Instantiation
**Likelihood**: High  
**Impact**: Medium  
**Mitigation**:
- Incremental migration (find issues early)
- Extensive testing
- Clear error messages
- Fallback mechanisms

#### Risk 4: pydantic-ai Integration Surprises
**Likelihood**: Medium  
**Impact**: Medium  
**Mitigation**:
- Study pydantic-ai patterns deeply
- Start with simple integration
- Collaborate with pydantic-ai community
- Have escape hatches

### Organizational Risks

#### Risk 1: Scope Creep
**Likelihood**: High  
**Impact**: High  
**Mitigation**:
- Strict phase boundaries
- Phase 1 must be complete before Phase 2
- Can ship v0.2 after Phase 2
- Phase 3+ can be v0.3

#### Risk 2: Breaking Changes
**Likelihood**: Low (with migration strategy)  
**Impact**: High  
**Mitigation**:
- Careful deprecation process
- Clear communication
- Migration guide
- Version bumps follow semver

---

## Success Criteria

### Phase 1 Success Criteria
- [ ] Container can register and resolve dependencies
- [ ] Override mechanism works for testing
- [ ] Singleton caching functions correctly
- [ ] 100% test coverage for DI infrastructure
- [ ] No changes to existing production code

### Phase 2 Success Criteria
- [ ] Core services migrated to DI
- [ ] All existing tests still pass
- [ ] New tests use override mechanism
- [ ] No performance regression
- [ ] Documentation updated

### Phase 3 Success Criteria
- [ ] pydantic-ai agents injectable
- [ ] Data sources work via DI
- [ ] Agent API updated
- [ ] Integration tests passing
- [ ] pydantic-ai patterns properly documented

### Overall Success Criteria (v0.3)
- [ ] All provider types work via DI
- [ ] Test code 50% less verbose (measured)
- [ ] New provider integration takes < 1 hour (documented)
- [ ] Zero breaking changes from v0.2 to v0.3
- [ ] Architecture documentation complete
- [ ] Migration guide published
- [ ] Performance within 5% of v0.1

---

## Alternative Approaches Considered

### Alternative 1: Pure FastAPI DI (Signature Inspection)

**Pros:**
- Most faithful to FastAPI pattern
- Very Pythonic
- Excellent type inference

**Cons:**
- Complex to implement (AST inspection, signature analysis)
- FastAPI does this because it controls the router layer
- We'd need to wrap every service method
- Overkill for our use case

**Decision**: Not chosen - too complex for benefit

### Alternative 2: dependency-injector Library

**Pros:**
- Mature, battle-tested
- Feature-complete
- Good documentation

**Cons:**
- Additional dependency
- Not aligned with pydantic ecosystem
- Different paradigm from FastAPI
- Learning curve for contributors

**Decision**: Not chosen - prefer aligned patterns

### Alternative 3: Manual Dependency Passing

**Pros:**
- Explicit is better than implicit
- No magic
- Simple to understand

**Cons:**
- Verbose signatures
- Doesn't scale
- Hard to test
- Already proven painful

**Decision**: Not chosen - this is what we're escaping

### Alternative 4: Service Locator Pattern

**Pros:**
- Simple implementation
- One global place to get dependencies

**Cons:**
- Anti-pattern in modern architecture
- Hidden dependencies
- Hard to test
- Not type-safe

**Decision**: Not chosen - architectural anti-pattern

---

## Implementation Checklist

### Pre-Implementation
- [x] Constitutional review - does this align with principles?
- [x] Review FastAPI DI implementation
- [x] Review pydantic-ai provider patterns
- [ ] Create proof-of-concept (simple container + one provider)
- [ ] Get user feedback on PoC
- [ ] Finalize design decisions

### Phase 1 Implementation
- [ ] Create `codeweaver/di/` package structure
- [ ] Implement `Container` class
- [ ] Implement `Depends` marker
- [ ] Create provider factories
- [ ] Write unit tests (aim for 100% coverage)
- [ ] Write integration tests
- [ ] Document API

### Phase 2 Implementation
- [ ] Migrate `Indexer`
- [ ] Migrate search services
- [ ] Update server initialization
- [ ] Update all tests
- [ ] Performance testing
- [ ] Document migration examples

### Phase 3 Implementation
- [ ] pydantic-ai agent factory
- [ ] Data source factories
- [ ] Update agent API
- [ ] Integration tests
- [ ] Documentation

### Phase 4+ Implementation
- [ ] Health check system
- [ ] Telemetry integration
- [ ] Plugin enhancements
- [ ] Performance optimization

### Phase 5 Implementation
- [ ] Deprecation warnings
- [ ] Complete migration
- [ ] Registry cleanup
- [ ] Documentation overhaul

---

## Questions for User

1. **Timing**: Should this be v0.2 or v0.3? Or phase it: Phase 1-2 in v0.2, Phase 3+ in v0.3?

2. **pydantic-ai integration priority**: How important is pydantic-ai provider integration for v0.1 release? Should we fast-track Phase 3?

3. **Breaking changes tolerance**: Are you comfortable with deprecation in v0.3, removal in v0.4? Or prefer longer timeline?

4. **Testing philosophy**: Should we require DI usage for all new code immediately after Phase 1, or wait until Phase 5?

5. **Plugin system**: Do you envision users creating custom providers that use DI? Should that be Phase 4 or later?

6. **Multi-tenancy**: Is this a near-term requirement? Affects container scoping design.

---

## References

### Internal Documents
- `.specify/memory/constitution.md` - Constitutional principles
- `ARCHITECTURE.md` - Current architecture
- `CODE_STYLE.md` - Code patterns and style
- `plans/IMPLEMENTATION_PLAN.md` - Overall roadmap

### External Resources
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [pydantic-ai Documentation](https://ai.pydantic.dev/)
- [Dependency Injection in Python (blog)](https://python-dependency-injector.ets-labs.org/introduction/di_in_python.html)
- [Clean Architecture (book)](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

---

## Appendix: Code Examples

### Example 1: Complete Service with DI

```python
# codeweaver/services/search_service.py
from typing import Annotated
from codeweaver.di.depends import Depends
from codeweaver.di.providers import (
    EmbeddingDep,
    VectorStoreDep,
    RerankingDep,
)
from codeweaver.engine.match_models import SearchResult

class SearchService:
    """Semantic search service with dependency injection."""
    
    def __init__(
        self,
        embedding: EmbeddingDep,
        vector_store: VectorStoreDep,
        reranking: RerankingDep | None = None,  # Optional
    ):
        self.embedding = embedding
        self.vector_store = vector_store
        self.reranking = reranking
    
    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        filters: dict | None = None,
    ) -> SearchResult:
        """Execute semantic search."""
        # Embed query
        query_embedding = await self.embedding.embed_query(query)
        
        # Vector search
        candidates = await self.vector_store.search(
            query_embedding,
            limit=limit * 3 if self.reranking else limit,
            filters=filters,
        )
        
        # Optional reranking
        if self.reranking:
            candidates = await self.reranking.rerank(
                query=query,
                documents=candidates,
                top_n=limit,
            )
        
        return SearchResult(matches=candidates)
```

### Example 2: Testing with DI

```python
# tests/test_search_service.py
import pytest
from codeweaver.di.container import Container
from codeweaver.providers.embedding.providers.base import EmbeddingProvider
from codeweaver.services.search_service import SearchService

class MockEmbeddingProvider(EmbeddingProvider):
    async def embed_query(self, query: str):
        return [0.1] * 768

@pytest.fixture
def container():
    """Test container with mock dependencies."""
    container = Container()
    
    # Override with mocks
    container.override(EmbeddingProvider, MockEmbeddingProvider())
    container.override(VectorStoreProvider, MockVectorStore())
    
    return container

async def test_search_service(container):
    """Test search service with mocked dependencies."""
    service = await container.resolve(SearchService)
    
    result = await service.search("test query")
    
    assert len(result.matches) > 0
```

### Example 3: Factory with Complex Logic

```python
# codeweaver/di/providers.py
from codeweaver.providers.embedding.providers.base import EmbeddingProvider

async def get_embedding_provider() -> EmbeddingProvider:
    """Factory for embedding provider with full complexity."""
    from codeweaver.common.registry import get_provider_registry
    from codeweaver.common.registry.utils import get_model_config
    from codeweaver.exceptions import ConfigurationError
    
    # Get settings
    config = get_model_config("embedding")
    if not config:
        raise ConfigurationError("No embedding provider configured")
    
    # Extract configuration
    provider_enum = config["provider"]
    model_settings = config["model_settings"]
    provider_settings = config.get("provider_settings")
    model_name = model_settings["model"]
    
    # Get registry
    registry = get_provider_registry()
    model_registry = registry.get_model_registry()
    
    # Resolve capabilities
    capabilities = model_registry.get_embedding_capabilities(
        provider_enum,
        model_name,
    )
    
    if not capabilities:
        raise ConfigurationError(
            f"No capabilities found for {provider_enum}:{model_name}"
        )
    
    # Instantiate with all context
    return registry.get_embedding_provider_instance(
        provider_enum,
        singleton=True,
        capabilities=capabilities[0],  # Use first capability
        model_settings=model_settings,
        provider_settings=provider_settings,
    )
```

---

## Conclusion

This DI architecture will:

1. ✅ **Reduce boilerplate** - Services declare dependencies, don't fetch them
2. ✅ **Improve testability** - Clean override mechanism
3. ✅ **Scale gracefully** - Adding providers becomes mechanical
4. ✅ **Align with FastAPI** - Familiar patterns (Constitutional Principle II)
5. ✅ **Maintain simplicity** - Complex logic hidden in factories (Constitutional Principle V)
6. ✅ **Support evidence-based development** - Incremental, testable (Constitutional Principle III)

**Recommendation**: Implement Phases 1-2 in v0.2, evaluate before committing to Phases 3+.

**Next Steps**:
1. Review and discuss this plan
2. Create proof-of-concept
3. Get user approval on design
4. Begin Phase 1 implementation

---

**Document Status**: Draft - awaiting user feedback  
**Last Updated**: 2025-10-31
