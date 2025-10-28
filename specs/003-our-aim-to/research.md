<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Phase 0: Research & Technical Decisions

**Feature**: CodeWeaver v0.1 Release
**Date**: 2025-10-27
**Status**: Complete - All decisions resolved in spec clarifications

## Research Summary

All technical decisions were resolved during the feature specification clarification process (see `spec.md` Session 2025-10-27). No additional research required for Phase 0.

## Technology Decisions

### 1. MCP Server Framework

**Decision**: FastMCP

**Rationale**:
- Official FastMCP framework provides proven MCP server implementation
- Created by Anthropic (same team behind MCP protocol)
- Pydantic-based request/response handling (aligns with constitution)
- FastAPI-style interface (proven patterns)
- Already in dependencies (pyproject.toml)

**Alternatives Considered**:
- Custom MCP implementation: Rejected - violates "proven patterns" principle
- Other MCP frameworks: None mature enough at this time

**Evidence**:
- FastMCP documentation: https://github.com/anthropics/fastmcp
- Existing usage in codebase: `src/codeweaver/server.py`

### 2. Vector Database

**Decision**: Qdrant (local deployment with persistence)

**Rationale**:
- Native hybrid search support (dense + sparse vectors)
- High-performance local mode (no separate service needed for v0.1)
- Persistence to disk for development convenience
- Python client library with full type hints
- Already in dependencies (qdrant-client)

**Alternatives Considered**:
- ChromaDB: Limited sparse vector support
- Weaviate: Requires separate service deployment
- FAISS: No native hybrid search, complex integration

**Evidence**:
- Qdrant hybrid search docs: https://qdrant.tech/documentation/concepts/hybrid-search/
- Existing integration: `src/codeweaver/providers/vector/qdrant.py` (skeleton exists)

### 3. Dense Embedding Provider

**Decision**: VoyageAI (voyage-code-3 model)

**Rationale**:
- Code-specific embedding model optimized for semantic code search
- Higher quality than general-purpose models
- Competitive pricing and performance
- Already configured in default settings

**Alternatives Considered**:
- OpenAI text-embedding-ada-002: General purpose, not code-optimized
- Cohere embeddings: Good quality but higher cost
- Local models (sentence-transformers): Lower quality for code

**Evidence**:
- VoyageAI code embeddings: https://docs.voyageai.com/docs/embeddings
- Default config: `src/codeweaver/_settings.py` (VoyageSettings)

### 4. Sparse Embedding Provider

**Decision**: FastEmbed with prithivida/Splade-PP_en_v2 model

**Rationale**:
- Local execution (no API calls, cost-free)
- SPLADE architecture proven for sparse retrieval
- Fast inference for real-time queries
- Complements dense embeddings well
- Already in dependencies (fastembed)

**Alternatives Considered**:
- BM25: Traditional keyword search, less semantic
- Custom TF-IDF: Requires manual tuning and maintenance
- API-based sparse: Adds latency and cost

**Evidence**:
- FastEmbed documentation: https://qdrant.github.io/fastembed/
- SPLADE paper: https://arxiv.org/abs/2109.10086
- Existing integration points in middleware

### 5. Reranking Model

**Decision**: VoyageAI rerank-2.5

**Rationale**:
- Highest quality reranking for code context
- Optimized for code-specific relevance scoring
- Same provider as embeddings (simplified auth)
- Proven in production semantic search systems

**Alternatives Considered**:
- Cohere rerank: Good quality, higher cost
- Cross-encoder models (local): Lower quality, slower inference
- No reranking: Lower search quality (unacceptable)

**Evidence**:
- VoyageAI reranker docs: https://docs.voyageai.com/docs/reranker
- Default config: `src/codeweaver/_settings.py`

### 6. CLI Framework

**Decision**: Cyclopts

**Rationale**:
- Modern Python CLI framework with type safety
- Pydantic integration for argument validation
- Automatic help generation from type hints
- Already in dependencies
- Simpler than Click/Typer for typed interfaces

**Alternatives Considered**:
- Click: Less type-safe, more boilerplate
- Typer: Good but cyclopts better Pydantic integration
- argparse: Too low-level for modern Python

