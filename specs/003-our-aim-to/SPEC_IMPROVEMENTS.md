<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Specification Improvements for CodeWeaver v0.1

**Expert Panel Review Date**: 2025-10-27
**Original Spec**: `specs/003-our-aim-to/spec.md`
**Status**: Recommended improvements with actual implementation references

---

## Overview

This document provides the expert panel's recommended improvements to the v0.1 specification, grounded in the actual codebase implementation. All recommendations reference existing code modules and data models.

**Expert Panel**: Karl Wiegers (Requirements), Gojko Adzic (Specification by Example), Michael Nygard (Operations), Martin Fowler (Architecture), Lisa Crispin (Testing)

**Overall Quality Score**: 7.5/10 → Target: 9/10 with improvements

---

## Critical Improvements (Must Fix)

### 1. Add Complete Interface Specifications

**Issue**: The spec references `find_code` tool and CLI commands without documenting their actual interfaces.

**Solution**: Document the actual implementations from the codebase.

#### find_code Tool Interface (MCP)

**Location**: `codeweaver/agent_api/find_code.py`
**Response Model**: `FindCodeResponseSummary` from `codeweaver/agent_api/models.py`

```yaml
FR-014a: find_code Tool Parameters
  Module: codeweaver.agent_api.find_code
  Function: async def find_code(query: str, *, intent, token_limit, include_tests, focus_languages, max_results)

  Parameters:
    - query: str (required)
      Description: Natural language search query
      Example: "authentication logic", "database connection setup"

    - intent: IntentType | None (optional, default=None)
      Description: User/agent intent for the search (from codeweaver.agent_api.intent)
      Type: IntentType enum
      Values: UNDERSTAND, IMPLEMENT, DEBUG, OPTIMIZE, TEST, CONFIGURE, DOCUMENT
      Example: IntentType.IMPLEMENT

    - token_limit: int (optional, default=10000)
      Description: Maximum tokens to return in results
      Range: positive integer

    - include_tests: bool (optional, default=False)
      Description: Whether to include test files in results

    - focus_languages: tuple[str, ...] | None (optional, default=None)
      Description: Filter results to specific programming languages
      Example: ("python", "typescript")

    - max_results: int (optional, default=50)
      Description: Maximum number of matches to return
      Range: positive integer

FR-014b: find_code Tool Response Format
  Module: codeweaver.agent_api.models
  Type: FindCodeResponseSummary (Pydantic model)

  Response Fields:
    matches: list[CodeMatch]
      - file: DiscoveredFile - File metadata
      - content: CodeChunk - Code chunk object with content and metadata
      - span: Span - Line range (start_line, end_line)
      - relevance_score: float [0.0-1.0] - Multi-layered weighted score
      - match_type: CodeMatchType enum - SEMANTIC | SYNTACTIC | KEYWORD | FILE_PATTERN
      - related_symbols: tuple[str] - Related functions/classes

    summary: str (max 1000 chars)
      - High-level explanation of findings

    query_intent: IntentType | None
      - Detected or specified intent

    total_matches: int
      - Total matches found before ranking

    total_results: int
      - Number of results in this response

    token_count: int
      - Actual tokens used in response

    execution_time_ms: float
      - Total processing time in milliseconds

    search_strategy: tuple[SearchStrategy, ...]
      - Methods used: FILE_DISCOVERY, TEXT_SEARCH, SEMANTIC, etc.

    languages_found: tuple[SemanticSearchLanguage | str, ...]
      - Programming languages in results

  MCP Integration:
    - FastMCP handles request/response serialization automatically
    - find_code returns Pydantic model → FastMCP serializes to JSON
    - No manual MCP protocol handling needed
```

#### CLI Commands

**Location**: `codeweaver/cli/app.py`
**Framework**: Cyclopts

