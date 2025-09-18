<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Implementation Plan
## Revised Architecture-Driven Roadmap

*Based on current implementation state as of January 2025*

---

## Executive Summary

CodeWeaver has evolved beyond its original architectural vision into a sophisticated semantic code search MCP server with enhanced pydantic-ai integration, span-based code tracking, and advanced metadata systems. This plan reflects the current implementation reality and provides a focused roadmap to complete the missing integration components.

**Current State**: Enhanced foundational architecture with sophisticated type systems and provider abstractions, but missing key integration pieces for a functional MCP server.

**Goal**: Complete integration work to deliver a working MCP server that leverages the superior architecture already built.

---

## Architectural Assessment

### ✅ **Strengths - What's Been Built**

**Enhanced Type System**:
- Sophisticated `Span`/`SpanGroup` architecture for precise code location tracking
- Immutable data structures with set operations (union, intersection, difference)
- Rich metadata system with semantic AST information
- Comprehensive `CodeChunk` and `CodeMatch` representations

**pydantic-ai Deep Integration**:
- Complete agent provider ecosystem integration
- Advanced settings system with multi-source configuration
- Capability-based provider selection matrix
- Dynamic provider inference and instantiation

**Sophisticated Data Structures**:
- `DiscoveredFile` with computed properties and metadata
- `ExtKind` for language and chunk type classification
- `SemanticMetadata` for AST node tracking
- Comprehensive response models with execution metadata

**Provider Architecture**:
- Abstract interfaces for embedding, vector store, and agent providers
- Multi-provider support (VoyageAI, FastEmbed, Qdrant, major cloud providers)
- Provider capability matrix with dynamic selection
- Settings registry foundation (though not implemented)

**Advanced Search System** (Vendored):
- Production-ready filtering system with pydantic integration
- Comprehensive filter types (keyword, numeric, range, geospatial, boolean)
- Dynamic tool signature generation via `@wrap_filters` decorator
- 80% vendor-agnostic design suitable for multi-provider support

### ❌ **Critical Gaps - What Needs Completion**

**Core Integration**:
- ✅ CLI implementation (comprehensive with server, search, config commands)
- Provider registry system (`_registry.py`)
- FastMCP middleware and application state management
- Vector store implementations (Qdrant incomplete, memory store basic)
- Integration of vendored search system into `find_code` tool interface

**Pipeline Components**:
- Background indexing with file watching
- Semantic embedding integration
- pydantic-graph orchestration
- Query intent analysis implementation

**Infrastructure**:
- Comprehensive testing framework
- Error handling and graceful degradation
- Performance optimization and caching
- Authentication/authorization middleware

---

## Implementation Phases

### **Phase 1: Core Integration (Weeks 1-2)**
*Complete the missing pieces to create a functional MCP server*

#### Week 1: Foundation Integration
- ✅ **CLI Implementation**: Already completed with comprehensive server, search, and config commands
- **Provider Registry**: Implement `_registry.py` for dynamic provider registration
- **Sophisticated statistics tracking system** in `_statistics.py` -- needs integration into architecture for continuous updating
- **FastMCP Middleware**: Complete application state management and context handling
   - Need to consider FastMCP server's lifespan handling. The indexer should run as a background service, so we need to ensure the lifespan for certain services can continue beyond the start and end of an MCP session.
- **Basic Vector Store**: Complete in-memory vector store implementation

#### Week 2: Core Functionality  
- **Find Code Tool**: Integrate existing components into working `find_code` implementation
- **Advanced Search Integration**: Integrate vendored search system for rich filtering capabilities
- **File Discovery**: Complete integration of rignore-based discovery service
- **Text Search**: Enhance existing text search with span-based results and filterable fields
- **Basic Testing**: Essential test coverage for core workflows

**Deliverable**: Working MCP server with basic text search capabilities

### **Phase 2: Semantic Search (Weeks 3-4)**
*Add semantic search capabilities using the enhanced architecture*

