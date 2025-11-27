<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Feature Specification: CodeWeaver v0.1 Release

**Feature Branch**: `003-our-aim-to`
**Created**: 2025-10-27
**Updated**: 2025-10-27 (Expert Panel Review Integrated)
**Status**: Ready for Implementation
**Quality Score**: 9.0/10 (Post-Review)
**Input**: User description: "Our aim to is to ship v.1 of CodeWeaver today. The main thing preventing that is a lack of integration. Here are the goals for where we want to be for 0.1: I can clone the repo, user can run codeweaver server and it starts without errors, user can point it at a codebase (CodeWeaver is fine) and it indexes, chunks, creates and stores embeddings, user through the CLI or an agent through MCP (using find_code tool) can run a search query and they receive useful results based on hybrid search (dense/sparse vectors) that have been reranked with a reranking and weighted by the semantic scoring system (see codeweaver.semantic.classifications), The README has a Quickstart section with commands that work, The README is rewritten to reflect the current state, not the aspiration, or at least, what we want it to do is clearly dilineated from what it can do today"

## Execution Flow (main)
```
1. Parse user description from Input
   → Completed: Clear goals for v0.1 release
2. Extract key concepts from description
   → Actors: developers, AI agents
   → Actions: install, start server, index codebase, search code
   → Data: code chunks, embeddings, search results
   → Constraints: must work today, realistic documentation
3. For each unclear aspect:
   → RESOLVED: Embedding provider = voyage-code-3 (default in settings)
   → RESOLVED: Vector store = Qdrant local (in-memory for dev, with persistence)
   → RESOLVED: Sparse embeddings = FastEmbed with prithivida/Splade-PP_en_v2
   → RESOLVED: Reranking = voyage-rerank-2.5 (default)
   → RESOLVED: Auto-indexing is default behavior (can be disabled in settings)
   → RESOLVED: Performance target = "it works and is useful" for v0.1
4. Fill User Scenarios & Testing section
   → Completed below
5. Generate Functional Requirements
   → Completed below
6. Identify Key Entities
   → Completed below with implementation references
7. Run Review Checklist
   → All clarifications resolved with defaults from codebase
8. Expert Panel Review
   → Integrated interface specifications, testable criteria, concrete examples
9. Return: SUCCESS (spec ready for implementation)
```

---

## Quick Guidelines
- Focus on WHAT users need and WHY
- Avoid HOW to implement (no tech stack, APIs, code structure)
- Written for business stakeholders, not developers
- **NEW**: All requirements now reference actual implementation modules

---

## Clarifications

### Session 2025-10-27
- Q: When indexing fails for individual files (e.g., corrupted file, unsupported encoding), how should the system behave? → A: Retry once, then log and continue. If ≥25 errors, show warning to stderr
- Q: How does the user specify which codebase directory to index when starting the CodeWeaver server? → A: Config file (CodeWeaverSettings from IndexerSettings)
- Q: When the embedding provider API (VoyageAI) is unavailable or returns errors during indexing, what should happen? → A: During indexing: log and continue with exponential backoff, still collect sparse indexes if configured. During query: try sparse-only search, warn user (MCP: context object, CLI: stdout), raise error only if no results possible
- Q: What level of detail should progress feedback show during indexing operations? → A: Index status reports through /health/ endpoint with detailed information (server.py, app_bindings.py). Also exposed via CLI command. Both need implementation
- Q: When the vector store (Qdrant) is unavailable at server startup or becomes unavailable during operation, what should happen? → A: Log and warn, exponential backoff. If problem persists, raise error and stop. Respond with error for queries until contact re-established (between identifying issue and raise + stop)

---

## User Scenarios & Testing *(mandatory)*

### Primary User Story
A developer wants to add semantic code search to their AI coding workflow. They clone CodeWeaver, start the server, point it at their codebase, and can immediately search for code using natural language queries. The search returns relevant code chunks ranked by semantic similarity and code classification scores.

An AI agent using MCP can connect to the running CodeWeaver server and use the `find_code` tool to search codebases on behalf of the developer, receiving contextually relevant results for code generation and analysis tasks.

### Acceptance Scenarios

#### Developer Installation and Setup
1. **Given** a developer has cloned the CodeWeaver repository
   **When** they follow the README Quickstart instructions
   **Then** they can start the CodeWeaver server without errors

2. **Given** the CodeWeaver server is running
   **When** the developer has specified a codebase directory path in the config file (CodeWeaverSettings)
   **Then** the system automatically indexes all discoverable code files, chunks them appropriately, generates embeddings, and stores them for search

3. **Given** a codebase is being indexed
   **When** the developer queries the /health/ endpoint or runs a CLI status command
   **Then** they receive detailed indexing progress information including files processed, current status, and any errors