```yaml
FR-011a: CLI Search Command
  Signature: codeweaver search <query> [OPTIONS]
  Implementation: codeweaver/cli/app.py::search()

  Parameters:
    query (str, positional, required):
      Description: Natural language search query

    --intent, -i (IntentType, optional):
      Description: Search intent override
      Values: understand | implement | debug | optimize | test | configure | document

    --limit, -l (int, optional, default=10):
      Description: Maximum number of results to return

    --include-tests (bool, flag, default=True):
      Description: Include test files in results

    --project, -p (Path, optional):
      Description: Project directory path (overrides config)

    --output-format, -o (str, optional, default="table"):
      Values: json | table | markdown
      Description: Output format for results

  Example:
    codeweaver search "authentication logic" --limit 5 --output-format markdown
    codeweaver search "database setup" --intent implement --project ./my-project

FR-011b: CLI Server Command
  Signature: codeweaver server [OPTIONS]
  Implementation: codeweaver/cli/app.py::server()

  Parameters:
    --config, -c (FilePath, optional):
      Description: Path to configuration file

    --project, -p (Path, optional):
      Description: Project directory to index

    --host (str, optional, default="127.0.0.1"):
      Description: Host address to bind server

    --port (int, optional, default=9328):
      Description: Port number for server

    --debug (bool, flag, default=False):
      Description: Enable debug mode

  Example:
    codeweaver server --project /path/to/codebase --port 9328
    codeweaver server --config ./codeweaver.toml --debug

FR-011c: CLI Config Command
  Signature: codeweaver config [OPTIONS]
  Implementation: codeweaver/cli/app.py::config()

  Parameters:
    --show (bool, flag):
      Description: Display current configuration

    --project, -p (Path, optional):
      Description: Project directory path

  Example:
    codeweaver config --show
    codeweaver config --project ./my-project --show

FR-011d: CLI Status Command (NOT YET IMPLEMENTED)
  Recommended Signature: codeweaver status [OPTIONS]
  Purpose: Display indexing progress and system health

  Status: NEEDS IMPLEMENTATION for v0.1
  References: FR-010 (health endpoint exists at /health/)
```

### 2. Document Actual Data Models

**Issue**: Spec mentions entities but doesn't reference actual implementations.

**Solution**: Reference the implemented Pydantic models.

