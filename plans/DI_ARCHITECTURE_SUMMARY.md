<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Dependency Injection Architecture - Executive Summary

**See Full Plan**: [dependency-injection-architecture-plan.md](./dependency-injection-architecture-plan.md)

## The Problem

Current provider instantiation is verbose and manual:

```python
# Scattered everywhere in the codebase
def _get_embedding_instance():
    from codeweaver.common.registry import get_provider_registry
    registry = get_provider_registry()
    if provider := registry.get_embedding_provider():
        return registry.get_embedding_provider_instance(provider, singleton=True)
    return None
```

**Issues:**
- 40+ providers across 6 types - boilerplate everywhere
- No declarative dependencies
- Hard to test (manual mocking)
- pydantic-ai providers not integrated
- Will get worse as we add more providers

## The Solution

FastAPI-inspired dependency injection:

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

**Core Components:**
1. **Container** - Central registry for dependency providers
2. **Depends()** - Dependency marker (like FastAPI)
3. **Factories** - Hide complex instantiation logic
4. **Type Aliases** - Clean service signatures

## Key Benefits

| Benefit | Impact |
|---------|--------|
| **Less Boilerplate** | 60-70% reduction in dependency code |
| **Better Testing** | Clean override mechanism |
| **Scalability** | Adding providers becomes mechanical |
| **FastAPI Alignment** | Familiar patterns for contributors |
| **Type Safety** | Full type inference and checking |

## Implementation Phases

### Phase 1: Foundation (2nd alpha feature release)
- Core DI infrastructure
- No production changes yet
- **Risk**: Low

### Phase 2: Integration (2nd alpha feature release)
- Migrate core services
- Old pattern still works
- **Risk**: Medium

### Phase 3: pydantic-ai (2nd alpha feature release / 3rd alpha feature release)
- Integrate pydantic-ai providers
- Data sources (Tavily, DuckDuckGo)
- **Risk**: Medium

### Phase 4+: Advanced (v0.3)
- Health checks, telemetry
- Plugin enhancements
- **Risk**: Low

## Migration Strategy

**2nd alpha**: DI available, old pattern works  
**3rd alpha**: Old pattern deprecated  
**4th alpha**: Old pattern removed

**Zero breaking changes until 4th alpha feature release**

## Code Comparison

### Before: Manual + Verbose

```python
# Service implementation
class Indexer:
    def __init__(self):
        self.embedding = self._get_embedding()
        self.vector_store = self._get_vector_store()
    
    def _get_embedding(self):
        registry = get_provider_registry()
        provider = registry.get_embedding_provider()
        return registry.get_embedding_provider_instance(provider, singleton=True)
    
    def _get_vector_store(self):
        registry = get_provider_registry()
        provider = registry.get_vector_store_provider()
        return registry.get_vector_store_provider_instance(provider, singleton=True)

# Testing
def test_indexer():
    indexer = Indexer()
    indexer.embedding = MockEmbedding()  # Brittle
    indexer.vector_store = MockVectorStore()
    # test...
```

### After: Declarative + Clean

```python
# Service implementation
from codeweaver.di.providers import EmbeddingDep, VectorStoreDep

class Indexer:
    def __init__(
        self,
        embedding: EmbeddingDep,
        vector_store: VectorStoreDep,
    ):
        self.embedding = embedding
        self.vector_store = vector_store

# Testing
def test_indexer(container):
    container.override(EmbeddingProvider, MockEmbedding())
    container.override(VectorStoreProvider, MockVectorStore())
    
    indexer = await container.resolve(Indexer)
    # test...
```

## Constitutional Compliance

✅ **Proven Patterns** (Principle II): Channels FastAPI's DI system  
✅ **Evidence-Based** (Principle III): Incremental, testable phases  
✅ **Simplicity** (Principle V): Hides complexity in factories  
✅ **AI-First Context** (Principle I): Self-documenting dependencies

## Questions for Discussion

1. **Timing**: v0.2, v0.3, or split across both?
2. **pydantic-ai priority**: Fast-track Phase 3?
3. **Breaking changes**: Deprecate in v0.3, remove in v0.4 OK?
4. **DI mandate**: Require for new code after Phase 1?

## Recommendation

**Implement Phases 1-2 in v0.2** (foundation + core migration)
- Low risk, high value
- Can evaluate before committing to Phase 3+
- Maintains backward compatibility
- Positions us well for v0.3 expansion

## Next Steps

1. ✅ Review planning document
2. ⏳ Get user approval on design
3. ⏳ Create proof-of-concept (simple container + one provider)
4. ⏳ Begin Phase 1 implementation

---

**Full Details**: See [dependency-injection-architecture-plan.md](./dependency-injection-architecture-plan.md) (32KB comprehensive analysis)