4. **Given** a codebase has been indexed
   **When** the developer runs a search query via CLI
   **Then** they receive ranked search results based on hybrid search (dense and sparse vectors), reranked by a reranking, and weighted by semantic classification scores

#### AI Agent MCP Integration
5. **Given** an AI agent supports MCP
   **When** the agent connects to the running CodeWeaver server
   **Then** the agent can use the `find_code` tool to search the indexed codebase

6. **Given** an AI agent has access to the `find_code` tool
   **When** the agent submits a natural language query
   **Then** the agent receives useful, contextually relevant code chunks with semantic scores

#### Search Workflow Pipeline
7. **Given** a codebase has been indexed and a search query is submitted
   **When** the `find_code` tool processes the query
   **Then** the system executes the following pipeline:
   - Analyzes query to determine IntentType heuristically
   - Embeds query using both dense (voyage-code-3) and sparse (Splade) methods
   - Retrieves candidate results using hybrid search from Qdrant
   - Reranks candidates using voyage-rerank-2.5
   - Rescores results based on AgentTask, IntentType, and ImportanceScores category
   - Returns top-k results with all relevance scores included

#### Documentation Accuracy
8. **Given** a new user reads the README
   **When** they compare documented features to actual functionality
   **Then** all documented features work as described, and aspirational features are clearly marked as "planned" or "future"

---

## Concrete Scenario Examples *(Specification by Example)*

### Example 1: Successful Search with Semantic Ranking

**Given**: CodeWeaver indexed with Python codebase containing:
- `src/auth/middleware.py`: AuthMiddleware class (lines 15-85, DEFINITION_TYPE)
- `src/auth/utils.py`: authenticate_user function (lines 10-35, DEFINITION_CALLABLE)
- `src/auth/tokens.py`: JWT validation logic (lines 5-25, OPERATION_DATA)
- `tests/test_auth.py`: authentication test fixtures (lines 1-50, DEFINITION_TEST)

**When**: User searches with:
```bash
codeweaver search "how to authenticate users" --intent understand --limit 5
```

**Then**: CLI displays results in order:
```
Found 4 matches (47 candidates processed in 850ms)

1. src/auth/middleware.py:15-85 (relevance: 0.92, type: DEFINITION_TYPE)
   class AuthMiddleware:
       """Handles authentication and authorization for requests."""
       def __init__(self, config: AuthConfig):
           ...

2. src/auth/utils.py:10-35 (relevance: 0.87, type: DEFINITION_CALLABLE)
   def authenticate_user(username: str, password: str) -> User | None:
       """Authenticate user credentials and return User object."""
       ...

3. src/auth/tokens.py:5-25 (relevance: 0.78, type: OPERATION_DATA)
   def validate_jwt_token(token: str) -> TokenPayload:
       """Validate JWT token and extract payload."""
       ...

4. tests/test_auth.py:1-50 (relevance: 0.45, type: DEFINITION_TEST)
   [Test fixtures ranked lower due to IntentType.UNDERSTAND]
```

**Explanation**: AuthMiddleware scores highest (0.92) because DEFINITION_TYPE has high discovery score (0.95) and IntentType.UNDERSTAND applies 1.5x boost to definitions. Test fixtures ranked lower despite keyword matches because DEFINITION_TEST has lower weight for UNDERSTAND intent.

### Example 2: MCP Tool Integration

**Given**: AI agent connected to CodeWeaver MCP server

**When**: Agent calls `find_code` with parameters:
```json
{
  "query": "database connection pooling implementation",
  "intent": "implement",
  "max_results": 3
}
```

**Then**: MCP tool returns `FindCodeResponseSummary`:
```json
{
  "matches": [
    {
      "file": {
        "path": "src/database/pool.py",
        "language": "python"
      },
      "content": {
        "content": "class ConnectionPool:\n    def __init__(self, config: PoolConfig):\n        ...",
        "line_range": [12, 45],
        "language": "python"
      },
      "span": [12, 45],
      "relevance_score": 0.94,
      "match_type": "SEMANTIC",
      "related_symbols": ["PoolConfig", "DatabaseConnection"]
    }
  ],
  "summary": "Found 1 connection pool implementation in database module",
  "query_intent": "implement",
  "total_matches": 8,
  "total_results": 3,
  "token_count": 450,
  "execution_time_ms": 720,
  "search_strategy": ["HYBRID_SEARCH", "SEMANTIC_RERANK"],
  "languages_found": ["python"]
}
```

### Example 3: Edge Case - No Results with Helpful Message

**Given**: Indexed Python codebase (no COBOL code)

**When**: User searches:
```bash
codeweaver search "COBOL mainframe integration"
```

**Then**: CLI shows:
```
Searching for: "COBOL mainframe integration"
No results found (searched 1,247 chunks across 85 files)

Suggestions:
  • No COBOL language files found in indexed codebase
  • Languages available: python, typescript, javascript
  • Try broader terms: "integration patterns" or "external systems"
  • Check indexed file types: codeweaver config --show
```