```yaml
Key Entities - Actual Implementation References:

CodeChunk (codeweaver/core/chunks.py):
  Description: Core building block for all CodeWeaver operations
  Fields:
    - content: str - Code content
    - line_range: Span - Line range in source file
    - file_path: Path | None - Source file path
    - language: SemanticSearchLanguage | str | None
    - source: ChunkSource enum - TEXT_BLOCK | FILE | AST_NODE | etc.
    - ext_kind: ExtKind | None - File extension metadata
    - timestamp: float - Creation/modification timestamp
    - chunk_id: UUID7 - Unique identifier
    - parent_id: UUID7 | None - Parent chunk (e.g., file ID)
    - metadata: Metadata | None - Additional metadata
    - chunk_name: str | None - Fully qualified identifier
    - embeddings: dict | None - Dense and/or sparse embeddings

CodeMatch (codeweaver/agent_api/models.py):
  Description: Individual code match with relevance scoring
  Fields:
    - file: DiscoveredFile - File information
    - content: CodeChunk - The relevant code chunk
    - span: Span - Line numbers (start, end)
    - relevance_score: float [0.0-1.0] - Multi-layered weighted score
    - match_type: CodeMatchType - SEMANTIC | SYNTACTIC | KEYWORD | FILE_PATTERN
    - related_symbols: tuple[str] - Related functions/classes

FindCodeResponseSummary (codeweaver/agent_api/models.py):
  Description: Complete find_code tool response
  Fields: [see FR-014b above]

IntentType (codeweaver/agent_api/intent.py):
  Description: User/agent intent classification
  Values:
    - UNDERSTAND: Understand codebase structure and functionality
    - IMPLEMENT: Implement new features
    - DEBUG: Debug issues and errors
    - OPTIMIZE: Optimize performance/efficiency
    - TEST: Write or modify tests
    - CONFIGURE: Update configuration settings
    - DOCUMENT: Write or update documentation

QueryIntent (codeweaver/agent_api/intent.py):
  Description: Classified query intent with confidence
  Fields:
    - intent_type: IntentType
    - confidence: float [0.0-1.0]
    - reasoning: str - Why this intent was detected
    - focus_areas: tuple[str] - Specific areas of focus
    - complexity_level: QueryComplexity - SIMPLE | MODERATE | COMPLEX

IntentResult (codeweaver/agent_api/intent.py):
  Description: Intent analysis with strategy recommendations
  Status: Intended for v0.2+ agent integration
  Fields:
    - intent: QueryIntent
    - file_patterns: list[str] - Patterns to prioritize
    - exclude_patterns: tuple[str] - Patterns to exclude
    - semantic_weight: float [0.0-1.0]
    - syntactic_weight: float [0.0-1.0]
    - keyword_weight: float [0.0-1.0]
    - include_context: bool
    - max_matches_per_file: int
    - prioritize_entry_points: bool

ImportanceScores (codeweaver/semantic/classifications.py):
  Description: Multi-dimensional importance scoring for AI contexts
  Fields:
    - discovery: float [0.0-1.0] - Finding relevant code
    - comprehension: float [0.0-1.0] - Understanding behavior
    - modification: float [0.0-1.0] - Safe editing points
    - debugging: float [0.0-1.0] - Tracing execution
    - documentation: float [0.0-1.0] - Explaining code

AgentTask (codeweaver/semantic/classifications.py):
  Description: Predefined task contexts with importance weight profiles
  Values:
    - DEBUG: Debugging code (debugging: 0.35, comprehension: 0.3)
    - DEFAULT: Balanced weights (all: 0.05)
    - DOCUMENT: Documenting code (documentation: 0.45)
    - IMPLEMENT: Implementing code (discovery: 0.3, comprehension: 0.3)
    - LOCAL_EDIT: Local code edits (discovery: 0.4, comprehension: 0.3)
    - REFACTOR: Refactoring code (modification: 0.45, comprehension: 0.25)
    - REVIEW: Code review (comprehension: 0.35, discovery: 0.25)
    - SEARCH: Searching code (discovery: 0.5)
    - TEST: Testing/writing tests (discovery: 0.5, debugging: 0.4)

SemanticClass (codeweaver/semantic/classifications.py):
  Description: Language-agnostic semantic categories for AST nodes
  Categories (5 tiers, 20+ classifications):
    Tier 1 - Primary Definitions:
      - DEFINITION_CALLABLE: Functions, methods
      - DEFINITION_TYPE: Classes, interfaces, structs
      - DEFINITION_DATA: Enums, constants
      - DEFINITION_TEST: Test functions
    Tier 2 - Behavioral Contracts:
      - BOUNDARY_MODULE: Imports, exports
      - BOUNDARY_ERROR: Exception definitions
      - BOUNDARY_RESOURCE: Resource management
      - DOCUMENTATION_STRUCTURED: Docstrings, API docs
    Tier 3 - Control Flow:
      - FLOW_BRANCHING: if/switch
      - FLOW_ITERATION: for/while loops
      - FLOW_CONTROL: return/break/continue
      - FLOW_ASYNC: async/await
    Tier 4 - Operations:
      - OPERATION_INVOCATION: Function calls
      - OPERATION_DATA: Variable assignments
      - OPERATION_OPERATOR: Mathematical/logical ops
      - EXPRESSION_ANONYMOUS: Lambdas, closures
    Tier 5 - Syntax:
      - SYNTAX_KEYWORD: Language keywords
      - SYNTAX_IDENTIFIER: Variable names
      - SYNTAX_LITERAL: String/number literals
      - SYNTAX_ANNOTATION: Decorators, attributes
      - SYNTAX_PUNCTUATION: Braces, parentheses
```

### 3. Make Requirements Testable

**Issue**: Several requirements use subjective terms without measurable criteria.

**Solution**: Rewrite with concrete acceptance criteria.

