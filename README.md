<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->
# CodeWeaver

Extensible context platform and MCP server for hybrid semantic code search and targeted context delivery to AI coding agents.

## Architectural Goals

1. **Provide semantically-rich, ranked and prioritized search results for developers and their coding agents.**
   
  **How**
  - CodeWeaver uses ast-grep, and support for dozens of embedding and reranking models, local and remote, to provide weighted responses to searches.
  - CodeWeaver is fully pluggable. You can add embedding providers, reranking providers, agent providers, services and middleware, and *new data sources* beyond your codebase.

2. **Eliminate 'cognitive load' on coding agents trying to get context on the codebase.**

  **How**
  - **Reduces all operations to a single simple tool** -- `find_code` -- allowing your coding agent to request what it needs, explain what it's trying to do, and get exactly the information it needs in response.
  - Uses **mcp sampling** to search and curate context for your coding agent -- using your coding agent! (also supports this outside of an MCP context where sampling isn't enabled or MCP is not available). CodeWeaver uses a *different instance* of your agent to evaluate your agent's needs and curate a response, keeping your agent unburdened with all the associated context from searching.

3. **Significantly cut context bloat, and costs**. This also helps keep agents razor focused on their tasks.

  **How**
  - CodeWeaver aims to *restrict* context to your coding agent to *only the information it needs*. Of course, that's not easy to do, but we hope to get close.
  - By reducing the context that's returned to your Agent, your Agent no longer has to "carry" all of that extra, unused, context with them -- reducing token use *with every turn* and reducing its exponential growth.

## Overview

CodeWeaver is more than an MCP server—it’s a context platform. It distills and delivers targeted, token-efficient context to your AI coding agent. Under the hood, it functions like RAG + hybrid search over semantically indexed code, and it can integrate arbitrary data sources (e.g., external API docs) through a provider architecture.

Status: Pre-release. Core architecture is in place; several integrations are still being tied together (see “Project status” and “Roadmap” below).


Contents
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
- Precise span-based code intelligence
  - Span and SpanGroup types for exact line/column tracking
  - Immutable set operations (union, intersection, difference) over spans
  - Rich semantic metadata (AST-aware) for better chunking and assembly
- Hybrid search foundation
  - Text and semantic search with unified ranking (architecture complete; semantic pipeline integration WIP)
  - Advanced, production-ready filtering (vendored search filters with pydantic-based validation)
- Provider architecture
  - Pluggable embedding, rerank, agent, vector store, and data source providers
  - Multi-provider capability matrix (dynamic selection and inference)
- pydantic-ai deep integration
  - Agent-capable providers for intent analysis, query rewriting, and context planning
  - Type-safe configuration and structured results
- CLI and MCP server
  - codeweaver server to run as an MCP server
  - codeweaver search for local interactive search with multiple output formats (json, table, markdown)
  - codeweaver config for configuration management and validation
- Designed for background indexing and live updates (file watching implemented with `watchfiles`)
- Strong foundation for performance and observability (robust statistics implementation, telemetry scaffolded)



Quickstart

Requirements
- Python 3.12+ (tested primarily on 3.12)
- Optional: Qdrant for vector storage (in progress), API keys for cloud providers if you choose them

Install
Pick one of the extras that fits your environment:

- Recommended (cloud-capable; includes telemetry)
  uv pip install "codeweaver-mcp[recommended]"

- Recommended without telemetry
  uv pip install "codeweaver-mcp[recommended-no-telemetry]"

- Local-only (no cloud calls; CPU embeddings via fastembed)
  uv pip install "codeweaver-mcp[recommended-local-only]"

A-la-carte (advanced)
You need:
- required-core
- at least one agent-capable provider (e.g., provider-openai or provider-anthropic)
- at least one embedding-capable provider (e.g., provider-voyageai or provider-fastembed)
- at least one vector store (provider-qdrant or provider-in-memory)

Example:
uv pip install "codeweaver-mcp[required-core,cli,provider-openai,provider-qdrant,source-filesystem]"

Run the server
codeweaver server
- Starts the MCP server with FastMCP.
- Use --help to see options.

Run a search locally
codeweaver search "how do we configure providers?"
- Use --format json|table|markdown
- Use --help to explore options.

Configure
codeweaver config --help
- Centralized config powered by pydantic-settings (multi-source).
- Supports selecting providers and setting provider-specific options (e.g., API keys when applicable).



CLI overview

The CLI includes:
- Server: codeweaver server
  - Runs the MCP server with proper lifespan and application state management (integration in progress where noted).
- Search: codeweaver search "query" [--format {json|table|markdown}]
  - Runs a local search pipeline using the span-based assembly and available providers.
- Config: codeweaver config …
  - Manages settings, validates configuration, and helps you choose providers.

Use --help on any subcommand for full options.



Concepts and architecture

Span-based core
- Spans precisely represent code locations (line/column), and SpanGroups allow composition.
- Immutable, set-like operations enable accurate merging of results across passes (text, semantic, AST).
- CodeChunk and CodeMatch carry spans and metadata, enabling token-aware, context-safe assembly.

Semantic metadata
- ExtKind enumerates language and chunk types.
- SemanticMetadata tracks AST nodes and classifications to improve chunk boundaries and ranking.

Provider ecosystem
- Embedding providers: VoyageAI, fastembed, sentence-transformers, etc.
- Rerank providers: cohere, bedrock (via pydantic-ai-slim integrations).
- Agent providers: major cloud LLMs via pydantic-ai-slim (OpenAI, Anthropic, Google, Mistral, Groq, Hugging Face, Bedrock, etc.).
- Vector stores: in-memory (basic), Qdrant (in progress for span-aware indexing).
- Data sources: filesystem (with planned file watching), Tavily, DuckDuckGo.

Advanced filtering (vendored)
- Rich, validated filters for keyword, numeric, range, boolean, etc.
- Dynamic tool signature generation via decorator-based wrappers.
- Designed to be vendor-agnostic.

Configuration and settings
- Multi-source configuration via pydantic-settings.
- Capability-based provider selection and dynamic instantiation (registry completing).
- Token budgeting and caching strategies planned.



Providers and optional extras

Top-level extras (convenience)
- recommended: end-to-end features with cloud support
- recommended-no-telemetry: same as above without telemetry
- recommended-local-only: local embeddings (fastembed), no cloud calls

A-la-carte extras (compose what you need)
- required-core: the minimal core of CodeWeaver
- cli: CLI niceties (rich, cyclopts)
- pre-context: components used for pre-context and watching
- Agent-only providers: provider-anthropic, provider-groq
- Agent + embeddings providers: provider-openai, provider-google, provider-huggingface, provider-mistral
- Embedding + rerank + agent: provider-bedrock, provider-cohere
- Embedding-only: provider-fastembed, provider-sentence-transformers (CPU/GPU variants), provider-voyageai
- Vector stores: provider-in-memory, provider-qdrant
- Data sources: source-filesystem, source-tavily, source-duckduckgo

See pyproject.toml for exact versions and groups.



Current tool surface (MCP + CLI)

MCP server
- Primary tool: find_code (being integrated)
  - Query: natural language
  - Filters (planned defaults):
    - language: keyword (any)
    - file_type: keyword (code, docs, config)
    - created_after: numeric timestamp (>=)
  - Output: span-based code matches with execution metadata
- Additional tool surfaces will evolve as pipelines and strategies are implemented.

CLI search
- codeweaver search "your query" --format table
- Uses the same underlying discovery and assembly model, outputting structured results.



Project status (what works vs. WIP)

What’s built
- Strong span-based type system and semantic metadata
- Sophisticated data models: DiscoveredFile, CodeChunk, CodeMatch
- Deep pydantic-ai provider integration
- Capability-based provider selection scaffolding
- CLI (server, search, config) with rich output and robust error handling
- Vendored filtering system that’s production-ready and provider-agnostic

What’s ~97% complete
- Embedding, reranking, and agentic capabilities (provider integrations and orchestration)
- Agent handling is implemented but needs to be tied fully into the pipelines

What’s in progress / planned
- Provider registry (_registry.py) and final glue code
- FastMCP middleware and application state management
- Vector stores: Qdrant implementation (span-aware); in-memory baseline
- File discovery + indexing: rignore-based discovery; background indexing with watchfiles
- Pipelines and strategies: orchestration via pydantic-graph
- Hybrid search with unified ranking across signals
- Query intent analysis via agents
- Performance, caching, and comprehensive test coverage
- Authentication and authorization middleware



Roadmap

Phase 1: Core integration
- Complete provider registry and statistics integration
- Finalize FastMCP application state and context handling
- Deliver working find_code over text search with filter integration
- Basic tests for core workflows

Phase 2: Semantic search
- Integrate embeddings (VoyageAI, fastembed) and Qdrant vector store
- AST-aware chunking and span-aware indexing
- Background indexing (watchfiles) and incremental updates
- Hybrid search with unified ranking and intent analysis

Phase 3: Advanced capabilities
- pydantic-graph pipelines and multi-stage workflows
- Multi-signal ranking (semantic, syntactic, keyword)
- Performance optimization and caching
- Enhanced metadata leverage, comprehensive testing, telemetry/monitoring



Development

Clone and install (full dev environment)
- uv pip install "codeweaver-mcp[all-dev]"

Linters and type checking
- Ruff and Pyright are configured (strict mode for src/codeweaver/**)

Tests
- Pytest config is included with markers for unit, integration, e2e, and provider-specific tests
- Coverage thresholds are configured (with cov-fail-under)

Local run
- codeweaver server
- codeweaver search "query"

Contribution notes
- Dual-licensed repository (MIT OR Apache-2.0)
- A contributors agreement is included; please review CONTRIBUTORS_LICENSE_AGREEMENT.py
- Issues and PRs welcome—especially for providers, vector stores, pipelines, and indexing (or anything else)

VS Code terminal: auto-activate .venv (first terminal too)

This workspace makes the very first integrated terminal auto-activate the repo `.venv` and lets you run extra commands.

How it works:
- `.vscode/settings.json` sets `ZDOTDIR` to `.vscode/zsh`, so zsh loads the workspace-local `.zshrc`.
- `.vscode/zsh/.zshrc` sources `scripts/dev-shell-init.zsh` (idempotent), which activates `.venv` and optionally sources `.vscode/terminal.extra.zsh` if present.
- Create `.vscode/terminal.extra.zsh` (see `.vscode/terminal.extra.zsh.example`) for your own exports/aliases and startup commands. This file is gitignored.

Notes:
- If `.venv` is missing, you'll see a hint. Create it with: `uv venv && uv sync`.
- We disable automatic terminal activation from the Python extension to avoid double activation.
- To opt out for a single terminal: `unset ZDOTDIR` before launching a new zsh.

Telemetry and auth middleware

Telemetry
- PostHog integration is available in recommended extras (we take great care to avoid capturing identifying or proprietary data -- we will only use this telemetry for improving CodeWeaver). If you're unsure, please look at our implementation for yourself so you can see what we collect.
- Use recommended-no-telemetry to exclude telemetry from install

Auth middleware (optional)
- Permit.io (permit-fastmcp), Eunomia (eunomia-mcp), and AuthKit integrations are scaffolded through FastMCP
- Enablement is controlled via environment variables when using those middlewares (see comments in pyproject.toml)

Licensing

All original Knitli code licensed under MIT OR Apache-2.0. See LICENSE, LICENSE-MIT, and LICENSE-APACHE-2.0. Some vendored code is Apache-2.0 only or MIT only. 

This project follows the [`REUSE`](https://reuse.software) specification. *Every file contains exact license information or has an accompanying `.license` file*.


Links

- Repository: https://github.com/knitli/codeweaver-mcp
- Issues: https://github.com/knitli/codeweaver-mcp/issues
- Documentation (in progress): https://dev.knitli.com/codeweaver
- Changelog: https://github.com/knitli/codeweaver-mcp/blob/main/CHANGELOG.md

- Knitli: https://knitli.com
- X: https://x.com/knitli_inc
- LinkedIn: https://linkedin.com/company/knitli
- Github: https://github.com/knitli

Notes
- Python package name: codeweaver-mcp
- CLI entry point: codeweaver (module: codeweaver.cli.app:main)
- Requires Python >= 3.11 (classifiers include 3.12–3.14)
