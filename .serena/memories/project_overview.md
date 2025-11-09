# CodeWeaver Project Overview

## Project Purpose
CodeWeaver is an extensible MCP (Model Context Protocol) server for semantic code search that delivers precise, token-efficient context to AI coding agents. It solves the fundamental context delivery problem where AI agents get overwhelmed with irrelevant code.

**Core Mission**: AI-first context delivery - enhance AI agent understanding of code through precise context delivery

**Key Value Propositions**:
- 60-80% reduction in context bloat and token costs
- Single `find_code` tool interface (vs 5-20+ tools in other MCP servers)
- Hybrid search (text + semantic embeddings + AST analysis)
- Platform extensibility (10+ embedding providers, multiple vector stores)
- 26 languages with full AST support, 170+ with heuristic chunking

## Current Status
**Version**: v0.1 Alpha Release - Early development phase

**What Works (v0.1)**:
- Core hybrid search (dense + sparse vectors)
- Semantic reranking with voyage-rerank-2.5
- CLI and MCP server interfaces
- Auto-indexing on server startup
- Health monitoring endpoint
- Circuit breaker resilience for external APIs
- Error recovery and graceful degradation
- Checkpoint/resume for interrupted indexing

**In Progress (v0.2)**:
- Real-time file watching (FileWatcher exists but not fully wired)
- Agent-driven intent analysis (pydantic-ai integration)
- Search result explanations
- Comprehensive test coverage

## Tech Stack

### Core Technologies
- **Python**: >=3.12 (currently using 3.13)
- **MCP Framework**: FastMCP 2.13.0.2+
- **Data Validation**: pydantic 2.12.4+, pydantic-settings, pydantic-ai, pydantic-graph
- **CLI Framework**: cyclopts 4.2.1+
- **Code Analysis**: ast-grep-py 0.39.7+
- **Vector Database**: qdrant-client 1.15.1+
- **Embeddings**: voyageai 0.3.5+ (primary), fastembed 0.7.3+ (local fallback)
- **File Discovery**: rignore 0.7.6 (gitignore support)
- **Utilities**: rich, tenacity, httpx, uvicorn

### Development Tools
- **Package Manager**: uv (replaces pip/poetry)
- **Environment Manager**: mise (replaces pyenv/nvm)
- **Linter/Formatter**: ruff
- **Type Checker**: ty (pyright-based)
- **Testing**: pytest with extensive markers
- **Documentation**: mkdocs with material theme

## Project Structure

```
src/codeweaver/
├── __init__.py           # Package root
├── main.py               # Application entry point
├── exceptions.py         # Custom exception definitions
├── _version.py           # Version information
├── agent_api/            # MCP agent interface
├── cli/                  # CLI commands (server, search, config)
├── common/               # Shared utilities and helpers
├── config/               # Configuration management
├── core/                 # Core types and abstractions
├── engine/               # Indexing and search engine
├── middleware/           # FastMCP middleware components
├── providers/            # Pluggable provider implementations
├── semantic/             # AST and semantic analysis
├── server/               # MCP server implementation
└── tokenizers/           # Token counting utilities
```

## Architecture Principles (from Constitution v2.0.1)

1. **AI-First Context**: Design with AI consumption as primary interface
2. **Proven Patterns**: Leverage pydantic ecosystem (FastAPI patterns)
3. **Evidence-Based Development**: All decisions backed by verifiable evidence (NON-NEGOTIABLE)
4. **Testing Philosophy**: Effectiveness over coverage - focus on user-affecting behavior
5. **Simplicity Through Architecture**: Flat structure, obvious purpose, avoid deep nesting