**Evidence**:
- Cyclopts documentation: https://cyclopts.readthedocs.io/
- Entry point defined: `pyproject.toml` (codeweaver = "codeweaver.cli.app:main")

### 7. Code Chunking Strategy

**Decision**: AST-based chunking with ast-grep-py (200-800 tokens per chunk)

**Rationale**:
- Preserves complete syntactic units (functions, classes, methods)
- Language-agnostic AST analysis (20+ languages supported)
- Better semantic coherence than arbitrary text splitting
- Existing middleware: `src/codeweaver/middleware/chunking.py`

**Alternatives Considered**:
- Fixed-size text chunks: Breaks logical units, poor semantic quality
- Tree-sitter: More complex integration, similar results
- Manual language parsers: Violates "proven patterns" principle

**Evidence**:
- ast-grep documentation: https://ast-grep.github.io/
- Chunking implementation: `src/codeweaver/middleware/chunking.py`
- FR-006 acceptance criteria: ≥95% complete syntactic units

### 8. File Discovery Strategy

**Decision**: rignore library (gitignore-aware file walking)

**Rationale**:
- Respects .gitignore rules automatically
- Fast recursive directory traversal
- Rust-based performance (ripgrep foundation)
- Simple Python bindings
- Already in dependencies

**Alternatives Considered**:
- pathlib.rglob: No gitignore support
- gitpython: Slower, more complex
- Custom implementation: Violates "proven patterns"

**Evidence**:
- rignore on PyPI: https://pypi.org/project/rignore/
- Existing usage: `src/codeweaver/middleware/filtering.py`

### 9. Configuration Management

**Decision**: pydantic-settings with TOML + environment variables

**Rationale**:
- Hierarchical config: env vars override TOML override defaults
- Type-safe validation (Pydantic)
- Auto-generated schema documentation
- .env file support for development
- Constitutional requirement (Configuration Management)

**Alternatives Considered**:
- Pure TOML (tomli): No validation, no env var hierarchy
- ConfigParser: Python 2 era, no type safety
- JSON: No comments, less human-friendly

**Evidence**:
- pydantic-settings docs: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- Existing implementation: `src/codeweaver/_settings.py`

### 10. Error Handling Patterns

**Decision**: Circuit breaker + exponential backoff for external services

**Rationale**:
- Prevents cascade failures (vector store/API outages)
- Graceful degradation (sparse-only search fallback)
- User-visible error communication (health endpoint, CLI warnings)
- Specified in clarifications (FR-008a, FR-009c, FR-021a)

**Alternatives Considered**:
- Simple retry: Can amplify outages
- Immediate failure: Poor user experience
- Silent fallback: Confusing behavior

**Evidence**:
- Circuit breaker pattern: Martin Fowler's "Release It!" book
- Spec requirements: FR-008a (circuit breaker state machine)
- Health endpoint: Circuit breaker state exposed

## Performance Research

### Search Query Performance

**Target**: <3s for ≤10k files, <10s for ≤100k files (FR-037)

**Approach**:
- Qdrant local mode: In-process, no network latency
- Hybrid search: Parallel dense + sparse retrieval
- Reranking: Batch processing of top-k candidates
- Benchmark testing: Required before v0.1 release

**Evidence**:
- Qdrant benchmarks: https://qdrant.tech/benchmarks/
- VoyageAI latency: ~200ms for embedding, ~150ms for reranking (batch)

### Indexing Performance

**Target**: ≥100 files/minute (FR-038)

**Approach**:
- Batch embedding requests (max 10 concurrent)
- AST parsing: ast-grep-py is highly optimized (Rust core)
- Checkpoint every 100 files (resumption on interruption)
- Progress monitoring: /health/ endpoint updates every 5s

**Evidence**:
- ast-grep performance: https://ast-grep.github.io/guide/tooling-overview.html#performance
- VoyageAI embedding batch: 100 chunks/request supported

## Testing Strategy Research

### Reference Test Suite (FR-036)

**Approach**:
- Dogfooding: Test against CodeWeaver's own codebase
- 20+ query/result pairs covering all IntentType values
- Quality metrics: Precision@3 ≥70%, Precision@5 ≥80%
- CI integration: Run on every PR affecting search/ranking

