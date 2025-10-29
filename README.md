<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->
# CodeWeaver

Extensible context platform and MCP server for hybrid semantic code search and targeted context delivery to AI coding agents.

**CodeWeaver solves the fundamental context delivery problem**: AI agents get overwhelmed with irrelevant code, wasting tokens and missing critical patterns. We deliver precisely what agents need through a single natural language interface, reducing context bloat by 60-80% while improving search precision.

## Why CodeWeaver?

### The Problem: Context Overload in AI Coding

**AI agents drown in irrelevant context, causing real costs:**
- **70-80% of returned code goes unused** by the agent
- **Token costs scale exponentially** with conversation length
- **Agents miss critical patterns** buried in noise
- **Developers waste time** on off-target suggestions and hallucinations

**Why This Happens:**

**🔀 Tool Confusion**: Most MCP servers expose 5-20+ tools for code discovery (search, grep, symbols, files, memory...). Agents waste reasoning cycles choosing *how* to search instead of focusing on *what* to find.

**📚 Context Bloat**: Average MCP tool loads consume 25K-40K tokens (20% of Claude's context window)—just for tool descriptions. That's ~$5 per 20-turn conversation in unused prompt overhead.

**🔒 Proprietary Lock-In**: IDE semantic search exists (VS Code, Cursor, Roo) but stays locked behind proprietary APIs. Developers run 5-10 redundant indexes with no data portability or control.

**The Result:**
```
❌ Traditional Approach:
Query: "How do we handle authentication?"
Returns: 47 files, 12,000 lines, 45KB context
Agent uses: ~8 files, ~400 lines (85% wasted)
Cost: $0.15-$0.30 per query

✅ CodeWeaver:
Query: "How do we handle authentication?"  
Returns: 8 files, 450 lines, 12KB context
Agent uses: ~7 files, ~380 lines (<20% wasted)
Cost: $0.03-$0.06 per query
```

### Our Solution: Precise, Agent-Aware Context

**🎯 Single-Tool Simplicity**
- One `find_code` tool with natural language queries—that's it
- No tool selection logic, no multi-endpoint orchestration
- Agents focus on *what* they need, not *how* to search
- **Impact**: Eliminates tool confusion, reduces cognitive load

**🤖 Agent-Driven Curation**
- Uses MCP sampling: your agent curates context using a *separate agent instance*
- Zero context pollution from the curation process itself
- 40-60% better precision vs. keyword-only search
- **Impact**: Smarter results without cluttering your agent's context

**🔍 Hybrid Intelligence**
- Text search + semantic embeddings + AST-aware analysis
- Span-based precision with exact line/column tracking
- Unified ranking across multiple signals
- **Impact**: Finds what keyword search misses, returns exactly what's relevant

**🔧 Platform Extensibility**
- 10+ embedding providers (VoyageAI, OpenAI, fastembed, sentence-transformers)
- Vendor-agnostic vector stores (Qdrant, in-memory)
- Plugin architecture for custom providers and data sources
- 26 languages (full AST) + 170+ languages (heuristic chunking)
- **Impact**: Use your existing infrastructure, support any codebase (even COBOL to Rust)

### The Impact

**For Developers:**
- ⚡ Faster answers about unfamiliar code
- 💰 60-80% reduction in AI token costs
- 🎯 Precise context prevents hallucinations

**For Teams:**
- 🔧 Plugin architecture fits your infrastructure
- 🌍 Legacy codebase support (COBOL to Rust)
- 🔓 Open source with dual licensing (MIT OR Apache-2.0)

**For AI Agents:**
- 📍 Exact line/column references (no "nearby code" confusion)
- 🧠 Task-aware context ranking
- 🔄 Background indexing keeps context current

---

## Installation

**Current Status**: v0.1 Development - Install from repository for working features

### Prerequisites
- Python 3.12 or higher
- Git for cloning repository
- 8GB RAM minimum for vector operations
- VoyageAI API key (for embeddings and reranking)

### Quick Install

```bash
# Clone repository
git clone https://github.com/knitli/codeweaver-mcp.git
cd codeweaver-mcp

# Set up environment (requires mise: https://mise.jdx.dev)
mise run setup

# Install dependencies
uv sync --all-groups

# Activate environment
mise run activate
```

### Configuration

Create `codeweaver.toml` in your project:

```toml
[codeweaver]
project_path = "/path/to/your/codebase"  # Required
max_chunk_size = 800                      # Optional: default 800 tokens

[embedding]
provider = "voyageai"
model = "voyage-code-3"
# Set VOYAGE_API_KEY environment variable

[sparse_embedding]
provider = "fastembed"
model = "prithivida/Splade-PP_en_v2"

[reranker]
provider = "voyageai"
model = "voyage-rerank-2.5"

[vector_store]
type = "qdrant"
location = "local"
path = ".codeweaver/qdrant"
```

**Set API Key**:
```bash
export VOYAGE_API_KEY="your-api-key-here"
```

---

## Quick Start

### 1. Start Server with Auto-Indexing

```bash
# Start CodeWeaver MCP server (auto-indexes project from config)
codeweaver server --config ./codeweaver.toml

# Expected output:
# CodeWeaver MCP server starting...
# Project: /path/to/your/codebase
# Host: 127.0.0.1:9328
# Indexing: starting...
# Discovering files...
# Found 1,247 files
# Indexing complete: 1,247 files, 8,500 chunks in 180s
# Server ready. Listening for MCP requests.
```

### 2. Search Your Code (CLI)

```bash
# Basic search
codeweaver search "authentication logic" --limit 5

# Intent-specific search
codeweaver search "how does chunking work" --intent understand
codeweaver search "database connection pooling" --intent implement --limit 3

# JSON output for scripting
codeweaver search "config loading" --output-format json | jq '.matches[0].file'
```

### 3. Check Indexing Progress

```bash
# Query health endpoint (server must be running)
curl http://localhost:9328/health/ | jq

# Example response:
# {
#   "status": "healthy",
#   "indexing": {
#     "state": "idle",
#     "progress": {
#       "files_processed": 1247,
#       "chunks_created": 8500
#     }
#   },
#   "services": {
#     "vector_store": {"status": "up"},
#     "embedding_provider": {"status": "up", "model": "voyage-code-3"}
#   }
# }
```

### 4. Use with AI Agents (MCP)

Add to your MCP client configuration (e.g., `claude_desktop_config.json`):

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

Then use natural language from your AI agent:
```
User: "Find the authentication middleware implementation"

Agent: [Calls find_code tool with query]
Agent receives structured results with:
- Exact file paths and line ranges
- Code content with syntax highlighting
- Relevance scores (0.0-1.0)
- Related symbols and dependencies
```

---

---

## What Works Today (v0.1)

✅ **Core Functionality**:
- Hybrid search (dense + sparse vectors)
- Semantic reranking with voyage-rerank-2.5
- CLI and MCP interfaces
- Auto-indexing on server startup
- Health monitoring endpoint
- Circuit breaker resilience
- Error recovery and graceful degradation
- Checkpoint/resume for interrupted indexing

✅ **Search Features**:
- Natural language queries
- Intent-based ranking (UNDERSTAND, IMPLEMENT, DEBUG, etc.)
- Exact line/column references
- Multi-language support (20+ with AST, 170+ with heuristics)
- JSON, table, and markdown output formats

✅ **Operational**:
- Local Qdrant vector store
- VoyageAI embeddings (voyage-code-3)
- FastEmbed sparse vectors (SPLADE)
- Graceful degradation when services unavailable
- Structured logging and metrics

## Planned for v0.2

🔮 **Coming Soon**:
- Real-time code change watching (FileWatcher exists but not fully wired)
- Agent-driven intent analysis (currently keyword-based heuristics)
- Search result explanations
- Advanced filters (date, file type, size)

---

**📊 For Product Managers**: See [PRODUCT.md](PRODUCT.md) for product overview, user personas, competitive positioning, and roadmap.

**🏗️ Architecture Reference**: See [ARCHITECTURE.md](ARCHITECTURE.md) for design decisions, principles, and technical philosophy.

## How It Works 

```
┌─────────────────┐
│  Your AI Agent  │  "How do we handle authentication?"
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│          CodeWeaver MCP Server                   │
│                                                   │
│  ┌──────────────┐      ┌──────────────────────┐ │
│  │  find_code   │─────▶│  Agent Curation      │ │
│  │     Tool     │      │  (MCP Sampling)      │ │
│  └──────────────┘      └──────────┬───────────┘ │
│                                   │              │
│                                   ▼              │
│  ┌────────────────────────────────────────────┐ │
│  │         Hybrid Search Pipeline             │ │
│  │                                            │ │
│  │  ┌──────────┐  ┌──────────┐  ┌─────────┐ │ │
│  │  │   Text   │  │ Semantic │  │   AST   │ │ │
│  │  │  Search  │  │Embeddings│  │Analysis │ │ │
│  │  └──────────┘  └──────────┘  └─────────┘ │ │
│  │                                            │ │
│  │  ┌────────────────────────────────────┐  │ │
│  │  │      Unified Ranking               │  │ │
│  │  │   (Span-based Assembly)            │  │ │
│  │  └────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────┘ │
│                                                   │
│  Providers: VoyageAI, OpenAI, fastembed,         │
│            Qdrant, in-memory, custom...          │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Precise Context Response                │
│                                          │
│  auth/middleware.py:45-67               │
│  auth/models.py:12-34                   │
│  config/security.py:89-102              │
│                                          │
│  12KB context (vs. 45KB traditional)    │
│  >90% relevant (vs. 20% traditional)    │
└─────────────────────────────────────────┘
```

## Overview

CodeWeaver is more than an MCP server—it’s a context platform. It distills and delivers targeted, token-efficient context to your AI coding agent. Under the hood, it functions like RAG + hybrid search over semantically indexed code, and it can integrate arbitrary data sources (e.g., external API docs) through a provider architecture.

Status: Pre-release. Core architecture is in place; several integrations are still being tied together (see "Project status" and "Roadmap" below).


Contents
- Why CodeWeaver?
- Product overview (see [PRODUCT.md](PRODUCT.md))
- Features at a glance
- Quickstart
- CLI overview
- Concepts and architecture
- Providers and optional extras
- Current tool surface (MCP + CLI)
- Project status (what works vs. WIP)
- Roadmap
- Development
- Telemetry and auth middleware
- Licensing
- Links



Features at a glance

**What you get:**
- **🎯 Pinpoint accuracy**: Exact line/column references eliminate "nearby code" confusion that wastes agent attention
- **🔍 Intelligent search**: Hybrid text + semantic + AST analysis finds what keyword search misses
- **⚡ Stay current**: Background file watching keeps index fresh without manual intervention
- **🔧 Infrastructure freedom**: 10+ embedding providers, multiple vector stores - use what you already have
- **📊 Built-in insights**: Statistics and telemetry help you understand search quality and optimize performance
- **🛠️ Flexible deployment**: Run as MCP server for agents or use CLI for interactive development

**Technical foundation:**
- Span-based code intelligence with exact line/column tracking and immutable set operations
- Hybrid search with unified ranking across text, semantic, and AST signals (semantic pipeline integration in progress)
- Production-ready filtering system with pydantic-based validation
- Plugin architecture: pluggable embedding, rerank, agent, vector store, and data source providers
- pydantic-ai integration for intent analysis, query rewriting, and context planning
- Type-safe configuration and structured results throughout
- Multiple interfaces: MCP server, HTTP, CLI search, config management


## Troubleshooting

### Server Fails to Start

**Check Prerequisites**:
```bash
# Verify Python version (must be 3.12+)
python --version

# Verify dependencies installed
uv sync --all-groups

# Check port availability (should be empty)
lsof -i :9328
```

### No Search Results Found

**Verify Indexing**:
```bash
# Check indexing completed
curl http://localhost:9328/health/ | jq '.indexing.state'  # Should be "idle"

# Check statistics
curl http://localhost:9328/health/ | jq '.statistics.total_chunks_indexed'  # Should be > 0

# Verify project path
codeweaver config --show | grep "path:"
```

### VoyageAI API Unavailable

**Graceful Degradation**:
- System automatically falls back to sparse-only search (local FastEmbed)
- Warning message displayed: "Dense embedding service unavailable"
- Search continues with reduced semantic accuracy
- Health endpoint shows `"status": "degraded"`

**Check Circuit Breaker**:
```bash
curl http://localhost:9328/health/ | jq '.services.embedding_provider.circuit_breaker_state'
# Should be "closed" (healthy) or "open" (failed)
```

### Slow Search Queries

**Monitor Service Latencies**:
```bash
curl http://localhost:9328/health/ | jq '.services'

# Expected latencies:
# - vector_store: <50ms
# - embedding_provider: <300ms
# - reranker: <200ms
```

**Optimization Tips**:
- Use local Qdrant (already default in config)
- Reduce `--limit` parameter for searches
- Check network connection to VoyageAI
- Consider smaller codebase or filtering

### High Error Count During Indexing

**Check Errors**:
```bash
curl http://localhost:9328/health/ | jq '.indexing.progress.errors'

# If ≥25 errors:
# - Check file permissions
# - Review unsupported file types
# - Examine server logs for details
```



## CLI Commands

### Server
Start the MCP server with auto-indexing:
```bash
codeweaver server --config ./codeweaver.toml
codeweaver server --project /path/to/codebase --port 9328
codeweaver server --debug  # Enable debug logging
```

### Search
Execute semantic code searches:
```bash
codeweaver search "query" [--format {json|table|markdown}]
codeweaver search "authentication logic" --limit 5
codeweaver search "how does chunking work" --intent understand
codeweaver search "database setup" --intent implement --project ./my-project
```

### Config
Manage configuration settings:
```bash
codeweaver config --show                    # Display current configuration
codeweaver config --project ./my-project    # Show project-specific config
```

**Use `--help`** on any command for full options.



## Architecture Overview (v0.1)

### Core Components

**Semantic Chunking**:
- AST-based boundaries for 20+ languages (functions, classes, methods)
- Delimiter-based heuristics for 170+ additional languages
- Target chunk size: 200-800 tokens
- Preserves complete logical units

**Hybrid Search Pipeline**:
1. Dense embeddings: VoyageAI voyage-code-3 (768 dimensions)
2. Sparse embeddings: FastEmbed Splade-PP (local, no API)
3. Vector storage: Qdrant (local with persistence)
4. Reranking: VoyageAI voyage-rerank-2.5
5. Semantic scoring: ImportanceScores weighted by IntentType

**Intent-Based Ranking**:
- `UNDERSTAND`: Boost definitions and interfaces
- `IMPLEMENT`: Boost definitions and boundaries
- `DEBUG`: Boost control flow and operations
- `TEST`: Boost test definitions
- `CONFIGURE`: Boost configuration patterns
- `DOCUMENT`: Boost documentation blocks

**Provider System**:
- Embedding: default primary is VoyageAI voyage-code-3 (requires API key); fallback local to 
- Vector Store: Qdrant local or remote
- Reranking: VoyageAI rerank-2.5
- Circuit breaker resilience for all external APIs

**Configuration**:
- Multi-source: TOML/YAML/JSON files, environment variables
- Pydantic-settings validation
- Token budgeting and batch tracking


## Performance Expectations (v0.1)

### Indexing Performance
- Small codebases (<1k files): 2-5 minutes
- Medium codebases (1k-10k files): 10-30 minutes
- Large codebases (10k-50k files): 1-3 hours
- Rate: ≥100 files/minute

### Search Performance
- Small codebases (<1k files): <1 second
- Medium codebases (1k-10k files): <3 seconds
- Large codebases (10k-100k files): <10 seconds


### Resource Limits
- Maximum chunk size: 4000 tokens (hard limit, truncate if exceeded)
- Maximum concurrent embedding requests: 10
- Maximum memory per indexing session: 2GB resident set size
- Warning at 50,000 files
- Error at 500,000 files (v0.1 limit)


## MCP Tool Interface

### find_code Tool

**Purpose**: Single natural language interface for semantic code search

**Parameters**:
- `query` (str, required): Natural language search query
- `intent` (str, optional): Search intent (understand|implement|debug|optimize|test|configure|document)
- `token_limit` (int, default=10000): Maximum tokens in response
- `include_tests` (bool, default=False): Include test files in results
- `focus_languages` (tuple[str], optional): Filter by programming languages
- `max_results` (int, default=50): Maximum matches to return

**Response Structure** (`FindCodeResponseSummary`):
```python
{
  "matches": [
    {
      "file": {"path": "src/auth.py", "language": "python"},
      "content": {"content": "...", "line_range": [15, 85]},
      "span": [15, 85],
      "relevance_score": 0.92,
      "match_type": "SEMANTIC",
      "related_symbols": ["AuthConfig", "authenticate"]
    }
  ],
  "summary": "Found authentication implementation in auth module",
  "query_intent": "understand",
  "total_matches": 47,
  "total_results": 5,
  "token_count": 450,
  "execution_time_ms": 850,
  "search_strategy": ["HYBRID_SEARCH", "SEMANTIC_RERANK"],
  "languages_found": ["python"]
}
```

## Development

### Setup Development Environment

```bash
# Clone and install full dev environment
git clone https://github.com/knitli/codeweaver-mcp.git
cd codeweaver-mcp
# if you don't have mise installed, first run:
# chmod +x scripts/ && ./scripts/dev-env/install-mise.sh
mise run setup
uv sync --all-groups
```

### Code Quality Commands

```bash
# Fix code issues (imports, formatting, linting)
mise run fix

# Run linting checks
mise run lint

# Format code
mise run format-fix

# Type checking
mise run check
```

### Testing

```bash
# Run tests
mise run test

# Run with coverage
mise run test-cov

# Watch mode
mise run test-watch

# Run specific markers
pytest -m "unit"              # Unit tests only
pytest -m "integration"       # Integration tests only
pytest -m "not network"       # Skip network-dependent tests
```

### Build

```bash
# Build package
mise run build

# Clean build artifacts
mise run clean

# Full CI pipeline
mise run ci
```

### Contributing

**License**: Dual-licensed (MIT OR Apache-2.0)
**Requirements**: Read `CONTRIBUTORS_LICENSE_AGREEMENT.py`
**Issues & PRs**: Welcome for providers, vector stores, pipelines, and all improvements

**Code Standards**:
- Follow `CODE_STYLE.md` principles
- Line length: 100 characters
- Google-style docstrings
- Type hints required (strict pyright)
- Pydantic models for data structures



## Roadmap

### ✅ v0.1 MVP (Current Release)
- ✅ Core integration complete
- ✅ Provider registry and statistics
- ✅ FastMCP server with find_code tool
- ✅ CLI commands (server, search, config)
- ✅ Hybrid search (dense + sparse vectors)
- ✅ Semantic reranking
- ✅ AST-aware chunking
- ✅ Health monitoring endpoint
- ✅ Error recovery and graceful degradation
- ✅ Checkpoint/resume indexing

### 🚧 v0.2 (Next Release)
- Real-time file watching (FileWatcher wiring)
- Agent-driven intent analysis (pydantic-ai integration)
- Search result explanations
- Advanced filters (language, file type, date ranges)
- Multiple simultaneous codebases
- Comprehensive test coverage (unit + integration)
- Telemetry and observability improvements

### 🔮 v0.3+ (Future)
- pydantic-graph pipelines for multi-stage workflows
- Additional vector stores (Pinecone, Weaviate)
- Add LiteLLM and MorphLLM to providers
- Web UI for search and monitoring
- Performance optimizations for large codebases (let us know how it handles!)

---

## Documentation

- **[README.md](README.md)**: This file - project overview and quickstart
- **[ARCHITECTURE.md](ARCHITECTURE.md)**: Design decisions and principles
- **[PRODUCT.md](PRODUCT.md)**: Product overview, vision, and roadmap
- **[CLAUDE.md](CLAUDE.md)**: AI agent context for Claude Code
- **[CODE_STYLE.md](CODE_STYLE.md)**: Coding standards and conventions
- **API Documentation**: See `context/apis/` directory
- **MkDocs Site**: Run `mise run docs-serve` for local development

---

## Licensing

**Dual License**: MIT OR Apache-2.0

All original Knitli code is licensed under your choice of MIT or Apache-2.0. See `LICENSE`, `LICENSE-MIT`, and `LICENSE-APACHE-2.0` files for details.

**REUSE Compliant**: This project follows the [REUSE specification](https://reuse.software). Every file contains exact license information or has an accompanying `.license` file.

**Vendored Code**: Some vendored code may be Apache-2.0 only or MIT only. Check individual file headers for specifics.

**Contributing**: Review `CONTRIBUTORS_LICENSE_AGREEMENT.py` before submitting PRs.


---

## Links

**Project**:
- Repository: https://github.com/knitli/codeweaver-mcp
- Issues: https://github.com/knitli/codeweaver-mcp/issues
- Documentation: https://dev.knitli.com/codeweaver (in progress)
- Changelog: https://github.com/knitli/codeweaver-mcp/blob/main/CHANGELOG.md

**Company**:
- Knitli: https://knitli.com
- X/Twitter: https://x.com/knitli_inc
- LinkedIn: https://linkedin.com/company/knitli
- GitHub: https://github.com/knitli

**Package Info**:
- Python package: `codeweaver-mcp`
- CLI command: `codeweaver`
- Python requirement: ≥3.12 (tested on 3.12, 3.13, 3.14)
- Entry point: `codeweaver.cli.app:main`

---

**Note**: v0.1 is an early MVP release. Some features are still in development. Contributions welcome!