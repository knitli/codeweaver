<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# DI Architecture Diagrams

## Current Architecture (v0.1)

```
┌─────────────────────────────────────────────────────────────┐
│                     Service Layer                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Indexer  │  │  Search  │  │   API    │  │  Agent   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │             │           │
│       └─────────────┴─────────────┴─────────────┘           │
│                          │                                   │
│                    Manual Fetching                           │
└──────────────────────────┼───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│              Provider Registry (Global Singleton)            │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  _embedding_providers: dict                            │ │
│  │  _sparse_embedding_providers: dict                     │ │
│  │  _reranking_providers: dict                            │ │
│  │  _vector_store_providers: dict                         │ │
│  │  _agent_providers: dict                                │ │
│  │  _data_providers: dict                                 │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  _embedding_instances: dict (cached singletons)        │ │
│  │  _sparse_embedding_instances: dict                     │ │
│  │  _reranking_instances: dict                            │ │
│  │  _vector_store_instances: dict                         │ │
│  │  _agent_instances: dict                                │ │
│  │  _data_instances: dict                                 │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Methods:                                                    │
│  - get_provider_class(provider, kind) -> LazyImport         │
│  - create_provider(provider, kind, **kwargs) -> Instance    │
│  - get_provider_instance(provider, kind, ...) -> Instance   │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                    Model Registry                            │
│  - Capabilities metadata                                     │
│  - Model -> Provider mapping                                 │
│  - Agent profile resolution                                  │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                 Settings (pydantic-settings)                 │
│  - Environment variables                                     │
│  - TOML config files                                         │
│  - Defaults                                                  │
└──────────────────────────────────────────────────────────────┘

Problems:
❌ Manual fetching in every service (_get_embedding_instance, etc.)
❌ No declarative dependencies
❌ Hard to test (brittle mocking)
❌ Boilerplate everywhere
❌ Circular dependency risks
```

## Proposed Architecture (v0.2+)

```
┌─────────────────────────────────────────────────────────────┐
│                     Service Layer                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ class Indexer:                                       │   │
│  │     def __init__(                                    │   │
│  │         self,                                        │   │
│  │         embedding: EmbeddingDep,      ◄─────────┐   │   │
│  │         vector_store: VectorStoreDep, ◄────┐    │   │   │
│  │     ):                                      │    │   │   │
│  │         self.embedding = embedding          │    │   │   │
│  │         self.vector_store = vector_store    │    │   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                    │    │     │
│                            Declarative Dependencies    │     │
└────────────────────────────────────────────────────┼────┼─────┘
                                                     │    │
┌────────────────────────────────────────────────────▼────▼─────┐
│                     DI Container                               │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Dependency Registration                                 │ │
│  │  ┌────────────────────────────────────────────────────┐ │ │
│  │  │ register(                                          │ │ │
│  │  │     interface=EmbeddingProvider,                   │ │ │
│  │  │     factory=get_embedding_provider,                │ │ │
│  │  │     singleton=True,                                │ │ │
│  │  │     lifecycle=True,                                │ │ │
│  │  │ )                                                  │ │ │
│  │  └────────────────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Dependency Resolution                                   │ │
│  │  ┌────────────────────────────────────────────────────┐ │ │
│  │  │ async def resolve(interface: type[T]) -> T:        │ │ │
│  │  │     if interface in _singletons:                   │ │ │
│  │  │         return _singletons[interface]              │ │ │
│  │  │     if interface in _overrides:  # Testing!        │ │ │
│  │  │         return _overrides[interface]               │ │ │
│  │  │     factory = _providers[interface]                │ │ │
│  │  │     instance = await factory()                     │ │ │
│  │  │     if singleton: _singletons[interface] = instance│ │ │
│  │  │     return instance                                │ │ │
│  │  └────────────────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Lifecycle Management                                    │ │
│  │  - Startup hooks (connection pooling, warmup)            │ │
│  │  - Shutdown hooks (cleanup, flush)                       │ │
│  │  - Health checks (coordinated)                           │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│                      Provider Factories                        │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ async def get_embedding_provider() -> EmbeddingProvider: │ │
│  │     config = get_model_config("embedding")               │ │
│  │     provider = config["provider"]                        │ │
│  │     capabilities = get_capabilities(provider, model)     │ │
│  │     return registry.get_embedding_provider_instance(     │ │
│  │         provider, capabilities=capabilities, ...         │ │
│  │     )                                                    │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                │
│  Similar factories for:                                        │
│  - get_sparse_embedding_provider()                             │
│  - get_reranking_provider()                                    │
│  - get_vector_store()                                          │
│  - get_pydantic_agent()                                        │
│  - get_data_source()                                           │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│              Provider Registry (Simplified)                    │
│  - Thin layer over DI container                                │
│  - Provider class management                                   │
│  - Lazy loading (LazyImport)                                   │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│                    Model Registry                              │
│  - Capabilities metadata                                       │
│  - Model -> Provider mapping                                   │
│  - Agent profile resolution                                    │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│                 Settings (pydantic-settings)                   │
│  - Environment variables                                       │
│  - TOML config files                                           │
│  - Defaults                                                    │
└────────────────────────────────────────────────────────────────┘

Benefits:
✅ Declarative dependencies (type hints)
✅ Clean testing (override mechanism)
✅ Lifecycle management (startup/shutdown)
✅ Type safety (full inference)
✅ FastAPI-like patterns (familiar)
```

