<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver v0.1 Quickstart

**Feature**: CodeWeaver v0.1 Release
**Date**: 2025-10-27
**Based On**: User scenarios from spec.md

## Prerequisites

- Python 3.12 or higher
- Git (for cloning repository)
- 8GB RAM minimum (for vector operations)
- API keys (optional, see Configuration)

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/knitli/codeweaver.git
cd codeweaver
```

### 2. Set Up Environment

```bash
# Install mise (if not already installed)
# See: https://mise.jdx.dev/getting-started.html
curl https://mise.run | sh

# Set up development environment
mise run setup

# Install dependencies
uv sync --all-groups

# Activate environment
mise run activate
```

### 3. Configure CodeWeaver

Create a configuration file at `codeweaver.toml`:

```toml
[codeweaver]
project_path = "/path/to/your/codebase"  # Required: path to index
max_chunk_size = 800                      # Optional: default 800 tokens

[embedding]
provider = "voyageai"                     # Options: voyageai, openai
model = "voyage-code-3"                   # VoyageAI code embedding model
# api_key set via VOYAGE_API_KEY env var

[sparse_embedding]
provider = "fastembed"                    # Local sparse embeddings
model = "prithivida/Splade-PP_en_v2"     # SPLADE model

[reranking]
provider = "voyageai"
model = "voyage-rerank-2.5"
# api_key set via VOYAGE_API_KEY env var

[vector_store]
type = "qdrant"
location = "local"                        # Local Qdrant instance
path = ".codeweaver/qdrant"              # Persistence directory
```

**Environment Variables**:

```bash
# Required for VoyageAI (dense embeddings + reranking)
export VOYAGE_API_KEY="your-api-key-here"

# Optional alternatives
# export OPENAI_API_KEY="your-openai-key"
```

### 4. Verify Installation

```bash
# Check configuration
codeweaver config --show

# Expected output:
# CodeWeaver Configuration
# ========================
# Project Settings:
#   path: /path/to/your/codebase
#   indexed: no
```

## Quick Start Scenarios

### Scenario 1: Start Server and Index Codebase

**Goal**: Start CodeWeaver MCP server, automatically index a codebase

```bash
# Start server (will auto-index project from config)
codeweaver server --config ./codeweaver.toml

# Expected output:
# CodeWeaver MCP server starting...
# Project: /path/to/your/codebase
# Host: 127.0.0.1:9328
# Indexing: starting...
#
# Discovering files...
# Found 1,247 files
# Indexing: 450/1247 files processed (3250 chunks created)
# Indexing: 900/1247 files processed (6500 chunks created)
# Indexing complete: 1,247 files, 8,500 chunks in 180s
#
# Server ready. Listening for MCP requests.
```

**Validation**:
- Server starts without errors
- Indexing completes (all files processed)
- Server listening on port 9328

### Scenario 2: Search via CLI

**Goal**: Execute a semantic code search query from command line

```bash
# Basic search
codeweaver search "authentication logic" --limit 5

# Expected output:
# Found 4 matches (47 candidates processed in 850ms)
#
# 1. src/auth/middleware.py:15-85 (relevance: 0.92, type: DEFINITION_TYPE)
#    class AuthMiddleware:
#        """Handles authentication and authorization for requests."""
#        def __init__(self, config: AuthConfig):
#            ...
#
# 2. src/auth/utils.py:10-35 (relevance: 0.87, type: DEFINITION_CALLABLE)
#    def authenticate_user(username: str, password: str) -> User | None:
#        """Authenticate user credentials and return User object."""
#        ...
#
# 3. src/auth/tokens.py:5-25 (relevance: 0.78, type: OPERATION_DATA)
#    def validate_jwt_token(token: str) -> TokenPayload:
#        """Validate JWT token and extract payload."""
#        ...
```

**Intent-Specific Search**:

```bash
# For understanding codebase
codeweaver search "how does chunking work" --intent understand

# For implementing features
codeweaver search "database connection pooling" --intent implement --limit 3

# For debugging
codeweaver search "error handling" --intent debug

# JSON output for scripting
codeweaver search "config loading" --output-format json | jq '.matches[0].file'
```

**Validation**:
- Results returned in <3 seconds
- Relevance scores ranked correctly
- Code snippets displayed properly

### Scenario 3: Monitor Indexing Progress

**Goal**: Check indexing status and system health

```bash
# Query health endpoint (server must be running)
curl http://localhost:9328/health/ | jq