#### Week 3: Embedding Integration
- **Embedding Providers**: Complete VoyageAI and FastEmbed implementations
- **Vector Store Integration**: Complete Qdrant implementation with span-based indexing
- **Chunking Strategy**: Implement AST-based chunking using existing semantic metadata
- **Cost Management**: Implement token budgeting and caching strategies

#### Week 4: Semantic Pipeline
- **Background Indexing**: Implement file watcher with incremental updates
- **Semantic Indexing**: Index codebases using span-based chunking and semantic metadata
- **Hybrid Search**: Combine semantic and text search with unified ranking
- **Intent Analysis**: Implement query intent classification using pydantic-ai agents

**Deliverable**: Full semantic search capabilities with background indexing

### **Phase 3: Advanced Features (Week 5)**
*Leverage the enhanced architecture for advanced capabilities*

#### Advanced Capabilities
- **pydantic-graph Pipeline**: Implement multi-stage workflow orchestration
- **Advanced Ranking**: Multi-signal, multi-source, ranking with semantic, syntactic, and keyword relevance
- **Performance Optimization**: Caching, batching, and response time optimization
- **Enhanced Metadata**: Leverage rich semantic metadata for improved search accuracy

#### Quality & Reliability
- **Comprehensive Testing**: Full test suite including unit, integration, and e2e tests
- **Error Handling**: Graceful degradation with fallback strategies
- **Documentation**: API documentation and usage guides
- **Monitoring**: Posthog telemetry integration and performance monitoring with statistics suite

**Deliverable**: Production-ready MCP server with advanced search capabilities

---

## Technical Implementation Details

### ✅ CLI Implementation (Completed)
The CLI is already comprehensively implemented with:
- **Server Command**: `codeweaver server` - Starts MCP server with configuration support
- **Search Command**: `codeweaver search` - Direct CLI search with multiple output formats (json, table, markdown)  
- **Config Command**: `codeweaver config` - Configuration management and validation
- **Rich Output**: Enhanced terminal output with tables, colors, and error handling
- **Error Handling**: Comprehensive exception handling with suggestions

### Provider Registry Implementation
```python
# src/codeweaver/_registry.py
from typing import Any
from codeweaver.embedding.base import EmbeddingProvider
from codeweaver.vector_stores.base import VectorStoreProvider

class ProviderRegistry:
    _embedding_providers: dict[str, EmbeddingProvider] = {}
    _vector_store_providers: dict[str, VectorStoreProvider] = {}
    
    @classmethod
    def register_embedding_provider(cls, name: str, provider_class: Type[EmbeddingProvider]) -> None:
        cls._embedding_providers[name] = provider_class
    
    @classmethod
    def get_embedding_provider(cls, name: str) -> Type[EmbeddingProvider]:
        return cls._embedding_providers[name]
```

### Enhanced Find Code Integration
```python
# Integration leveraging vendored search system + existing architecture
from codeweaver.services._wrap_filters import wrap_filters
from codeweaver.services._filter import FilterableField

# Define default filterable fields for code search
DEFAULT_FILTERABLE_FIELDS = {
    "language": FilterableField(
        name="language", 
        field_type="keyword", 
        condition="any",
        description="Programming languages to search"
    ),
    "file_type": FilterableField(
        name="file_type",
        field_type="keyword", 
        condition="==",
        description="Type of file (code, docs, config)"
    ),
    "created_after": FilterableField(
        name="created_at",
        field_type="float", 
        condition=">=",
        description="Files created after timestamp"
    )
}

@wrap_filters(
    original_func=find_code_implementation,
    filterable_fields=DEFAULT_FILTERABLE_FIELDS
)
async def find_code(
    query: str,
    intent: Optional[IntentType] = None,
    token_limit: int = 10000,
    include_tests: bool = True,
    context: Context = None,
    **dynamic_filters  # Generated from filterable fields
) -> FindCodeResponseSummary:
    
    # Convert filters to query_filter for vector store
    query_filter = make_filter(dynamic_filters) if dynamic_filters else None
    
    # Leverage existing span-based architecture with enhanced filtering
    discovered_files = await discovery_service.discover_files(
        include_tests=include_tests,
        query_filter=query_filter
    )
    
    # Enhanced semantic search with filtering
    semantic_matches = await semantic_search(query, discovered_files, query_filter)
    
    # Apply span-based result assembly
    code_matches = assemble_code_matches(semantic_matches, token_limit)
    
    return FindCodeResponseSummary(
        matches=code_matches,
        metadata=ExecutionMetadata(
            query=query,
            intent=intent,
            total_files_searched=len(discovered_files),
            filters_applied=query_filter
        )
    )
```