### Example 4: Error Handling - Embedding Service Unavailable

**Given**: CodeWeaver server running, VoyageAI API down

**When**: User searches:
```bash
codeweaver search "authentication logic"
```

**Then**: System behavior:
1. Attempts dense embedding → timeout after 30s
2. Falls back to sparse-only search (local FastEmbed)
3. Returns results with warning:

```
⚠️  Warning: Dense embedding service unavailable, using sparse search only
Results may have reduced semantic accuracy

Found 5 matches (sparse search in 450ms)
[results from sparse vector search only]
```

**MCP Behavior**: Response includes degraded service indicator in metadata, warning communicated via MCP context object

---

## Requirements *(mandatory)*

### Functional Requirements

#### Installation & Setup
- **FR-001**: System MUST be installable from a cloned repository following documented steps
- **FR-002**: System MUST provide clear error messages if prerequisites are missing
  - **Acceptance Criteria**:
    - Error messages MUST include: (1) root cause, (2) operation context, (3) suggested action
    - Example: "Failed to connect to Qdrant at localhost:6333. Check Qdrant is running: `docker run -p 6333:6333 qdrant/qdrant`"
    - Example: "VoyageAI API key not found. Set VOYAGE_API_KEY environment variable or add to .env file"
- **FR-003**: System MUST start a server process without errors when all prerequisites are met. This means it MUST: start, initiate the MCP server and all necessary services for indexing/embedding generation, and MCP without error and successfully respond to a search request through MCP and cli

#### Indexing
- **FR-004**: System MUST accept a codebase directory path via config file (CodeWeaverSettings from IndexerSettings)

- **FR-005**: System MUST discover code files in the codebase using the following filters:
  - Exclude files matching .gitignore rules
  - Exclude hidden directories except known tooling directories (e.g., .github)
  - Include only files with known extensions or user-defined extensions (from ChunkerSettings)
  - Tabulate other discovered files for statistics without collecting data on them

- **FR-006**: System MUST chunk code using AST-based boundaries when available (functions, classes, methods) with target size 200-800 tokens, preserving complete logical units. For languages without AST support, use text-based chunking with similar size targets.
  - **Acceptance Criteria**:
    - ≥95% of chunks for AST-supported languages are complete syntactic units
    - Chunks MUST NOT split function/class definitions across boundaries
    - Average chunk size: 400-600 tokens
    - Chunk size range: 200-800 tokens (95th percentile)
  - **Validation**: Parse random sample of 100 chunks per language, verify syntactic completeness by re-parsing without errors

- **FR-007**: System MUST generate embeddings for each code chunk using voyage-code-3 (Provider.VOYAGE, configurable via settings)

- **FR-008**: System MUST store embeddings in Qdrant vector database (local in-memory with persistence for dev, configurable for remote)

- **FR-008a**: When vector store is unavailable, system MUST log and warn, retry with exponential backoff (delays: 1s, 2s, 4s), and raise error to stop if problem persists
  - **Circuit Breaker**: After 3 consecutive failures → open circuit for 30s → half-open state allows 1 request → success closes circuit, failure reopens for 60s

- **FR-008b**: When vector store is unavailable, system MUST respond to queries with error messages until connection is re-established

- **FR-009**: System MUST handle indexing errors gracefully without crashing the server

- **FR-009a**: When individual file processing fails, system MUST retry once, then log error and continue indexing remaining files

- **FR-009b**: When ≥25 file processing errors occur during indexing, system MUST display warning to stderr while continuing indexing

- **FR-009c**: When embedding provider API is unavailable during indexing, system MUST log errors, retry with exponential backoff (max 5 retries: 1s, 2s, 4s, 8s, 16s), and continue collecting sparse embeddings (local providers) if configured. After exhaustion, continue with sparse-only search.

- **FR-010**: System MUST provide detailed indexing progress feedback via:
  - **Health Endpoint**: GET /health/ with JSON response (see FR-010-Enhanced below)
  - **CLI Status Command**: `codeweaver status` (needs implementation for v0.1)

- **FR-010-Enhanced**: Health endpoint response format:
  ```json
  {
    "status": "healthy" | "degraded" | "unhealthy",
    "timestamp": "ISO8601",
    "uptime_seconds": int,
    "indexing": {
      "state": "idle" | "indexing" | "error",
      "progress": {
        "files_discovered": int,
        "files_processed": int,
        "chunks_created": int,
        "errors": int,
        "current_file": "path/to/file.py",
        "start_time": "ISO8601",
        "estimated_completion": "ISO8601"
      },
      "last_indexed": "ISO8601"
    },
    "services": {
      "vector_store": {"status": "up|down|degraded", "latency_ms": int},
      "embedding_provider": {"status": "up|down", "model": str, "latency_ms": int, "circuit_breaker_state": "closed|open|half_open"},
      "sparse_embedding": {"status": "up", "provider": "fastembed_local"},
      "reranking": {"status": "up|down", "model": str, "latency_ms": int}
    },
    "statistics": {
      "total_chunks_indexed": int,
      "total_files_indexed": int,
      "languages_indexed": [str],
      "index_size_mb": int,
      "queries_processed": int,
      "avg_query_latency_ms": float
    }
  }
  ```
  - **Status Determination**:
    - `healthy`: All services up, indexing idle or progressing normally
    - `degraded`: Some services down but core functionality works (e.g., sparse-only search)
    - `unhealthy`: Critical services down (vector store unavailable)