**Test Categories**:
- UNDERSTAND intent: "how does chunking work", "authentication logic"
- IMPLEMENT intent: "database connection pooling", "error handling patterns"
- DEBUG intent: "where are exceptions raised", "logging configuration"
- OPTIMIZE intent: "performance bottlenecks", "caching strategies"
- TEST intent: "test fixtures for auth", "integration test examples"
- CONFIGURE intent: "settings validation", "config file format"
- DOCUMENT intent: "docstring examples", "API documentation"

**Evidence**:
- Test file: `tests/integration/reference_queries.yml` (to be created in Phase 1)
- Evaluation framework: pytest with custom fixtures for precision calculation

### Integration Testing

**Focus**: Complete workflows, not implementation details

**Key Scenarios**:
1. Server startup → health check → indexing → search → results
2. Error recovery: API timeout → sparse fallback → warning displayed
3. Concurrent operations: Multiple searches during indexing
4. Graceful shutdown: SIGTERM → checkpoint → clean exit

**Evidence**:
- Constitutional requirement: "Testing Philosophy" (effectiveness over coverage)
- Spec examples: See "Concrete Scenario Examples" in spec.md

## Observability Research

### Structured Logging (FR-040)

**Format**: JSON for machines, structured text for humans

**Required Fields**:
- timestamp (ISO8601), level, component, operation
- duration_ms, request_id (UUID), error, context

**Log Levels by Component**:
- DEBUG: AST parsing details, chunk boundary decisions
- INFO: Indexing progress, search queries, configuration loading
- WARNING: Fallback activations, service degradation, high error counts
- ERROR: API failures, vector store unavailable, indexing crashes
- CRITICAL: Irrecoverable failures requiring restart

**Evidence**:
- Structured logging best practices: https://www.structlog.org/
- FR-040 specification in feature spec

### Metrics Collection (FR-041)

**Health Endpoint Metrics**:
- Search: latency percentiles (p50, p95, p99), total queries, intent distribution
- Indexing: files/second, chunks created, errors, duration
- Services: API latency, circuit breaker state, operation counts

**Implementation**:
- In-memory aggregation for recent metrics (last 100 queries)
- Prometheus-compatible format for future monitoring integration
- Exposed via /health/ endpoint JSON response

**Evidence**:
- FR-010-Enhanced health endpoint format specification
- FR-041 key metrics listing

## API Documentation Research

### MCP Tool Contract

**find_code Interface** (codeweaver/agent_api/find_code.py):
```python
async def find_code(
    query: str,
    *,
    intent: IntentType | None = None,
    token_limit: int = 10000,
    include_tests: bool = False,
    focus_languages: tuple[str, ...] | None = None,
    max_results: int = 50
) -> FindCodeResponseSummary
```

**Response Structure** (codeweaver/agent_api/models.py):
- FindCodeResponseSummary: Top-level response with metadata
- CodeMatch: Individual results with relevance scores
- DiscoveredFile: File metadata and language detection
- CodeChunk: Content with line ranges and embeddings

**Evidence**:
- FR-014a, FR-014b interface specifications
- Existing models: `src/codeweaver/agent_api/models.py`

### CLI Command Interface

**Commands** (codeweaver/cli/app.py):
1. `codeweaver server` - Start MCP server
2. `codeweaver search` - Execute search query
3. `codeweaver config` - Display configuration
4. `codeweaver status` - Show indexing progress (needs implementation)

**Evidence**:
- FR-011a through FR-011d command specifications
- Entry point: `pyproject.toml` [project.scripts]

## Open Questions

None. All technical decisions resolved through spec clarifications.

## Next Steps (Phase 1)

1. Generate data model documentation (data-model.md)
2. Create API contracts (contracts/ directory)
3. Generate contract tests (tests/contract/)
4. Extract quickstart scenarios (quickstart.md)
5. Update agent context file (CLAUDE.md or AGENTS.md)
6. Re-verify constitution compliance

---

**Phase 0 Status**: ✅ COMPLETE
**All Decisions**: Evidence-based with documented rationale
**Ready for Phase 1**: Data model and contract generation