## Dependency Flow Comparison

### Current (Manual)

```
Service Needs Provider
        │
        ▼
Service calls _get_embedding_instance()
        │
        ▼
Helper function:
  1. Import registry module
  2. Get registry singleton
  3. Get provider enum from settings
  4. Get model config from settings
  5. Get capabilities from model registry
  6. Call registry.get_provider_instance(...)
        │
        ▼
Registry checks cache, creates if needed
        │
        ▼
Service receives provider instance

Issues:
- 7+ steps scattered across multiple modules
- Boilerplate in every service
- Hard to trace
- Hard to test
```

### Proposed (DI)

```
Service declares dependency in __init__
        │
        ▼
Container sees EmbeddingDep in signature
        │
        ▼
Container calls registered factory:
  get_embedding_provider()
        │
        ▼
Factory does all complex logic once
        │
        ▼
Container caches result (if singleton)
        │
        ▼
Service receives provider instance

Benefits:
- 3 steps, 1 central location
- No service boilerplate
- Easy to trace (factory = single source of truth)
- Easy to test (override in container)
```

## Testing Flow Comparison

### Current (Manual Mocking)

```python
# Test setup - brittle
def test_indexer():
    indexer = Indexer()
    # Reach into internals to replace
    indexer.embedding = MockEmbeddingProvider()
    indexer.vector_store = MockVectorStore()
    
    # Test...

Issues:
- Must know internal structure
- Fragile (breaks if internals change)
- No type checking
- Verbose
```

### Proposed (DI Override)

```python
# Test setup - clean
def test_indexer(container):
    # Clean override at container level
    container.override(EmbeddingProvider, MockEmbeddingProvider())
    container.override(VectorStoreProvider, MockVectorStore())
    
    # Container handles injection
    indexer = await container.resolve(Indexer)
    
    # Test...

Benefits:
- Type-safe overrides
- Tests interface, not implementation
- Robust (survives internal changes)
- Concise
```

## Provider Factory Example

```python
# codeweaver/di/providers.py

async def get_embedding_provider() -> EmbeddingProvider:
    """Factory for embedding provider.
    
    Encapsulates all complex instantiation logic:
    - Settings resolution
    - Capabilities lookup
    - Provider registration
    - Error handling
    
    Services just declare: embedding: EmbeddingDep
    """
    from codeweaver.common.registry import get_provider_registry
    from codeweaver.common.registry.utils import get_model_config
    
    # 1. Get configuration
    config = get_model_config("embedding")
    if not config:
        raise ConfigurationError("No embedding provider configured")
    
    # 2. Extract settings
    provider_enum = config["provider"]
    model_settings = config["model_settings"]
    provider_settings = config.get("provider_settings")
    model_name = model_settings["model"]
    
    # 3. Get registries
    registry = get_provider_registry()
    model_registry = registry.get_model_registry()
    
    # 4. Resolve capabilities
    capabilities = model_registry.get_embedding_capabilities(
        provider_enum,
        model_name,
    )
    
    if not capabilities:
        raise ConfigurationError(
            f"No capabilities found for {provider_enum}:{model_name}"
        )
    
    # 5. Instantiate with full context
    return registry.get_embedding_provider_instance(
        provider_enum,
        singleton=True,
        capabilities=capabilities[0],
        model_settings=model_settings,
        provider_settings=provider_settings,
    )

# Type alias for clean service signatures
EmbeddingDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
```

## Migration Timeline

```
v0.1 (Current)
├─ Manual dependency fetching
└─ Registry pattern

v0.2 Early (Phase 1)
├─ DI infrastructure added
├─ Old pattern still works
└─ New pattern available

v0.2 Mid (Phase 2)
├─ Core services use DI
├─ Old pattern still works
└─ Both patterns documented

v0.2 Late (Phase 3 - Optional)
├─ pydantic-ai integrated
├─ Data sources via DI
└─ Old pattern still works

v0.3 Early (Phase 4)
├─ Advanced DI features
├─ Old pattern deprecated (warnings)
└─ Migration guide published

v0.3 Late (Phase 5)
├─ All code uses DI
├─ Registry simplified
└─ Old pattern still works (deprecated)

v0.4 (Future)
├─ Old pattern removed
└─ Breaking change release
```

## Key Design Principles

1. **Proven Patterns**: FastAPI-inspired (Constitutional Principle II)
2. **Type Safety**: Full type inference, IDE support
3. **Simplicity**: Complexity in factories, not services
4. **Testability**: Override mechanism for clean testing
5. **Incremental**: Phase-by-phase, backward compatible
6. **Lifecycle**: Startup/shutdown hooks built-in
7. **Provider Agnostic**: Uniform across all provider types

---

See full details in [dependency-injection-architecture-plan.md](./dependency-injection-architecture-plan.md)