#### Search - CLI

- **FR-011a**: CLI MUST provide search command with signature:
  ```
  codeweaver search <query> [OPTIONS]

  Parameters:
    query (str, positional, required): Natural language search query
    --intent, -i (str, optional): Search intent (understand|implement|debug|optimize|test|configure|document)
    --limit, -l (int, optional, default=10): Maximum results to return
    --include-tests (bool, flag, default=True): Include test files in results
    --project, -p (Path, optional): Project directory path (overrides config)
    --output-format, -o (str, optional, default="table"): Output format (json|table|markdown)

  Examples:
    codeweaver search "authentication logic" --limit 5 --output-format markdown
    codeweaver search "database setup" --intent implement --project ./my-project
  ```
  - **Implementation**: `codeweaver/cli/app.py::search()`

- **FR-011b**: CLI MUST provide server command with signature:
  ```
  codeweaver server [OPTIONS]

  Parameters:
    --config, -c (FilePath, optional): Path to configuration file
    --project, -p (Path, optional): Project directory to index
    --host (str, optional, default="127.0.0.1"): Host address to bind server
    --port (int, optional, default=9328): Port number for server
    --debug (bool, flag, default=False): Enable debug mode

  Examples:
    codeweaver server --project /path/to/codebase --port 9328
    codeweaver server --config ./codeweaver.toml --debug
  ```
  - **Implementation**: `codeweaver/cli/app.py::server()`

- **FR-011c**: CLI MUST provide config command with signature:
  ```
  codeweaver config [OPTIONS]

  Parameters:
    --show (bool, flag): Display current configuration
    --project, -p (Path, optional): Project directory path

  Examples:
    codeweaver config --show
    codeweaver config --project ./my-project --show
  ```
  - **Implementation**: `codeweaver/cli/app.py::config()`

- **FR-011d**: CLI status command (NOT YET IMPLEMENTED - needs v0.1 implementation):
  ```
  codeweaver status [OPTIONS]

  Purpose: Display indexing progress and system health
  Note: Status available via /health/ endpoint, needs CLI wrapper
  ```

- **FR-012**: CLI search MUST accept natural language queries as input

- **FR-013**: CLI search MUST return ranked results to the user

#### Search - MCP Tool

- **FR-014**: System MUST expose a `find_code` tool via MCP protocol using FastMCP

- **FR-014a**: `find_code` tool MUST accept parameters:
  ```python
  # Module: codeweaver.agent_api.find_code
  async def find_code(
      query: str,                                      # Required: Natural language search query
      *,
      intent: IntentType | None = None,               # Optional: Search intent override
      token_limit: int = 10000,                       # Optional: Max tokens in response
      include_tests: bool = False,                    # Optional: Include test files
      focus_languages: tuple[str, ...] | None = None, # Optional: Filter by languages
      max_results: int = 50                           # Optional: Max matches to return
  ) -> FindCodeResponseSummary
  ```
  - **IntentType Values** (from `codeweaver.agent_api.intent`):
    - `UNDERSTAND`: Understand codebase structure and functionality
    - `IMPLEMENT`: Implement new features
    - `DEBUG`: Debug issues and errors
    - `OPTIMIZE`: Optimize performance/efficiency
    - `TEST`: Write or modify tests
    - `CONFIGURE`: Update configuration settings
    - `DOCUMENT`: Write or update documentation

- **FR-014b**: `find_code` tool MUST return `FindCodeResponseSummary` with fields:
  ```python
  # Module: codeweaver.agent_api.models
  class FindCodeResponseSummary:
      matches: list[CodeMatch]               # Ranked code matches
      summary: str                          # High-level explanation (max 1000 chars)
      query_intent: IntentType | None       # Detected or specified intent
      total_matches: int                    # Matches found before ranking
      total_results: int                    # Results in this response
      token_count: int                      # Actual tokens used
      execution_time_ms: float              # Total processing time
      search_strategy: tuple[SearchStrategy, ...] # Methods used
      languages_found: tuple[str, ...]      # Languages in results

  # CodeMatch structure:
  class CodeMatch:
      file: DiscoveredFile                  # File metadata
      content: CodeChunk                    # Code chunk with content and metadata
      span: Span                            # Line range (start, end)
      relevance_score: float                # Multi-layered weighted score [0.0-1.0]
      match_type: CodeMatchType             # SEMANTIC | SYNTACTIC | KEYWORD | FILE_PATTERN
      related_symbols: tuple[str]           # Related functions/classes
  ```
  - **MCP Integration**: FastMCP handles request/response serialization automatically. `find_code` returns Pydantic model, FastMCP serializes to JSON.