```yaml
FR-006 (CURRENT - TOO VAGUE):
  "System MUST chunk code files into semantically meaningful segments"

FR-006 (IMPROVED - TESTABLE):
  System MUST chunk code using AST-based boundaries when available (functions,
  classes, methods) with target size 200-800 tokens, preserving complete logical
  units. For languages without AST support, use text-based chunking with
  similar size targets.

  Acceptance Criteria:
    - ≥95% of chunks for AST-supported languages are complete syntactic units
    - Chunks MUST NOT split function/class definitions across boundaries
    - Average chunk size: 400-600 tokens
    - Chunk size range: 200-800 tokens (95th percentile)

  Validation:
    - Parse random sample of 100 chunks per language
    - Verify syntactic completeness (re-parse without errors)
    - Measure token distribution

FR-019 (CURRENT - TOO VAGUE):
  "Search results MUST be weighted by semantic classification scores"

FR-019 (IMPROVED - TESTABLE):
  System MUST apply ImportanceScores from SemanticClass categories when
  ranking search results. Scoring weights MUST be adjusted based on query
  IntentType or AgentTask context.

  Weighting Rules:
    - IntentType.UNDERSTAND queries: Boost DEFINITION_* categories by 1.5x
    - IntentType.IMPLEMENT queries: Boost DEFINITION_* and BOUNDARY_* by 1.3x
    - IntentType.DEBUG queries: Boost FLOW_* and OPERATION_* by 1.4x
    - IntentType.TEST queries: Boost DEFINITION_TEST by 2.0x
    - AgentTask weights: Apply task-specific ImportanceScores profile

  Acceptance Criteria:
    - Reference test suite (FR-036) passes with ≥70% expected results in top 5
    - For IntentType.IMPLEMENT + query "authentication", AuthMiddleware
      class appears in top 3 (it's a DEFINITION_TYPE)
    - Semantic weights visible in CodeMatch.relevance_score calculation

  Validation:
    - Run reference test suite
    - Log relevance score calculations for manual inspection
    - Measure precision@5 for each IntentType category
```

---

## High Priority Improvements (Strongly Recommended)

### 4. Add Concrete Scenario Examples

**Expert**: Gojko Adzic
**Impact**: Dramatically improves implementation clarity

```markdown
### Scenario Examples (Specification by Example)

#### Example 1: Successful Search with Semantic Ranking

**Given**: CodeWeaver indexed with Python codebase containing:
  - `src/auth/middleware.py`: AuthMiddleware class (lines 15-85, DEFINITION_TYPE)
  - `src/auth/utils.py`: authenticate_user function (lines 10-35, DEFINITION_CALLABLE)
  - `src/auth/tokens.py`: JWT validation logic (lines 5-25, OPERATION_DATA)
  - `tests/test_auth.py`: authentication test fixtures (lines 1-50, DEFINITION_TEST)

**When**: User searches with:
```
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

**Explanation**:
- AuthMiddleware scores highest (0.92) because:
  - DEFINITION_TYPE has high discovery score (0.95)
  - IntentType.UNDERSTAND applies 1.5x boost to definitions
  - Semantic match on "authenticate" + "middleware"
- Test fixtures ranked lower despite keyword matches:
  - DEFINITION_TEST has lower weight for UNDERSTAND intent
  - User wants to understand implementation, not tests

#### Example 2: MCP Tool Integration

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

#### Example 3: Edge Case - No Results with Helpful Message

**Given**: Indexed Python codebase (no COBOL code)

**When**: User searches:
```
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

#### Example 4: Error Handling - Embedding Service Unavailable

**Given**: CodeWeaver server running, VoyageAI API down

**When**: User searches:
```
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

**MCP Behavior**:
- Response includes degraded service indicator in metadata
- Warning communicated via MCP context object
- Agent can decide whether to retry or use results
```

---

### 5. Add Performance Requirements

**Experts**: Lisa Crispin, Michael Nygard
**Impact**: Enables performance validation

```yaml
FR-037: Search Performance Requirements
  - Search queries MUST return results within 3 seconds for codebases ≤10,000 files
  - Search queries MUST return results within 10 seconds for codebases ≤100,000 files
  - If query processing exceeds timeout, system MUST return partial results
    with warning rather than error

  Measurement:
    - execution_time_ms field in FindCodeResponseSummary
    - P95 latency across 100 test queries

  Hardware Baseline:
    - 4 CPU cores, 8GB RAM, SSD storage
    - Local Qdrant (in-memory mode)

