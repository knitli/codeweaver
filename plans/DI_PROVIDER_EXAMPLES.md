<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Provider Integration Examples - Before & After DI

This document shows concrete examples of how each provider type will work before and after DI implementation.

## Table of Contents

1. [Dense Embedding Providers](#1-dense-embedding-providers)
2. [Sparse Embedding Providers](#2-sparse-embedding-providers)
3. [Reranking Providers](#3-reranking-providers)
4. [Vector Store Providers](#4-vector-store-providers)
5. [Agent Providers (pydantic-ai)](#5-agent-providers-pydantic-ai)
6. [Data Source Providers](#6-data-source-providers)
7. [Multiple Providers](#7-multiple-providers-advanced)

---

## 1. Dense Embedding Providers

### Current (alpha1) - Manual

```python
# codeweaver/engine/indexer.py

def _get_embedding_instance() -> EmbeddingProvider[Any] | None:
    """Helper to get embedding provider - duplicated everywhere."""
    from codeweaver.common.registry import get_provider_registry
    
    registry = get_provider_registry()
    if provider := registry.get_embedding_provider():
        return registry.get_embedding_provider_instance(
            provider=provider, 
            singleton=True
        )
    return None

class Indexer:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.embedding = _get_embedding_instance()  # Manual!
        if not self.embedding:
            raise ConfigurationError("No embedding provider configured")
    
    async def embed_chunks(self, chunks: list[CodeChunk]):
        return await self.embedding.embed_documents(chunks)

# Testing - brittle
def test_indexer(tmp_path):
    indexer = Indexer(tmp_path)
    # Replace after construction - fragile
    indexer.embedding = MockEmbeddingProvider()
    # test...
```

### Proposed (v0.2+) - DI

```python
# codeweaver/di/providers.py

from typing import Annotated
from codeweaver.di.depends import Depends
from codeweaver.providers.embedding.providers.base import EmbeddingProvider

async def get_embedding_provider() -> EmbeddingProvider:
    """Factory encapsulates all complexity."""
    from codeweaver.common.registry import get_provider_registry
    from codeweaver.common.registry.utils import get_model_config
    
    config = get_model_config("embedding")
    if not config:
        raise ConfigurationError("No embedding provider configured")
    
    registry = get_provider_registry()
    return registry.get_embedding_provider_instance(
        provider=config["provider"],
        singleton=True,
    )

# Type alias for clean signatures
EmbeddingDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]

# codeweaver/engine/indexer.py

class Indexer:
    def __init__(
        self,
        project_root: Path,
        embedding: EmbeddingDep,  # Declarative!
    ):
        self.project_root = project_root
        self.embedding = embedding  # Guaranteed non-None by DI
    
    async def embed_chunks(self, chunks: list[CodeChunk]):
        return await self.embedding.embed_documents(chunks)

# Testing - clean
@pytest.fixture
def container():
    container = Container()
    container.override(EmbeddingProvider, MockEmbeddingProvider())
    return container

async def test_indexer(tmp_path, container):
    indexer = await container.resolve(
        Indexer,
        project_root=tmp_path,  # Non-injected args passed normally
    )
    # embedding already mocked via container
    # test...
```

---

## 2. Sparse Embedding Providers

### Current - Manual

```python
# Separate helper, similar boilerplate
def _get_sparse_embedding_instance() -> EmbeddingProvider[Any] | None:
    from codeweaver.common.registry import get_provider_registry
    
    registry = get_provider_registry()
    if provider := registry.get_embedding_provider(sparse=True):
        return registry.get_sparse_embedding_provider_instance(
            provider=provider,
            singleton=True
        )
    return None

class HybridSearchService:
    def __init__(self):
        self.dense_embedding = _get_embedding_instance()
        self.sparse_embedding = _get_sparse_embedding_instance()
```

### Proposed - DI

```python
# codeweaver/di/providers.py

async def get_sparse_embedding_provider() -> EmbeddingProvider:
    """Factory for sparse embeddings."""
    from codeweaver.common.registry import get_provider_registry
    from codeweaver.common.registry.utils import get_model_config
    
    config = get_model_config("sparse_embedding")
    if not config:
        return None  # Sparse is optional
    
    registry = get_provider_registry()
    return registry.get_sparse_embedding_provider_instance(
        provider=config["provider"],
        singleton=True,
    )

SparseEmbeddingDep = Annotated[
    EmbeddingProvider | None,
    Depends(get_sparse_embedding_provider)
]

# Usage
class HybridSearchService:
    def __init__(
        self,
        dense_embedding: EmbeddingDep,
        sparse_embedding: SparseEmbeddingDep,  # Optional!
    ):
        self.dense_embedding = dense_embedding
        self.sparse_embedding = sparse_embedding
```

---

## 3. Reranking Providers

### Current - Manual

```python
def _get_reranking_instance() -> RerankingProvider[Any] | None:
    from codeweaver.common.registry import get_provider_registry
    
    registry = get_provider_registry()
    if provider := registry.get_reranking_provider():
        return registry.get_reranking_provider_instance(
            provider=provider,
            singleton=True
        )
    return None

class SearchService:
    def __init__(self):
        self.embedding = _get_embedding_instance()
        self.reranker = _get_reranking_instance()  # May be None
```

### Proposed - DI

```python
# codeweaver/di/providers.py

async def get_reranking_provider() -> RerankingProvider | None:
    """Factory for reranking (optional)."""
    from codeweaver.common.registry import get_provider_registry
    from codeweaver.common.registry.utils import get_model_config
    
    config = get_model_config("reranking")
    if not config:
        return None  # Reranking is optional
    
    registry = get_provider_registry()
    return registry.get_reranking_provider_instance(
        provider=config["provider"],
        singleton=True,
    )

RerankingDep = Annotated[
    RerankingProvider | None,
    Depends(get_reranking_provider)
]

# Usage
class SearchService:
    def __init__(
        self,
        embedding: EmbeddingDep,
        reranker: RerankingDep = None,  # Optional with default
    ):
        self.embedding = embedding
        self.reranker = reranker
    
    async def search(self, query: str, candidates: list):
        # Use reranker if available
        if self.reranker:
            return await self.reranker.rerank(query, candidates)
        return candidates
```

---

## 4. Vector Store Providers

### Current - Manual

```python
def _get_vector_store_instance() -> VectorStoreProvider[Any] | None:
    from codeweaver.common.registry import get_provider_registry
    
    registry = get_provider_registry()
    if provider := registry.get_vector_store_provider():
        return registry.get_vector_store_provider_instance(
            provider=provider,
            singleton=True
        )
    return None

class Indexer:
    def __init__(self):
        self.embedding = _get_embedding_instance()
        self.vector_store = _get_vector_store_instance()
```

### Proposed - DI

```python
# codeweaver/di/providers.py

async def get_vector_store() -> VectorStoreProvider:
    """Factory for vector store."""
    from codeweaver.common.registry import get_provider_registry
    from codeweaver.common.registry.utils import get_vector_store_config
    
    config = get_vector_store_config()
    if not config:
        raise ConfigurationError("No vector store configured")
    
    registry = get_provider_registry()
    return registry.get_vector_store_provider_instance(
        provider=config["provider"],
        singleton=True,
        **config.get("provider_settings", {}),
    )

VectorStoreDep = Annotated[VectorStoreProvider, Depends(get_vector_store)]

# Usage
class Indexer:
    def __init__(
        self,
        embedding: EmbeddingDep,
        vector_store: VectorStoreDep,
    ):
        self.embedding = embedding
        self.vector_store = vector_store
```

---

## 5. Agent Providers (pydantic-ai)

### Current - Not Integrated

```python
# Currently not accessible in CodeWeaver v0.1
# pydantic-ai agents wired but not integrated

# If we were to integrate manually, would look like:
from pydantic_ai import Agent

def _get_agent_instance():
    # Complex: need to parse model string, handle settings, etc.
    from codeweaver.common.registry.utils import get_model_config
    
    config = get_model_config("agent")
    model_name = config["model"]  # e.g., "openai:gpt-4"
    settings = config.get("model_settings")
    
    # pydantic-ai's instantiation pattern
    return Agent(model_name, settings=settings)

class ContextAgent:
    def __init__(self):
        self.agent = _get_agent_instance()  # Manual
```

### Proposed - DI (Phase 3)

```python
# codeweaver/di/providers.py

from pydantic_ai import Agent

async def get_pydantic_agent() -> Agent:
    """Factory for pydantic-ai agents.
    
    Respects pydantic-ai's native instantiation pattern.
    """
    from codeweaver.common.registry.utils import get_model_config
    
    config = get_model_config("agent")
    if not config:
        raise ConfigurationError("No agent provider configured")
    
    model_name = config["model"]  # e.g., "openai:gpt-4"
    settings = config.get("model_settings")
    
    # Use pydantic-ai's pattern directly
    return Agent(model_name, settings=settings)

AgentDep = Annotated[Agent, Depends(get_pydantic_agent)]

# Usage
class ContextAgent:
    def __init__(
        self,
        agent: AgentDep,  # pydantic-ai Agent injected!
    ):
        self.agent = agent
    
    async def curate_context(self, query: str, candidates: list):
        result = await self.agent.run(
            f"Curate best results for: {query}",
            deps={"candidates": candidates},
        )
        return result.data
```

---

## 6. Data Source Providers

### Current - Not Integrated

```python
# Currently not accessible
# Tavily and DuckDuckGo tools exist but aren't integrated

# Manual integration would be complex:
from pydantic_ai.tools import TavilyWebSearchTool

def _get_tavily_tool():
    import os
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return None
    return TavilyWebSearchTool(api_key=api_key)

class ResearchAgent:
    def __init__(self):
        self.tavily = _get_tavily_tool()
```

### Proposed - DI (Phase 3)

```python
# codeweaver/di/providers.py

from pydantic_ai.tools import TavilyWebSearchTool, DuckDuckGoSearchTool

async def get_tavily_search() -> TavilyWebSearchTool | None:
    """Factory for Tavily search tool."""
    from codeweaver.common.registry.utils import get_data_configs
    
    configs = get_data_configs()
    tavily_config = next(
        (c for c in configs if c["provider"] == Provider.TAVILY),
        None
    )
    
    if not tavily_config:
        return None  # Optional
    
    api_key = tavily_config["api_key"]
    return TavilyWebSearchTool(api_key=api_key)

async def get_duckduckgo_search() -> DuckDuckGoSearchTool:
    """Factory for DuckDuckGo search tool (no auth needed)."""
    return DuckDuckGoSearchTool()

TavilyDep = Annotated[
    TavilyWebSearchTool | None,
    Depends(get_tavily_search)
]
DuckDuckGoDep = Annotated[DuckDuckGoSearchTool, Depends(get_duckduckgo_search)]

# Usage
class ResearchAgent:
    def __init__(
        self,
        agent: AgentDep,
        tavily: TavilyDep = None,
        duckduckgo: DuckDuckGoDep,
    ):
        self.agent = agent
        self.tavily = tavily
        self.duckduckgo = duckduckgo
    
    async def research(self, query: str):
        # Use tavily if available, else duckduckgo
        search_tool = self.tavily or self.duckduckgo
        return await search_tool.search(query)
```

---

## 7. Multiple Providers (Advanced)

### Current - Very Verbose

```python
# services/advanced_search.py

class AdvancedSearchService:
    def __init__(self):
        # Manual fetching for each dependency
        self.dense_embedding = _get_embedding_instance()
        self.sparse_embedding = _get_sparse_embedding_instance()
        self.vector_store = _get_vector_store_instance()
        self.reranker = _get_reranking_instance()
        
        # Validation
        if not self.dense_embedding:
            raise ConfigurationError("Dense embedding required")
        if not self.vector_store:
            raise ConfigurationError("Vector store required")
        
        # Optional providers
        self.has_sparse = self.sparse_embedding is not None
        self.has_reranking = self.reranker is not None
    
    async def search(self, query: str):
        # Dense search
        dense_vec = await self.dense_embedding.embed_query(query)
        candidates = await self.vector_store.search(dense_vec)
        
        # Optional sparse
        if self.has_sparse:
            sparse_vec = await self.sparse_embedding.embed_query(query)
            sparse_results = await self.vector_store.search(sparse_vec)
            candidates = merge_results(candidates, sparse_results)
        
        # Optional reranking
        if self.has_reranking:
            candidates = await self.reranker.rerank(query, candidates)
        
        return candidates
```

### Proposed - Clean & Declarative

```python
# services/advanced_search.py

from codeweaver.di.providers import (
    EmbeddingDep,
    SparseEmbeddingDep,
    VectorStoreDep,
    RerankingDep,
)

class AdvancedSearchService:
    def __init__(
        self,
        dense_embedding: EmbeddingDep,        # Required
        vector_store: VectorStoreDep,         # Required
        sparse_embedding: SparseEmbeddingDep = None,  # Optional
        reranker: RerankingDep = None,        # Optional
    ):
        self.dense_embedding = dense_embedding
        self.vector_store = vector_store
        self.sparse_embedding = sparse_embedding
        self.reranker = reranker
    
    async def search(self, query: str):
        # Dense search
        dense_vec = await self.dense_embedding.embed_query(query)
        candidates = await self.vector_store.search(dense_vec)
        
        # Optional sparse
        if self.sparse_embedding:
            sparse_vec = await self.sparse_embedding.embed_query(query)
            sparse_results = await self.vector_store.search(sparse_vec)
            candidates = merge_results(candidates, sparse_results)
        
        # Optional reranking
        if self.reranker:
            candidates = await self.reranker.rerank(query, candidates)
        
        return candidates

# Testing is trivial!
@pytest.fixture
def search_service(container):
    # Override with mocks
    container.override(EmbeddingProvider, MockEmbedding())
    container.override(VectorStoreProvider, MockVectorStore())
    container.override(RerankingProvider, MockReranker())
    
    return await container.resolve(AdvancedSearchService)

async def test_search_with_reranking(search_service):
    # All dependencies mocked
    results = await search_service.search("test query")
    # assert...
```

---

## Summary: Benefits by Provider Type

| Provider Type | Current Pain | DI Benefit | Impact |
|--------------|--------------|------------|--------|
| **Embedding (Dense)** | Helper functions everywhere | Single factory, declarative | ⭐⭐⭐⭐⭐ |
| **Embedding (Sparse)** | Duplicate boilerplate | Optional dependency pattern | ⭐⭐⭐⭐ |
| **Reranking** | Manual None checks | Clean optional injection | ⭐⭐⭐⭐ |
| **Vector Store** | Complex config resolution | Factory handles complexity | ⭐⭐⭐⭐⭐ |
| **Agent (pydantic-ai)** | Not integrated yet | Native integration via DI | ⭐⭐⭐⭐⭐ |
| **Data Sources** | Not integrated yet | Clean tool injection | ⭐⭐⭐⭐ |
| **Multiple Providers** | Very verbose, brittle | Declarative, type-safe | ⭐⭐⭐⭐⭐ |

---

## Code Metrics Comparison

### Lines of Code (LoC)

| Operation | Current (v0.1) | Proposed (v0.2+) | Reduction |
|-----------|----------------|------------------|-----------|
| Single provider service | ~20 LoC | ~5 LoC | **75%** |
| Multi-provider service | ~40 LoC | ~10 LoC | **75%** |
| Test setup (single) | ~10 LoC | ~3 LoC | **70%** |
| Test setup (multi) | ~25 LoC | ~5 LoC | **80%** |

### Boilerplate Distribution

**Current**:
- 60% boilerplate (fetching, validation, None checks)
- 40% business logic

**Proposed**:
- 15% boilerplate (type annotations)
- 85% business logic

**Net gain**: ~70% more focus on business logic

---

## Migration Path Examples

### Simple Service (Easy)

```python
# Step 1: Add DI imports
from codeweaver.di.providers import EmbeddingDep

# Step 2: Replace manual fetching with injection
class MyService:
    # Before
    def __init__(self):
        self.embedding = _get_embedding_instance()
    
    # After
    def __init__(self, embedding: EmbeddingDep):
        self.embedding = embedding

# Step 3: Update tests
@pytest.fixture
def my_service(container):
    container.override(EmbeddingProvider, MockEmbedding())
    return await container.resolve(MyService)
```

### Complex Service (Moderate)

```python
# Before: 40 lines of manual wiring
class ComplexService:
    def __init__(self):
        self.dense_embedding = _get_embedding_instance()
        self.sparse_embedding = _get_sparse_embedding_instance()
        self.vector_store = _get_vector_store_instance()
        self.reranker = _get_reranking_instance()
        
        if not self.dense_embedding:
            raise ConfigurationError("...")
        # ... more validation

# After: 10 lines, declarative
class ComplexService:
    def __init__(
        self,
        dense_embedding: EmbeddingDep,
        vector_store: VectorStoreDep,
        sparse_embedding: SparseEmbeddingDep = None,
        reranker: RerankingDep = None,
    ):
        self.dense_embedding = dense_embedding
        self.vector_store = vector_store
        self.sparse_embedding = sparse_embedding
        self.reranker = reranker
```

---

## Conclusion

DI provides consistent patterns across all provider types while:
1. Reducing boilerplate by 70-80%
2. Improving type safety
3. Simplifying testing dramatically
4. Enabling future provider types seamlessly
5. Maintaining backward compatibility during migration

See [dependency-injection-architecture-plan.md](./dependency-injection-architecture-plan.md) for full details.