# Expected output:
# {
#   "status": "healthy",
#   "timestamp": "2025-10-27T14:30:00Z",
#   "uptime_seconds": 3600,
#   "indexing": {
#     "state": "indexing",
#     "progress": {
#       "files_discovered": 1247,
#       "files_processed": 450,
#       "chunks_created": 3250,
#       "errors": 2,
#       "current_file": "src/services/search.py",
#       "start_time": "2025-10-27T14:00:00Z",
#       "estimated_completion": "2025-10-27T15:00:00Z"
#     }
#   },
#   "services": {
#     "vector_store": {"status": "up", "latency_ms": 12},
#     "embedding_provider": {"status": "up", "model": "voyage-code-3", "latency_ms": 185}
#   },
#   "statistics": {
#     "total_chunks_indexed": 3250,
#     "total_files_indexed": 450,
#     "languages_indexed": ["python", "typescript", "rust"],
#     "queries_processed": 127,
#     "avg_query_latency_ms": 850
#   }
# }
```

**CLI Status (when implemented)**:

```bash
codeweaver status

# Expected output:
# CodeWeaver Status
# =================
# Server: running
# Uptime: 1h 0m
#
# Indexing:
#   State: indexing
#   Files Processed: 450/1247 (36%)
#   Chunks Created: 3250
#   Current: src/services/search.py
#
# Services:
#   Vector Store: up (12ms)
#   Embedding Provider: up (185ms)
#   Reranking: up (150ms)
```

**Validation**:
- Health endpoint responds in <200ms
- Progress updates every 5 seconds
- Accurate statistics reported

### Scenario 4: Use MCP Tool from AI Agent

**Goal**: AI agent (e.g., Claude Code) uses `find_code` tool to search codebase

**MCP Server Configuration** (for Claude Code):

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "codeweaver": {
      "command": "codeweaver",
      "args": ["server", "--config", "/path/to/codeweaver.toml"],
      "env": {
        "VOYAGE_API_KEY": "your-api-key"
      }
    }
  }
}
```

**Agent Interaction**:

```
User: "Find the authentication middleware implementation"

Agent: [Calls find_code tool]
{
  "query": "authentication middleware implementation",
  "intent": "understand",
  "max_results": 5
}

Agent receives:
{
  "matches": [
    {
      "file": {"path": "src/auth/middleware.py", "language": "python"},
      "content": {
        "content": "class AuthMiddleware:\n    def __init__(self, config: AuthConfig):\n        ...",
        "line_range": [15, 85],
        "language": "python"
      },
      "span": [15, 85],
      "relevance_score": 0.92,
      "match_type": "SEMANTIC",
      "related_symbols": ["AuthConfig", "authenticate_request"]
    }
  ],
  "summary": "Found authentication middleware implementation in auth module",
  "query_intent": "understand",
  "total_matches": 47,
  "total_results": 1,
  "token_count": 450,
  "execution_time_ms": 850,
  "search_strategy": ["HYBRID_SEARCH", "SEMANTIC_RERANK"],
  "languages_found": ["python"]
}

Agent: "I found the authentication middleware implementation in src/auth/middleware.py..."
```

**Validation**:
- MCP server connects successfully
- `find_code` tool available to agent
- Structured responses received
- Agent can consume results effectively

### Scenario 5: Error Recovery - Embedding API Unavailable

**Goal**: System gracefully degrades when VoyageAI API is down

```bash
# Start server (VoyageAI API down)
codeweaver server --config ./codeweaver.toml

# Expected behavior:
# - Dense embeddings fail with timeout (30s)
# - Falls back to sparse-only embeddings (FastEmbed local)
# - Indexing continues with sparse vectors only
# - Warning logged: "VoyageAI unavailable, using sparse-only search"

# Search query during degraded state
codeweaver search "authentication logic"

# Expected output:
# ⚠️  Warning: Dense embedding service unavailable, using sparse search only
# Results may have reduced semantic accuracy
#
# Found 5 matches (sparse search in 450ms)
# [results from sparse vector search only]
```

**Health Endpoint During Degradation**:

```bash
curl http://localhost:9328/health/ | jq '.status, .services.embedding_provider'

# Output:
# "degraded"
# {
#   "status": "down",
#   "model": "voyage-code-3",
#   "latency_ms": 0,
#   "circuit_breaker_state": "open"
# }
```

**Validation**:
- System continues operating (no crash)
- Sparse-only search functions correctly
- User warned via CLI/MCP context
- Health status reflects degradation

### Scenario 6: Self-Hosted Testing (Dogfooding)

**Goal**: Index CodeWeaver's own codebase and search it

```bash
# Point CodeWeaver at itself
cat > codeweaver.toml <<EOF
[codeweaver]
project_path = "."  # Current directory (codeweaver)
EOF

# Start server
codeweaver server --config ./codeweaver.toml

# Test searches (from reference test suite)
codeweaver search "how does chunking work" --intent understand
codeweaver search "embedding provider interface" --intent implement
codeweaver search "where are errors logged" --intent debug
codeweaver search "settings configuration" --intent configure
```