FR-038: Indexing Performance Requirements
  - System MUST index at least 100 files/minute on standard hardware
  - System MUST provide progress updates via /health/ endpoint every 5 seconds
  - Indexing MUST be interruptible with graceful shutdown (SIGTERM handling)
  - Indexing MUST persist checkpoint every 100 files for resumption

  Standard Hardware: Same as FR-037

  Progress Indicators:
    - files_discovered: int
    - files_processed: int
    - chunks_created: int
    - errors: int
    - estimated_time_remaining_seconds: int (calculated)

FR-039: Resource Limits
  - Maximum chunk size: 4000 tokens (hard limit, truncate if exceeded)
  - Maximum concurrent embedding requests: 10 (to external APIs)
  - Maximum memory per indexing session: 2GB resident set size
  - System MUST emit warning to stderr if codebase exceeds 50,000 files
  - System MUST emit error if codebase exceeds 500,000 files (v0.1 limit)

  Validation:
    - Monitor RSS with `psutil` or equivalent
    - Test with progressively larger synthetic codebases
    - Verify warning/error messages appear at thresholds
```

### 6. Enhance Observability Specifications

**Expert**: Michael Nygard
**Impact**: Operational monitoring and debugging

```yaml
FR-010-Enhanced: Health Endpoint Specification
  Path: GET /health/
  Implementation: Already exists in server.py, needs format spec

  Response Format (JSON):
  {
    "status": "healthy" | "degraded" | "unhealthy",
    "timestamp": "2025-10-27T15:30:45.123Z",
    "uptime_seconds": 3600,

    "indexing": {
      "state": "idle" | "indexing" | "error",
      "progress": {
        "files_discovered": 1247,
        "files_processed": 1200,
        "chunks_created": 8450,
        "errors": 3,
        "current_file": "src/auth/middleware.py",
        "start_time": "2025-10-27T14:30:00Z",
        "estimated_completion": "2025-10-27T15:35:00Z"
      },
      "last_indexed": "2025-10-27T15:30:40Z"
    },

    "services": {
      "vector_store": {
        "status": "up" | "down" | "degraded",
        "type": "qdrant_local",
        "latency_ms": 15,
        "last_check": "2025-10-27T15:30:45Z"
      },
      "embedding_provider": {
        "status": "up" | "down",
        "provider": "voyageai",
        "model": "voyage-code-3",
        "latency_ms": 250,
        "last_check": "2025-10-27T15:30:44Z",
        "circuit_breaker_state": "closed" | "open" | "half_open"
      },
      "sparse_embedding": {
        "status": "up",
        "provider": "fastembed_local",
        "model": "Splade-PP_en_v2"
      },
      "reranker": {
        "status": "up" | "down",
        "provider": "voyageai",
        "model": "rerank-2.5",
        "latency_ms": 180
      }
    },

    "statistics": {
      "total_chunks_indexed": 8450,
      "total_files_indexed": 1200,
      "languages_indexed": ["python", "typescript", "javascript"],
      "index_size_mb": 145,
      "queries_processed": 42,
      "avg_query_latency_ms": 650
    }
  }

  Status Determination:
    - healthy: All services up, indexing idle or progressing normally
    - degraded: Some services down but core functionality works (e.g., sparse-only search)
    - unhealthy: Critical services down (vector store unavailable)