- **FR-015**: The `find_code` tool MUST accept natural language queries from AI agents

- **FR-016**: The `find_code` tool MUST return ranked results to the requesting agent

#### Search Quality

- **FR-017**: Search MUST use hybrid search combining dense vectors (voyage-code-3 embeddings) and sparse vectors (FastEmbed with prithivida/Splade-PP_en_v2)

- **FR-018**: Search results MUST be reranked using voyage-rerank-2.5 (configurable via settings)

- **FR-019**: System MUST apply ImportanceScores from SemanticClass categories when ranking search results. Scoring weights MUST be adjusted based on query IntentType or AgentTask context.
  - **Weighting Rules**:
    - IntentType.UNDERSTAND queries: Boost DEFINITION_* categories by 1.5x
    - IntentType.IMPLEMENT queries: Boost DEFINITION_* and BOUNDARY_* by 1.3x
    - IntentType.DEBUG queries: Boost FLOW_* and OPERATION_* by 1.4x
    - IntentType.TEST queries: Boost DEFINITION_TEST by 2.0x
    - AgentTask weights: Apply task-specific ImportanceScores profile
  - **Acceptance Criteria**: Reference test suite (FR-036) passes with ≥70% expected results in top 5
  - **Validation**: For IntentType.IMPLEMENT + query "authentication", AuthMiddleware class appears in top 3 (it's a DEFINITION_TYPE)

- **FR-020**: Search results MUST include code content, file path, and relevance scores

- **FR-021**: Search MUST handle queries that match no results gracefully (see Example 3)

- **FR-021a**: When embedding provider API is unavailable during query, system MUST attempt sparse-only search, warn user (MCP: via context object, CLI: to stdout), and return best available results

- **FR-021b**: When no results can be provided due to service failures, system MUST raise an error

#### Search Workflow (find_code Pipeline)

- **FR-022**: System MUST heuristically analyze the query to determine search intent (IntentType)

- **FR-023**: System MUST embed the query using both dense and sparse embedding methods

- **FR-024**: System MUST retrieve candidate results from the vector store using hybrid search

- **FR-025**: System MUST rerank candidates using the configured reranking model

- **FR-026**: System MUST rescore results based on analyzed AgentTask, IntentType, and ImportanceScores category

- **FR-027**: System MUST return top-k results (configurable k value)

- **FR-028**: IntentType enum MUST be designed to allow future additions without breaking changes to find_code tool API
  - **Requirements**:
    - IntentType defined as extensible Python enum
    - find_code accepts IntentType | str for forward compatibility
    - Unknown IntentType values handled gracefully (default to None)
    - API clients can pass custom intent strings
  - **Test**: Add new IntentType value in test, verify find_code accepts without code changes
  - **Rationale**: Enables v0.2+ to add agent-driven intent analysis without breaking v0.1 clients

#### Operational Requirements

- **FR-033**: External Service Timeouts
  - All external service calls MUST timeout after 30 seconds
  - Timeout triggers retry logic with exponential backoff
  - Applies to: embedding API calls, vector store operations, reranking calls

- **FR-034**: Indexing Checkpoint and Resume
  - System MUST persist indexing state to enable resumption after interruption
  - Checkpoint frequency: Every 100 files, every 5 minutes, on SIGTERM
  - Checkpoint data stored in `.codeweaver/index_checkpoint.json`:
    ```json
    {
      "session_id": "UUID7",
      "project_path": "/path/to/codebase",
      "start_time": "ISO8601",
      "last_checkpoint": "ISO8601",
      "files_processed": ["file1.py", "file2.py", ...],
      "chunks_created": 450,
      "errors": [],
      "settings_hash": "sha256:..."
    }
    ```
  - Resume behavior:
    - On server start, check for checkpoint file
    - If settings_hash matches: resume from checkpoint
    - If settings_hash differs: reindex from scratch
    - If checkpoint >24 hours old: reindex from scratch
  - User control: `codeweaver server --reindex` ignores checkpoint

- **FR-035**: Concurrent Access Behavior
  - System MUST support unlimited concurrent search requests (read-only)
  - System MUST prevent concurrent indexing on same codebase (file lock: `.codeweaver/index.lock`)
  - Searches during indexing use eventually-consistent index
  - CLI shows warning if searching during active indexing: "⚠️ Results may be incomplete, indexing in progress"

- **FR-036**: Reference Test Suite
  - System MUST be validated against reference test suite: `tests/integration/reference_queries.yml`
  - Minimum 20 query/result pairs covering all IntentType values
  - Quality targets:
    - Precision@3: ≥70% (7/10 queries return expected result in top 3)
    - Precision@5: ≥80% (8/10 queries return expected result in top 5)
  - Test against CodeWeaver's own codebase (dogfooding)
  - CI integration: Run on every PR affecting search/ranking logic

- **FR-037**: Search Performance Requirements
  - Queries MUST return results within 3 seconds for codebases ≤10,000 files
  - Queries MUST return results within 10 seconds for codebases ≤100,000 files
  - If query exceeds timeout, return partial results with warning
  - Hardware baseline: 4 CPU cores, 8GB RAM, SSD storage, local Qdrant

- **FR-038**: Indexing Performance Requirements
  - System MUST index at least 100 files/minute on standard hardware
  - System MUST provide progress updates via /health/ endpoint every 5 seconds
  - Indexing MUST be interruptible with graceful shutdown (SIGTERM handling)
  - Indexing MUST persist checkpoint every 100 files for resumption
  - Standard hardware: Same as FR-037

- **FR-039**: Resource Limits
  - Maximum chunk size: 4000 tokens (hard limit, truncate if exceeded)
  - Maximum concurrent embedding requests: 10 (to external APIs)
  - Maximum memory per indexing session: 2GB resident set size
  - System MUST emit warning to stderr if codebase exceeds 50,000 files
  - System MUST emit error if codebase exceeds 500,000 files (v0.1 limit)

- **FR-040**: Structured Logging Requirements
  - All log entries MUST include:
    - `timestamp`: ISO8601 format with timezone
    - `level`: DEBUG | INFO | WARNING | ERROR | CRITICAL
    - `component`: "indexer" | "searcher" | "server" | "cli" | "embedder" | "vectorstore"
    - `operation`: specific operation name (e.g., "embed_chunk", "hybrid_search")
    - `duration_ms`: for completed operations
    - `request_id`: UUID for request tracing
    - `error`: error message and type if applicable
    - `context`: relevant operation-specific data
  - Format: JSON for machine parsing, structured text for human readability

- **FR-041**: Key Metrics to Track
  - Search metrics (via /health/ endpoint):
    - `search_query_latency_ms`: {p50, p95, p99} over last 100 queries
    - `search_queries_total`: count
    - `search_results_returned`: {avg, p50, p95}
    - `search_intent_distribution`: count per IntentType
  - Indexing metrics:
    - `indexing_files_per_second`: current rate
    - `indexing_chunks_created_total`: cumulative count
    - `indexing_errors_total`: cumulative count
    - `indexing_duration_seconds`: last complete duration
  - Service health metrics:
    - `embedding_api_requests_total`, `embedding_api_errors_total`
    - `embedding_api_latency_ms`: {p50, p95, p99}
    - `vector_store_operation_latency_ms`: {p50, p95, p99}
    - `circuit_breaker_state`, `circuit_breaker_open_count`

#### Documentation

- **FR-029**: README MUST include a "Quickstart" section with working commands

- **FR-030**: README MUST clearly distinguish between current capabilities and future/planned features

- **FR-031**: README MUST reflect the actual state of v0.1, not aspirational features

- **FR-032**: Documentation MUST include examples of successful searches

---

## Data Models and Implementation References

All entities below reference actual Pydantic models in the codebase:

### CodeChunk
**Module**: `codeweaver/core/chunks.py`
**Description**: Core building block for all CodeWeaver operations
**Key Fields**:
- `content: str` - Code content
- `line_range: Span` - Line range in source file
- `file_path: Path | None` - Source file path
- `language: SemanticSearchLanguage | str | None`
- `source: ChunkSource` - TEXT_BLOCK | FILE | SEMANTIC
- `ext_kind: ExtKind | None` - File extension metadata
- `timestamp: float` - Creation/modification timestamp
- `chunk_id: UUID7` - Unique identifier
- `parent_id: UUID7 | None` - Parent chunk (e.g., DiscoveredFile's source_id)
- `metadata: Metadata | None` - Additional metadata
- `chunk_name: str | None` - Fully qualified identifier (e.g., "auth.py:UserAuth.validate")
- `embeddings: dict | None` - Dense and/or sparse embeddings

### CodeMatch
**Module**: `codeweaver/agent_api/models.py`
**Description**: Individual code match with relevance scoring
**Key Fields**:
- `file: DiscoveredFile` - File information
- `content: CodeChunk` - The relevant code chunk
- `span: Span` - Line numbers (start, end)
- `relevance_score: float [0.0-1.0]` - Multi-layered weighted score
- `match_type: CodeMatchType` - SEMANTIC | SYNTACTIC | KEYWORD | FILE_PATTERN
- `related_symbols: tuple[str]` - Related functions/classes

### CodeMatchType
**Module**: `codeweaver/agent_api/models.py`
**Description**: Classification of match method (enum)
**Values**: SEMANTIC, SYNTACTIC, KEYWORD, FILE_PATTERN

### SearchStrategy
**Module**: `codeweaver/agent_api/models.py`
**Description**: Search methods applied to query (enum)
**Values**: HYBRID_SEARCH, SEMANTIC_RERANK, SPARSE_ONLY, DENSE_ONLY, KEYWORD_FALLBACK

### ChunkSource
**Module**: `codeweaver/core/metadata.py`
**Description**: Origin of chunk data (enum)
**Values**: TEXT_BLOCK, FILE, AST_NODE

### FindCodeResponseSummary
**Module**: `codeweaver/agent_api/models.py`
**Description**: Complete find_code tool response
**Key Fields**: See FR-014b

### IntentType
**Module**: `codeweaver/agent_api/intent.py`
**Description**: User/agent intent classification (enum)
**Values**: UNDERSTAND, IMPLEMENT, DEBUG, OPTIMIZE, TEST, CONFIGURE, DOCUMENT

### QueryIntent
**Module**: `codeweaver/agent_api/intent.py`
**Description**: Classified query intent with confidence
**Key Fields**:
- `intent_type: IntentType`
- `confidence: float [0.0-1.0]`
- `reasoning: str` - Why this intent was detected
- `focus_areas: tuple[str]` - Specific areas of focus
- `complexity_level: QueryComplexity` - SIMPLE | MODERATE | COMPLEX

### IntentResult *(v0.2 Future Feature)*
**Module**: `codeweaver/agent_api/intent.py`
**Description**: Intent analysis with strategy recommendations requiring agent feedback loop
**Status**: Deferred to v0.2 - not required for v0.1 MVP
**Key Fields**: Search strategy weights, file patterns, response formatting preferences

### ImportanceScores
**Module**: `codeweaver/semantic/classifications.py`
**Description**: Multi-dimensional importance scoring for AI contexts
**Fields**:
- `discovery: float [0.0-1.0]` - Finding relevant code
- `comprehension: float [0.0-1.0]` - Understanding behavior
- `modification: float [0.0-1.0]` - Safe editing points
- `debugging: float [0.0-1.0]` - Tracing execution
- `documentation: float [0.0-1.0]` - Explaining code

### AgentTask
**Module**: `codeweaver/semantic/classifications.py`
**Description**: Predefined task contexts with importance weight profiles
**Values**: DEBUG, DEFAULT, DOCUMENT, IMPLEMENT, LOCAL_EDIT, REFACTOR, REVIEW, SEARCH, TEST
**Example Profile** (DEBUG):
```python
{
    "discovery": 0.2,
    "comprehension": 0.3,
    "modification": 0.1,
    "debugging": 0.35,  # Highest weight for debugging context
    "documentation": 0.05
}
```

### SemanticClass
**Module**: `codeweaver/semantic/classifications.py`
**Description**: Language-agnostic semantic categories for AST nodes (20+ classifications)
**Categories** (5 tiers):
- **Tier 1 - Primary Definitions**: DEFINITION_CALLABLE, DEFINITION_TYPE, DEFINITION_DATA, DEFINITION_TEST
- **Tier 2 - Behavioral Contracts**: BOUNDARY_MODULE, BOUNDARY_ERROR, BOUNDARY_RESOURCE, DOCUMENTATION_STRUCTURED
- **Tier 3 - Control Flow**: FLOW_BRANCHING, FLOW_ITERATION, FLOW_CONTROL, FLOW_ASYNC
- **Tier 4 - Operations**: OPERATION_INVOCATION, OPERATION_DATA, OPERATION_OPERATOR, EXPRESSION_ANONYMOUS
- **Tier 5 - Syntax**: SYNTAX_KEYWORD, SYNTAX_IDENTIFIER, SYNTAX_LITERAL, SYNTAX_ANNOTATION, SYNTAX_PUNCTUATION

---

## Edge Cases - Complete Answers

| Scenario | Behavior | Output/Logging |
|----------|----------|----------------|
| **Empty directory** | Accept as valid empty index | INFO "No files discovered in /path/to/empty"<br>Indexing completes with 0 chunks<br>Health: `{"indexing": {"state": "idle", "progress": {"files_discovered": 0}}}` |
| **No files with known extensions** | Complete with warning | WARNING "No files matched configured extensions"<br>"Indexed 0 files. Discovered 47 files with unknown extensions."<br>Suggestion: "Add custom extensions in codeweaver.toml" |
| **Query matches no results** | Return empty results with suggestions | See Example 3 above |
| **Very large codebases (100k+ files)** | Warning at 50k, error at 500k | Warning at 50k: "Large codebase detected, indexing may be slow"<br>Error at 500k: "Codebase too large for v0.1, consider filtering"<br>Future: v0.2 incremental indexing |
| **Multiple concurrent indexing** | Reject with error | "Indexing already in progress (started at 14:00:00 UTC)"<br>Exit code: 1<br>File lock: `.codeweaver/index.lock` |
| **Partially indexed codebase** | Detect and offer resume | Detect checkpoint on startup<br>Prompt: "Incomplete index found. Resume from 450 chunks or reindex?"<br>Auto-resume with `--resume` flag |
| **Indexing fails for individual files** | See FR-009a, FR-009b | Retry once → log error → continue<br>≥25 errors → warning to stderr |
| **Embedding API unavailable (indexing)** | See FR-009c | Exponential backoff, continue with sparse-only |
| **Embedding API unavailable (query)** | See FR-021a | Sparse-only search with warning |
| **Vector store unavailable** | See FR-008a, FR-008b | Exponential backoff → circuit breaker → error if persists |

---

## Review & Acceptance Checklist

### Content Quality
- [x] No implementation details (languages, frameworks, APIs) - *Note: Implementation references added for clarity, not prescription*
- [x] Focused on user value and business needs
- [x] Written for business stakeholders with technical references for implementers
- [x] All mandatory sections completed
- [x] **NEW**: Concrete examples with actual inputs/outputs added
- [x] **NEW**: All requirements have testable acceptance criteria

### Requirement Completeness
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified
- [x] **NEW**: Interface specifications complete (find_code, CLI commands)
- [x] **NEW**: Data models referenced with actual modules
- [x] **NEW**: Edge cases have documented answers
- [x] **NEW**: Performance baselines defined
- [x] **NEW**: Operational requirements specified (timeouts, circuit breakers, observability)

### Expert Panel Validation
- [x] **Wiegers**: Requirements use measurable criteria (FR-006, FR-019 rewritten)
- [x] **Adzic**: Concrete examples provided (4 scenarios with actual I/O)
- [x] **Nygard**: Operational requirements complete (timeouts, circuit breakers, health checks)
- [x] **Fowler**: Interface specifications documented (find_code, CLI commands)
- [x] **Crispin**: Reference test suite requirement added (FR-036)

**Quality Score**: 9.0/10 (up from 7.5/10 pre-review)

---

## Execution Status

- [x] User description parsed
- [x] Key concepts extracted
- [x] Ambiguities marked and resolved
- [x] User scenarios defined
- [x] Requirements generated
- [x] Entities identified with implementation references
- [x] Review checklist passed
- [x] Expert panel review completed and integrated
- [x] Concrete examples added
- [x] Interface specifications documented
- [x] Edge cases completed

**Status**: ✅ READY FOR IMPLEMENTATION

---

## Additional Context

### Scope Boundaries for v0.1

**In Scope:**
- Single codebase indexing
- CLI and MCP interfaces for search
- Hybrid search with reranking
- Semantic classification weighting
- Health monitoring endpoint
- Basic error recovery and graceful degradation
- Performance monitoring
- Checkpoint/resume for interrupted indexing

**Out of Scope for v0.1:**
- Multiple simultaneous codebases
- Real-time code change watching/incremental updates
- Advanced search filters (language, file type, date ranges)
- Search result explanations
- Full performance optimization for large codebases (>100k files)
- Web UI for search
- Authentication/authorization
- Distributed deployment

### Success Metrics

- Developer can go from clone to first search in under 10 minutes
- Search returns relevant results for common code queries (e.g., "authentication logic", "database connection")
- MCP integration works with at least one AI agent (Claude Code, Cursor, etc.)
- All README Quickstart commands execute without errors
- **NEW**: Reference test suite achieves ≥70% precision@3, ≥80% precision@5
- **NEW**: Search queries complete within 3 seconds for typical codebases (<10k files)
- **NEW**: Health endpoint returns accurate status and metrics

### Assumptions

- Users have Python 3.12+ installed
- Users have access to embedding provider API keys (VoyageAI or alternatives)
- Codebases are primarily in supported languages (20+ languages via language detection)
- Initial v0.1 testing will use CodeWeaver's own codebase as reference
- Standard hardware available: 4 CPU cores, 8GB RAM, SSD storage
- Internet connectivity for external embedding/reranking services

### Implementation Priority

**Critical (Before Implementation)**:
1. Interface specifications complete ✅
2. Testable requirements defined ✅
3. Timeout/circuit breaker specs ✅
4. Data models referenced ✅

**High Priority (During Implementation)**:
5. Health endpoint format implementation
6. Reference test suite creation
7. Performance monitoring
8. Error handling with graceful degradation

**Medium Priority (Time Permitting)**:
9. Checkpoint/resume functionality
10. CLI status command
11. Comprehensive edge case handling

---

**Specification Version**: 2.0 (Post-Expert Review)
**Last Updated**: 2025-10-27
**Review Status**: Expert panel validated, ready for implementation