---

## Architecture Decisions Rationale

### **Why Span-Based Architecture is Superior**
The current implementation's span-based approach provides:
- **Precise Code Location**: Exact line/column tracking with set operations
- **Immutable Operations**: Thread-safe operations with functional programming benefits
- **Rich Metadata**: Semantic AST information attached to precise locations
- **Flexible Composition**: Union/intersection operations for complex queries

### **Why Enhanced pydantic-ai Integration**
The deep pydantic-ai integration enables:
- **Unified Provider Ecosystem**: Single configuration for all AI providers
- **Advanced Agent Capabilities**: Complex query analysis and intent classification
- **Type Safety**: Comprehensive validation and structured data handling
- **Future Extensibility**: Easy addition of new AI-powered features

### **Why Current Architecture Exceeds Original Plan**
- **More Sophisticated**: Current type system and metadata handling exceeds original vision
- **Better Patterns**: pydantic-ai integration provides superior patterns to original design
- **Enhanced Capabilities**: Span-based tracking enables more precise search than originally planned
- **Stronger Foundation**: Current architecture provides better foundation for advanced features
- **Production-Ready Search**: Vendored search system provides enterprise-grade filtering capabilities

---

## Migration Strategy

### **From Current State to Working System**

1. **Leverage Existing Components**: Use sophisticated data structures and provider architecture as-is
2. **Complete Integration Gaps**: Focus on missing CLI, registry, and middleware components
3. **Maintain Architecture Quality**: Preserve enhanced type system and span-based patterns
4. **Incremental Enhancement**: Build on existing foundation rather than replacing it

### **Risk Mitigation**
- **Incremental Delivery**: Each phase delivers working functionality
- **Fallback Strategies**: Text search fallback when semantic search fails
- **Quality Gates**: Testing and validation at each phase
- **Architecture Preservation**: Maintain superior patterns already established

---

## Success Metrics

### **Phase 1 Success Criteria**
- ✅ CLI starts MCP server successfully (CLI already implemented)
- ✅ Basic text search returns span-based results  
- ✅ Provider registry enables dynamic provider selection
- ✅ Essential test coverage (>70%) for core workflows

### **Phase 2 Success Criteria**
- ✅ Semantic search with embedding providers working
- ✅ Background indexing with file watching operational
- ✅ Hybrid search combining semantic and text results
- ✅ Cost management and caching implemented

### **Phase 3 Success Criteria**
- ✅ Production-ready performance (<2s response times)
- ✅ Comprehensive error handling and graceful degradation
- ✅ Full test coverage (>90%) including integration tests
- ✅ Documentation and monitoring ready for deployment

---

## Resource Requirements

### **Development Resources**
- **Phase 1**: 1-2 developers, 2 weeks
- **Phase 2**: 1-2 developers, 2 weeks  
- **Phase 3**: 1-2 developers, 1 week
- **Total**: 5 weeks with current enhanced foundation

### **Infrastructure Requirements**
- **Development**: Local Qdrant instance, API keys for embedding providers
- **Testing**: CI/CD pipeline with automated testing
- **Production**: Qdrant cluster, monitoring infrastructure, API rate limiting

---

## Conclusion

The current CodeWeaver implementation has evolved into a sophisticated foundation that exceeds the original architectural vision. The enhanced type system, span-based architecture, and deep pydantic-ai integration provide a superior foundation for semantic code search.

This plan focuses on completing the integration work needed to leverage this enhanced architecture into a working MCP server. By building on the sophisticated foundation already created, we can deliver a production-ready system more quickly and with better capabilities than originally planned.

**Key Insight**: Don't replace the enhanced architecture - complete it. The current implementation represents a superior evolution of the original vision that should be preserved and completed.