FR-040: Structured Logging Requirements
  All log entries MUST include:
    - timestamp: ISO8601 format with timezone
    - level: DEBUG | INFO | WARNING | ERROR | CRITICAL
    - component: "indexer" | "searcher" | "server" | "cli" | "embedder" | "vectorstore"
    - operation: specific operation name (e.g., "embed_chunk", "hybrid_search")
    - duration_ms: for completed operations
    - user_id: optional, for multi-tenant scenarios
    - request_id: UUID for request tracing
    - error: error message and type if applicable
    - context: relevant operation-specific data

  Format: JSON for machine parsing, structured text for human readability

  Example:
  {
    "timestamp": "2025-10-27T15:30:45.123Z",
    "level": "INFO",
    "component": "searcher",
    "operation": "hybrid_search",
    "duration_ms": 680,
    "request_id": "01934e7a-8d9c-7b3a-9f42-3c8e4b5a6d7e",
    "context": {
      "query": "authentication logic",
      "intent": "understand",
      "candidates": 47,
      "results": 5
    }
  }

FR-041: Key Metrics to Track
  System MUST expose metrics via /health/ endpoint (embedded in response):

  Search Metrics:
    - search_query_latency_ms: {p50, p95, p99} over last 100 queries
    - search_queries_total: count
    - search_results_returned: {avg, p50, p95}
    - search_intent_distribution: count per IntentType

  Indexing Metrics:
    - indexing_files_per_second: current rate
    - indexing_chunks_created_total: cumulative count
    - indexing_errors_total: cumulative count
    - indexing_duration_seconds: last complete indexing duration

  Service Health Metrics:
    - embedding_api_requests_total: count
    - embedding_api_errors_total: count
    - embedding_api_latency_ms: {p50, p95, p99}
    - vector_store_operation_latency_ms: {p50, p95, p99}
    - circuit_breaker_state: closed | open | half_open
    - circuit_breaker_open_count: count of circuit opens
```

---

## Medium Priority Improvements (Should Address)

### 7. State Management and Resumption

**Experts**: Michael Nygard, Martin Fowler

```yaml
FR-034: Indexing Checkpoint and Resume
  System MUST persist indexing state to enable resumption after interruption:

  Checkpoint Data (JSON file: .codeweaver/index_checkpoint.json):
  {
    "session_id": "01934e7a-...",
    "project_path": "/path/to/codebase",
    "start_time": "2025-10-27T14:00:00Z",
    "last_checkpoint": "2025-10-27T14:15:30Z",
    "files_processed": [
      "src/auth/middleware.py",
      "src/auth/utils.py",
      ...
    ],
    "chunks_created": 450,
    "errors": [],
    "settings_hash": "sha256:abc123..." // detect config changes
  }

  Checkpoint Frequency:
    - Every 100 files processed
    - Every 5 minutes of continuous indexing
    - On SIGTERM signal (graceful shutdown)

  Resume Behavior:
    - On server start, check for checkpoint file
    - If found and settings_hash matches:
      - Log "Resuming indexing from checkpoint at 450 chunks"
      - Skip files in files_processed list
      - Continue from next file
    - If settings_hash mismatches:
      - Log "Configuration changed, reindexing from scratch"
      - Delete checkpoint, start fresh
    - If checkpoint >24 hours old:
      - Log "Checkpoint stale, reindexing from scratch"
      - Delete checkpoint, start fresh

  User Control:
    - `codeweaver server --reindex` flag: ignore checkpoint, start fresh
    - Checkpoint file location configurable via settings

FR-035: Concurrent Access Behavior
  Read Operations (Search):
    - System MUST support unlimited concurrent search requests
    - Searches are read-only, no locking required
    - Search during indexing uses eventually-consistent index
      (may not include files currently being processed)

  Write Operations (Indexing):
    - System MUST prevent concurrent indexing operations on same codebase
    - Use file lock: .codeweaver/index.lock
    - If lock exists on index start:
      - Check if process still alive (via PID in lock file)
      - If alive: reject with "Indexing already in progress (PID: 1234)"
      - If dead: remove stale lock, proceed

  CLI Behavior:
    - `codeweaver search` during indexing:
      - Show warning: "⚠️  Results may be incomplete, indexing in progress"
      - Include warning in JSON output: {"warning": "indexing_in_progress"}
    - Second `codeweaver server` while first running:
      - Error: "Server already running on port 9328"
      - Suggest: "Use different port with --port flag"