**Expected Results** (Reference Test Suite - FR-036):

Query: "how does chunking work"
- Top result: `src/codeweaver/middleware/chunking.py` (ChunkerSelector class)
- Precision@3: ≥70% (relevant result in top 3)

Query: "embedding provider interface"
- Top result: `src/codeweaver/providers/embedding/base.py` (EmbeddingProvider protocol)
- Precision@3: ≥70%

Query: "where are errors logged"
- Top result: Error handling in `src/codeweaver/server.py` or middleware
- Precision@5: ≥80%

**Validation**:
- Indexing completes for CodeWeaver codebase (~100 files)
- Search quality meets reference test targets
- All IntentType values produce relevant results

## Common Operations

### Update Index After Code Changes

```bash
# Currently: Restart server to re-index
codeweaver server --config ./codeweaver.toml --reindex

# Future (v0.2): Incremental indexing with file watching
```

### Change Embedding Provider

```toml
# Use OpenAI instead of VoyageAI
[embedding]
provider = "openai"
model = "text-embedding-3-small"
# Set OPENAI_API_KEY environment variable
```

### Export Search Results

```bash
# JSON format for scripting
codeweaver search "database queries" --output-format json > results.json

# Markdown format for documentation
codeweaver search "API endpoints" --output-format markdown > api_docs.md
```

## Troubleshooting

### Issue: Server fails to start

**Check**:
```bash
# Verify Python version
python --version  # Should be 3.12+

# Verify dependencies installed
uv sync --all-groups

# Check port availability
lsof -i :9328  # Should be empty
```

### Issue: No results found

**Check**:
```bash
# Verify indexing completed
curl http://localhost:9328/health/ | jq '.indexing.state'  # Should be "idle"

# Check statistics
curl http://localhost:9328/health/ | jq '.statistics.total_chunks_indexed'  # Should be > 0

# Verify project path
codeweaver config --show | grep "path:"
```

### Issue: Slow search queries

**Check**:
```bash
# Monitor service latencies
curl http://localhost:9328/health/ | jq '.services'

# Expected:
# - vector_store.latency_ms: <50ms
# - embedding_provider.latency_ms: <300ms
# - reranking.latency_ms: <200ms

# If high latency:
# - Check network connection to VoyageAI
# - Consider local Qdrant (already default)
# - Reduce max_results parameter
```

### Issue: High error count during indexing

**Check**:
```bash
# View health endpoint
curl http://localhost:9328/health/ | jq '.indexing.progress.errors'

# If ≥25 errors:
# - Check file permissions
# - Review unsupported file types
# - Examine indexing logs for details
```

## Performance Benchmarks

### Expected Performance (v0.1)

**Indexing**:
- Small codebases (<1k files): 2-5 minutes
- Medium codebases (1k-10k files): 10-30 minutes
- Large codebases (10k-50k files): 1-3 hours
- Rate: ≥100 files/minute (FR-038)

**Search**:
- Small codebases (<1k files): <1 second
- Medium codebases (1k-10k files): <3 seconds (FR-037)
- Large codebases (10k-100k files): <10 seconds (FR-037)

**Hardware**: 4 CPU cores, 8GB RAM, SSD storage

## Next Steps

### Integration with AI Agents

1. **Claude Code**: Add MCP server to `claude_desktop_config.json`
2. **Cursor**: Configure MCP server in Cursor settings
3. **Custom agents**: Use MCP client library to connect

### Advanced Configuration

- Custom file filters (`.gitignore` patterns)
- Language-specific chunking rules
- Semantic classification weights
- Performance tuning (batch sizes, timeouts)

### Reference Test Suite

Run dogfooding tests:

```bash
# Run integration tests (requires CodeWeaver indexed)
pytest tests/integration/reference_queries.yml

# Expected: Precision@3 ≥70%, Precision@5 ≥80%
```

## Success Criteria

✅ Developer can go from clone to first search in <10 minutes
✅ Search returns relevant results for common queries
✅ MCP integration works with at least one AI agent
✅ All Quickstart commands execute without errors
✅ Reference test suite achieves quality targets
✅ Search queries complete within performance targets
✅ Health endpoint returns accurate status

## Documentation

- **README.md**: Project overview and installation
- **ARCHITECTURE.md**: Design decisions and principles
- **CLAUDE.md**: AI agent context for Claude Code
- **API docs**: See `contracts/` directory

---

**Quickstart Status**: ✅ COMPLETE
**Based On**: Feature spec user scenarios and acceptance criteria
**Validation**: Commands testable once implementation complete