```

### 8. Complete Edge Cases Documentation

```yaml
Edge Cases - Complete Answers:

Empty Directory:
  Behavior: Accept as valid empty index
  Logging: INFO "No files discovered in /path/to/empty"
  Status: Indexing completes successfully with 0 chunks
  Health: {"indexing": {"state": "idle", "progress": {"files_discovered": 0}}}

No Files with Known Extensions:
  Behavior: Complete indexing with warning
  Logging: WARNING "No files matched configured extensions"
  Output: "Indexed 0 files. Discovered 47 files with unknown extensions."
  Suggestion: "Add custom extensions in codeweaver.toml: file_extensions = [\".xyz\"]"
  Statistics: Tabulate discovered extensions in console output

Query Matches No Results:
  CLI Output:
    ```
    Searching for: "nonexistent_function_xyz"
    No results found (searched 1,247 chunks across 85 files)

    Suggestions:
      • Check spelling and try broader terms
      • Try different intent: --intent understand vs --intent implement
      • Verify codebase is fully indexed: codeweaver status
    ```
  MCP Response:
    {
      "matches": [],
      "summary": "No matches found for query",
      "total_matches": 0,
      "total_results": 0
    }

Very Large Codebases (100k+ files):
  v0.1 Behavior:
    - Emit warning at 50,000 files: "Large codebase detected, indexing may be slow"
    - Emit error at 500,000 files: "Codebase too large for v0.1, consider filtering"
  Recommendation: "Use file filters to exclude generated code, dependencies"
  Future: v0.2 will support incremental indexing for large codebases

Multiple Concurrent Indexing Requests:
  Behavior: Reject subsequent requests with clear error
  Error Message: "Indexing already in progress (started at 14:00:00 UTC)"
  Exit Code: 1
  Suggestion: "Wait for current indexing to complete or cancel with SIGTERM"
  Implementation: File-based lock .codeweaver/index.lock

Partially Indexed Codebase (Interrupted):
  Behavior: Detect checkpoint file on startup
  Prompt: "Incomplete index found. Resume from 450 chunks or reindex?"
  Options:
    - Auto-resume if --resume flag or CI environment detected
    - Interactive prompt in terminal
    - Reindex if --reindex flag present
  Delete checkpoint: After successful completion or explicit reindex
```

---

## Additional Recommendations

### 9. Add Reference Test Suite Requirement

**Expert**: Lisa Crispin

```yaml
FR-036: Reference Test Suite
  System MUST be validated against reference test suite for semantic search quality:

  Test Suite Location: tests/integration/reference_queries.yml

  Structure:
  ```yaml
  - query: "file filtering logic"
    intent: understand
    expected_top_3:
      - file: "src/middleware/filtering.py"
        symbol: "FileFilterSettings"
        min_score: 0.80
      - file: "src/middleware/discovery.py"
        symbol: "FileDiscoveryService"
        min_score: 0.70
    expected_excluded:
      - "tests/*"

  - query: "chunking strategy implementation"
    intent: implement
    expected_top_5:
      - file: "src/middleware/chunking.py"
        contains: "ChunkerSelector"
  ```

  Quality Targets:
    - Minimum 20 query/result pairs covering all IntentType values
    - Precision@3: ≥70% (7/10 queries return expected result in top 3)
    - Precision@5: ≥80% (8/10 queries return expected result in top 5)
    - Test against CodeWeaver's own codebase (dogfooding)

  CI Integration:
    - Run on every PR affecting search/ranking logic
    - Fail build if precision drops below thresholds
    - Track precision trends over time

  Maintenance:
    - Review and update quarterly
    - Add new queries for bug reports
    - Validate against human relevance judgments
```

### 10. Clarify or Remove FR-028

**Expert**: Karl Wiegers

```yaml
FR-028 (CURRENT - UNTESTABLE):
  "System MUST be designed to support future agent-driven intent resolution
   and curation (extensibility requirement)"

OPTION A (Remove - It's Architecture Guidance):
  Remove from functional requirements section
  Move to "Architecture Notes" section
  Rationale: "Designed to support" is not testable for v0.1

OPTION B (Make Concrete and Testable):
  FR-028: API Stability for Intent Evolution
    IntentType enum MUST be designed to allow future additions without
    breaking changes to find_code tool API.

    Requirements:
      - IntentType is defined as extensible Python enum
      - find_code accepts IntentType | str for forward compatibility
      - Unknown IntentType values handled gracefully (default to None)
      - API clients can pass custom intent strings

    Test:
      - Add new IntentType value in test
      - Verify find_code accepts new value without code changes
      - Verify backward compatibility with old clients

    Rationale: Enables v0.2+ to add agent-driven intent analysis without
               breaking v0.1 clients

RECOMMENDATION: Choose Option B if API stability matters for early adopters,
                otherwise Option A to reduce scope.
```

---

## Implementation Priority

### Before Implementation Starts (Critical)
1. ✅ Add interface specifications (FR-014a/b, FR-011a/b/c/d)
2. ✅ Document actual data models with module references
3. ✅ Rewrite ambiguous requirements (FR-006, FR-019)
4. ✅ Add timeout specifications (FR-033)
5. ✅ Enhance circuit breaker details (FR-008a)

### During Implementation (High Priority)
6. ✅ Add concrete scenario examples section
7. ✅ Add performance requirements (FR-037, FR-038, FR-039)
8. ✅ Specify health endpoint format (FR-010-Enhanced, FR-040, FR-041)
9. ✅ Create reference test suite (FR-036)
10. ✅ Complete edge cases table with answers

### Optional Enhancements (Medium Priority)
11. Add state management (FR-034, FR-035)
12. Implement CLI status command (FR-011d)
13. Clarify or remove FR-028
14. Add deployment validation checklist

---

## Summary of Changes Required

### Specification Document Updates

**Section: Functional Requirements**
- Add FR-014a, FR-014b (find_code interface)
- Add FR-011a, FR-011b, FR-011c, FR-011d (CLI commands)
- Rewrite FR-006 (chunking with measurable criteria)
- Rewrite FR-019 (semantic scoring with weights)
- Add FR-033 (timeouts)
- Enhance FR-008a (circuit breaker details)
- Add FR-034, FR-035 (state management - optional)
- Add FR-036 (reference test suite)
- Add FR-037, FR-038, FR-039 (performance requirements)
- Enhance FR-010 (health endpoint format)
- Add FR-040, FR-041 (logging and metrics)

**New Section: Data Models and Types**
- Reference actual modules for all entities
- Include import paths and key fields
- Link to actual Pydantic model definitions

**New Section: Scenario Examples**
- Add 4+ concrete examples with actual inputs/outputs
- Include both success and error scenarios
- Show MCP and CLI interactions

**Section: Edge Cases**
- Complete all unanswered questions
- Add expected behavior for each case
- Include actual error messages and outputs

**Section: Success Metrics**
- Add precision targets from FR-036
- Add performance targets from FR-037/038/039
- Add health check validation

---

## Expert Consensus

**All experts agree**:
1. ✅ Specification has strong structural foundation
2. ✅ Requirements numbering and traceability is excellent
3. ✅ Error handling strategy is well-thought-out
4. ❌ Missing interface specifications are the biggest blocker
5. ✅ Concrete examples would dramatically improve clarity
6. ❌ Some requirements need measurable acceptance criteria before implementation

**Quality Projection**:
- Current: 7.5/10
- With Critical Fixes: 8.5/10
- With All High Priority: 9.0/10
- With Complete Implementation: 9.5/10

**Next Steps**:
1. Review this document with team
2. Prioritize changes based on implementation timeline
3. Update spec.md with agreed-upon improvements
4. Create reference test suite file
5. Begin implementation with clear, testable requirements

---

**Document Version**: 1.0
**Last Updated**: 2025-10-27
