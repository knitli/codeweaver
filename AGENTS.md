<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code), Github Copilot, Roo, and other AI agents when working with code in this repository.

## Project Overview

CodeWeaver is an extensible MCP (Model Context Protocol) server for semantic code search. It provides intelligent codebase context discovery through a single `find_code` tool interface, supporting multiple embedding providers, vector databases, and data sources through a plugin architecture.

**Architecture**: CodeWeaver runs as a daemon with separate transport servers:
- **Daemon**: Background services (indexing, file watching, health monitoring)
- **Management Server**: HTTP endpoints at port 9329 (health, status, metrics)
- **MCP HTTP Server**: FastMCP at port 9328 for HTTP clients
- **MCP stdio**: Lightweight proxy that forwards to the HTTP backend (default transport)

**Current Status**: Early release (0.x). Most core features complete and relatively stable. Advanced functionality planned in several epics.

> [!IMPORTANT]
> Because it is an MCP server, you can use CodeWeaver while assisting with CodeWeaver development!
> In your list of available tools, you may see `find_code` or `codeweaver__find_code`
> Congrats! You're both an early tester and contributor!

## Project Constitution (DEFINITIVE GUIDANCE)

**This project is governed by the CodeWeaver Constitution at `.specify/memory/constitution.md`.** (path relative to repo root)

All development decisions, code reviews, and technical choices MUST comply with the constitutional principles. When in doubt, consult the constitution first.

### Constitutional Requirements Summary

1. **AI-First Context**: Enhance AI agent understanding of code through precise context delivery
2. **Proven Patterns**: Use FastAPI/pydantic ecosystem patterns over reinvention
3. **Evidence-Based Development (NON-NEGOTIABLE)**: All decisions backed by verifiable evidence
4. **Testing Philosophy**: Effectiveness over coverage - focus on user-affecting behavior, likely user stories and usage
5. **Simplicity Through Architecture**: Clear, flat structure with obvious purpose

**Full Constitutional Text**: See `.specify/memory/constitution.md` v2.0.1

## Development Commands

### Environment Setup
```bash
# Set up development environment
mise run setup

# Install dependencies
mise run sync

# Activate environment
mise run activate
```

### Code Quality
```bash
# Fix code issues (imports, formatting, linting)
mise run fix-python

# Run linting checks
mise run lint

# Format code
mise run format-fix

# Check code quality (includes type checking)
mise run check
```

> NOTE: This project uses the [`ty` typechecker](https://astral.sh/ty). `ty: ignore[some_rule]` statements are *not* typos

### Testing
```bash
# Run tests
mise run test

# Run with coverage
mise run test --cov

# Run specific test profile
mise run test --profile fast        # Fast unit tests
mise run test --profile integration # Integration tests
mise run test --profile real        # Real provider tests

# Watch mode
mise run test-watch
```

### Build
```bash
# Build package
mise run build

# Clean build artifacts and cache files
mise run clean

# Full CI pipeline (nonfunctional on 4/6/2026)
mise run ci
```

## Architecture Overview

### Core Design Principles

**These principles derive from and must comply with the Project Constitution (.specify/memory/constitution.md):**

- **AI-First Context**: Deliver precise codebase context for agent requests
- **Pydantic Ecosystem Alignment**: Heavy use of `pydantic`, `pydantic-settings`, `pydantic-ai`, `FastMCP`
- **Single Tool Interface**: One `find_code` tool vs multiple endpoints
- **Pluggable Providers**: Extensible backends for embeddings and vector stores

### Project Structure
```
src/codeweaver/
├── cli/                 # Command-line interface
│   ├── __main__.py      # CLI entry point
│   ├── __init__.py
│   ├── dependencies.py  # CLI dependency injection
│   ├── utils.py         # CLI utilities
│   ├── ui/              # CLI/TUI UI management
│   │   ├── __init__.py
│   │   ├── error_handler.py  # Error filtering and display for UI
│   │   ├── interaction.py    # User interaction utilities
│   │   └── status_display.py # Main StatusDisplay class
│   └── commands/        # CLI command implementations
│       ├── __init__.py
│       ├── config.py    # Configuration management commands
│       ├── context.py   # Context exploration commands *scaffolding*
│       ├── doctor.py    # Health check and diagnostics
│       ├── index.py     # Indexing commands
│       ├── init.py      # Project initialization + service persistence
│       ├── ls.py        # List resources (models, providers, etc.)
│       ├── migrate.py   # Migration commands
│       ├── search.py    # Search command (wraps find_code)
│       ├── server.py    # MCP server management (stdio/HTTP transports)
│       ├── start.py     # Start daemon in background (or --foreground)
│       ├── status.py    # Status display commands
│       └── stop.py      # Stop the running daemon
│
├── core/                # Core domain models, business logic, and shared infrastructure
│   ├── __init__.py
│   ├── chunks.py        # Immutable CodeChunk model (principal data object in the codebase)
│   ├── constants.py     # Core constants
│   ├── discovery.py     # DiscoveredFile model (created from indexing and watch operations)
│   ├── exceptions.py    # Global exception definitions
│   ├── file_extensions.py # File extension mappings (150+ languages)
│   ├── language.py      # Language detection for AST-based semantic support (20+ languages)
│   ├── _logging.py      # Centralized logging configuration
│   ├── metadata.py      # Metadata models supporting `CodeChunk`
│   ├── repo.py          # Repository abstraction *scaffolding*
│   ├── secondary_languages.py # Script-generated literal types for all supported languages
│   ├── spans.py         # `Span` (immutable) and `SpanGroup` (mutable) for context-aware code span operations
│   ├── statistics.py    # Statistics collection and reporting
│   ├── stores.py        # Data store abstractions - `UUIDStore` for storage/caching and `BlakeStore` for deduplication
│   ├── ui_protocol.py   # UI protocol definitions
│   ├── config/          # Core configuration (pydantic-settings based)
│   │   ├── __init__.py
│   │   ├── core_settings.py  # Core settings definitions
│   │   ├── envs.py           # Environment variable definitions
│   │   ├── loader.py         # Configuration loading
│   │   ├── _logging.py       # Logging configuration
│   │   ├── settings_type.py  # Settings type definitions
│   │   ├── telemetry.py      # Telemetry configuration
│   │   └── types.py          # Configuration type definitions
│   ├── dependencies/    # Core dependency injection bindings
│   │   ├── __init__.py
│   │   ├── component_settings.py
│   │   ├── core_settings.py
│   │   ├── services.py
│   │   └── utils.py
│   ├── di/              # Dependency injection framework
│   │   ├── __init__.py
│   │   ├── container.py # DI container
│   │   ├── dependency.py # Dependency definitions
│   │   └── utils.py     # DI utilities -- defines `@dependency_provider` decorator used for registration
│   ├── telemetry/       # Usage tracking and analytics
│   │   ├── __init__.py
│   │   ├── client.py    # PostHog telemetry client
│   │   ├── events.py    # Event definitions and tracking
│   │   ├── _project.py  # Project telemetry config
│   │   └── utils.py     # Telemetry utilities
│   ├── types/           # Core type definitions for codebase
│   │   ├── __init__.py
│   │   ├── aliases.py   # NewType definitions for string types, other aliases
│   │   ├── dataclasses.py # `DataclassSerializationMixin` for dataclasses throughout the codebase
│   │   ├── delimiter.py # Delimiter type definitions
│   │   ├── dictview.py  # Serializable `DictView` type for readonly views of TypedDicts
│   │   ├── embeddings.py # Embedding type definitions
│   │   ├── enum.py      # `BaseEnum` and `BaseDataclassEnum` subclassed throughout codebase
│   │   ├── env.py       # Environment type definitions
│   │   ├── models.py    # `BasedModel`, `RootedRoot` pydantic models subclassed throughout codebase
│   │   ├── provider.py  # `Provider` and `ProviderCategory` enums
│   │   ├── search.py    # Search type definitions
│   │   ├── sentinel.py  # Base `Sentinel` type with serialization support - `Unset` & `Missing` sentinels
│   │   ├── service_cards.py # Service card type definitions for provider instantiation
│   │   ├── settings_model.py # Settings model (BaseSettings object subclassed by domain configs)
│   │   ├── statistics.py # Statistics type definitions for telemetry and reporting
│   │   └── utils.py     # Type utilities
│   └── utils/           # Common utility functions
│       ├── __init__.py
│       ├── checks.py    # Validation and checking utilities
│       ├── environment.py # Environment utilities
│       ├── filesystem.py # Filesystem utilities
│       ├── general.py   # General utilities
│       ├── generation.py # Generation utilities
│       ├── introspect.py # Reflection and introspection
│       ├── procs.py     # Process management utilities
│       └── text.py      # Text manipulation utilities
│
├── engine/              # Core indexing and search engine
│   ├── __init__.py
│   ├── dependencies.py  # Engine dependency injection
│   ├── chunker/         # Code chunking implementations
│   │   ├── __init__.py
│   │   ├── base.py      # Base chunker interface
│   │   ├── delimiter.py # Delimiter-based chunking (150+ languages)
│   │   ├── delimiter_model.py # Delimiter models
│   │   ├── exceptions.py # Chunker exceptions
│   │   ├── governance.py # Chunking governance and rules
│   │   ├── _logging.py  # Chunker-specific logging
│   │   ├── parallel.py  # Parallel chunking
│   │   ├── registry.py  # Chunker registry
│   │   ├── selector.py  # Chunker selection logic
│   │   ├── semantic.py  # Semantic/AST-based chunking
│   │   └── delimiters/  # Delimiter definitions for delimiter-based chunker
│   │       ├── __init__.py
│   │       ├── custom.py    # Custom delimiter patterns
│   │       ├── families.py  # Delimiter families by language
│   │       └── patterns.py  # Delimiter pattern definitions
│   ├── config/          # Engine configuration
│   │   ├── __init__.py
│   │   ├── chunker.py       # Chunker configuration
│   │   ├── failover.py      # Failover configuration
│   │   ├── failover_detector.py # Failover detection config
│   │   ├── indexer.py       # Indexer configuration
│   │   └── root_settings.py # Engine root settings
│   ├── managers/        # Engine state managers
│   │   ├── __init__.py
│   │   ├── checkpoint_manager.py # Indexing checkpoint management
│   │   ├── manifest_manager.py   # Index manifest for state between sessions
│   │   └── progress_tracker.py   # Progress tracking
│   ├── services/        # Engine services
│   │   ├── __init__.py
│   │   ├── chunking_service.py      # Chunking service coordination
│   │   ├── config_analyzer.py       # Configuration analysis
│   │   ├── failover_service.py      # Failover handling
│   │   ├── indexing_service.py      # Main indexing implementation
│   │   ├── migration_service.py     # Migration service
│   │   ├── reconciliation_service.py # Data reconciliation
│   │   ├── snapshot_service.py      # Snapshot management
│   │   └── watching_service.py      # File system watcher service
│   └── watcher/         # File system watching for incremental indexing
│       ├── __init__.py
│       ├── _logging.py       # Watcher-specific logging
│       ├── progress.py       # Watch progress tracking
│       ├── types.py          # Watcher type definitions
│       └── watch_filters.py  # File filtering, primarily `IgnoreFilter` (wraps `rignore`)
│
├── providers/           # Provider implementations for embeddings, vector stores, reranking, agents, data sources
│   ├── __init__.py
│   ├── exceptions.py    # Provider exceptions
│   ├── http_pool.py     # HTTP connection pooling
│   ├── optimize.py      # Optimization utilities for sentence-transformers and fastembed
│   ├── agent/           # Agent providers (Context Agent, etc.) -- wraps `pydantic-ai`
│   │   ├── __init__.py
│   │   ├── capabilities.py # Agent capability definitions
│   │   ├── providers.py    # Agent provider implementations
│   │   └── resolver.py     # Agent provider resolution
│   ├── config/          # Provider configuration (pydantic-settings based)
│   │   ├── __init__.py
│   │   ├── backup_models.py  # Backup configuration models
│   │   ├── profiles.py       # Configuration profiles
│   │   ├── providers.py      # Provider configuration
│   │   ├── root_settings.py  # Provider root settings
│   │   ├── types.py          # Provider config types
│   │   ├── categories/       # Per-category provider configuration
│   │   │   └── (agent, embedding, reranking, vector_store, data, sparse_embedding, etc.)
│   │   ├── clients/          # Provider client configuration
│   │   │   └── (agent, vector_store, data, multi, etc.)
│   │   └── sdk/              # SDK-specific provider configuration
│   │       └── (agent, embedding, reranking, vector_store, data, sparse_embedding)
│   ├── data/            # Data source providers
│   │   ├── __init__.py
│   │   ├── duckduckgo.py # DuckDuckGo search provider
│   │   ├── exa.py        # Exa search provider
│   │   ├── providers.py  # Data provider registry
│   │   ├── tavily.py     # Tavily search provider
│   │   └── utils.py      # Data provider utilities
│   ├── dependencies/    # Provider dependency injection
│   │   ├── __init__.py
│   │   ├── capabilities.py # Provider capability definitions/constants
│   │   ├── config.py       # Provider DI config
│   │   ├── providers.py    # Provider DI registration
│   │   └── services.py     # Provider DI services
│   ├── embedding/       # Embedding providers
│   │   ├── __init__.py
│   │   ├── cache_manager.py      # Embedding cache management
│   │   ├── fastembed_extensions.py # FastEmbed extensions
│   │   ├── registry.py           # Embedding results registry (temporary store/backup)
│   │   ├── capabilities/         # Model capability definitions by creator (20+ providers)
│   │   │   └── (alibaba_nlp, amazon, baai, cohere, google, ibm_granite, intfloat,
│   │   │       jinaai, minishlab, mistral, mixedbread_ai, morph, nomic_ai, openai,
│   │   │       qwen, sentence_transformers, snowflake, thenlper, voyage, whereisai, etc.)
│   │   └── providers/            # Provider implementations by client interface
│   │       └── (base, bedrock, cohere, fastembed, google, huggingface,
│   │           litellm, mistral, openai_factory, sentence_transformers, voyage)
│   ├── env_registry/    # Environment-based provider registry
│   │   ├── __init__.py
│   │   ├── builders.py      # Registry builders
│   │   ├── conversion.py    # Registry conversion
│   │   ├── models.py        # Registry models
│   │   ├── registry.py      # Registry implementation
│   │   └── definitions/     # Provider definitions
│   │       └── (cloud_platforms, openai_compatible, specialized)
│   ├── reranking/       # Reranking providers
│   │   ├── __init__.py
│   │   ├── capabilities/    # Reranker model capabilities by creator
│   │   │   └── (alibaba_nlp, amazon, baai, cohere, jinaai, mixed_bread_ai,
│   │   │       ms_marco, qwen, voyage, etc.)
│   │   └── providers/       # Provider implementations
│   │       └── (base, bedrock, cohere, fastembed, sentence_transformers, voyage, types)
│   ├── types/           # Provider type definitions
│   │   ├── __init__.py
│   │   ├── circuit_breaker.py # Circuit breaker types
│   │   ├── embedding.py      # Embedding types
│   │   ├── resolvers.py      # Provider resolver types
│   │   ├── search.py         # Search types
│   │   ├── vectors.py        # Vector types
│   │   └── vector_store.py   # Vector store types
│   └── vector_stores/   # Vector database providers
│       ├── __init__.py
│       ├── base.py          # Base vector store interface
│       ├── inmemory.py      # In-memory vector store (qdrant_client w/ RocksDB persistence)
│       ├── qdrant_base.py   # Qdrant base class for shared inmemory/qdrant functions
│       ├── qdrant.py        # Qdrant vector database (local and cloud/remote)
│       ├── qdrant_service.py # Qdrant service layer
│       └── search/          # Search filtering and matching
│           ├── __init__.py
│           ├── condition.py      # Search condition builders
│           ├── filter_factory.py # Filter creation
│           ├── geo.py            # Geospatial filters
│           ├── match.py          # Match filters
│           ├── payload.py        # Payload filtering
│           ├── range.py          # Range filters
│           └── wrap_filters.py   # Filter wrappers
│
├── semantic/            # Semantic grammar characterization and normalization
│   ├── __init__.py
│   ├── ast_grep.py      # AST-grep integration
│   ├── classifications.py # Code classification definitions
│   ├── classifier.py    # Code classifier implementation
│   ├── dependencies.py  # Semantic dependency injection
│   ├── grammar.py       # Grammar definitions for semantic analysis
│   ├── node_type_parser.py # AST node-type.json parsing
│   ├── registry.py      # Node characterization and classifications by language
│   ├── scoring.py       # Semantic scoring (node, purpose and objective layered weighting)
│   ├── token_patterns.py # Token pattern matching for cross-language token identification
│   ├── types.py         # Semantic analysis types
│   └── data/            # Semantic data files
│       ├── classifications/ # Classification definitions (with overrides/)
│       └── node_types/      # AST node type definitions
│
├── server/              # Server implementations
│   ├── __init__.py
│   ├── _assets.py       # Server asset management
│   ├── background_services.py # Background service coordination
│   ├── dependencies.py  # Server dependency injection
│   ├── lifespan.py      # Server lifespan management
│   ├── _logging.py      # Server-specific logging
│   ├── management.py    # Management server (Starlette, port 9329)
│   ├── server.py        # Main server entry point
│   ├── agent_api/       # Tool interfaces and implementations for agents
│   │   ├── __init__.py
│   │   └── search/      # Primary `find_code` tool - exposed to User Agent and CLI
│   │       ├── __init__.py    # Tool interface and entry point
│   │       ├── conversion.py  # Convert between result/response objects and API CodeMatch
│   │       ├── filters.py     # Search filtering logic
│   │       ├── intent.py      # Query intent classification
│   │       ├── pipeline.py    # Search execution pipeline
│   │       ├── response.py    # Response formatting and assembly
│   │       ├── scoring.py     # Result scoring and relevance calculation
│   │       └── types.py       # Type definitions for find_code API
│   ├── config/          # Server configuration
│   │   ├── __init__.py
│   │   ├── helpers.py        # Configuration helpers
│   │   ├── mcp.py            # MCP server configuration
│   │   ├── middleware.py     # Middleware configuration
│   │   ├── server_defaults.py # Server default settings
│   │   ├── settings.py       # Main server settings
│   │   └── types.py          # Server config types
│   ├── health/          # Health check system
│   │   ├── __init__.py
│   │   ├── endpoint.py       # Health check endpoint
│   │   ├── health_service.py # Health check service
│   │   └── models.py         # Health check data models
│   └── mcp/             # MCP protocol implementation
│       ├── __init__.py
│       ├── server.py         # MCP server (FastMCP, port 9328)
│       ├── state.py          # MCP state management
│       ├── tools.py          # MCP tool definitions
│       ├── types.py          # MCP type definitions
│       ├── user_agent.py     # User agent interface
│       └── middleware/       # FastMCP middleware
│           ├── __init__.py
│           ├── fastmcp.py    # FastMCP middleware integration
│           └── statistics.py # Statistics middleware (times MCP request/response)
│
├── __init__.py          # Package root
├── _version.py          # Version information (generated)
├── main.py              # Application entry point
└── py.typed             # PEP 561 marker for type checking
```

### Key Dependencies
- **FastMCP**: MCP server framework
- **ast-grep-py**: Semantic code analysis
- **qdrant-client**: Vector database
- **voyageai**: Code embeddings (primary provider)
- **rignore**: File discovery with gitignore support
- **cyclopts**: CLI framework

### Missing Components (Implementation Needed)
- Agent integration
- Pipeline orchestration with pydantic-graph
- Testing strong but has big gaps in places

## Code Style Guidelines

**PRIMARY**: Follow the Project Constitution at `.specify/memory/constitution.md` for all architectural and development decisions.

### Follow CODE_STYLE.md Principles
- **Line length**: 100 characters
- **Docstrings**: Google convention, active voice, start with verbs
- **Type hints**: Modern Python ≥3.12 syntax (`int | str`, `typing.Self`)
- **Models**: Prefer `pydantic.BaseModel` with `frozen=True` for immutable data. Subclass codebase's types.
- **Lazy evaluation and immutables**: Use generators, tuples, frozensets, DictView/MappingProxyType when appropriate

### Architecture Patterns
- **Flat Structure**: Avoid deep nesting, group related modules in packages
- **Dependency Injection**: Custom type-safe system mostly based on FastAPI with important differences and improvements
- **Provider Pattern**: Abstract base classes for pluggable backends
- **Graceful Degradation**: AST → text fallback, AI → NLP → rule-based fallback

### Typing Requirements
- **Strict typing** with opinionated `ty` rules
- Use `TypedDict`, `Protocol`, `NamedTuple`, `enum.Enum` for structured data
- Prefer domain-specific dataclasses/BaseModels (`BasedModel`) over `dict[str, Any]`
- Define proper generic types using `ParamSpec`/`Concatenate`
- Generics defined with parameterized types; don't use `Generic`
- type aliases defined with `type` keyword

## Testing Approach

**Philosophy**: Effectiveness over coverage. Focus on critical behavior affecting user experience.

### Test Categories (via pytest markers)
- **unit**: Individual component tests
- **integration**: Component interaction tests
- **e2e**: End-to-end workflow tests
- **benchmark**: Performance tests
- **network/external_api**: Tests requiring external services
- **async_test**: Asynchronous test cases

Apply relevant pytest markers to new tests (see pyproject.toml for full list).

## Implementation Priorities

### Phase 1: Core Infrastructure  ✅ **complete**
1. Implement CLI entry point (`src/codeweaver/cli/__main__.py`)
2. Create main FastMCP server with `find_code` tool
3. Build provider abstractions and concrete implementations
4. Add basic pipeline orchestration

### Phase 2: Core Functionality  ✅ **complete**
5. Implement background indexing with watchfiles
6. Add comprehensive error handling and graceful degradation
7. Integrate telemetry and observability
8. Build comprehensive test suite

### Phase 3: Advanced Orchestration ❌ **Planned for Next Two Minor Releases**
9. Integrate agentic handling of query response (Context agent and Context agent API)
10. Add Context agent tools
11. Pluggable pipeline orchestration with `pydantic-graph`
12. Pipeline/response evaluation and validation with `pydantic-eval`
13. Expanded testing
14. ~~Replace registry system with dependency injection pattern~~ ✅ **complete** (DI refactor shipped)

### Key Implementation Notes
- **pypi package name is `code-weaver`** (naming collision).
- Entry point in pyproject.toml: `codeweaver = "codeweaver.cli.__main__:main"`
- Main tool interface: `find_code(query: str, intent: IntentType | None = None, ...)`
- Provider system: Abstract `EmbeddingProvider`, `SparseEmbeddingProvider`, `RerankingProvider` and `VectorStoreProvider` classes
- Settings: Unified hierarchical config via `pydantic-settings` with env vars and TOML files and cloud secret integration (pydantic settings handles all the heavy lifting here)

## Documentation
- Specifications, tasks, and associated files in `specs`
- `docs-site/` Astro/Starlight based documentation at <docs.knitli.com/codeweaver>
- Use `mise run dev` for local documentation development (nonfunctional on 4/6/2026)

## Instructions

**CONSTITUTIONAL COMPLIANCE REQUIRED**: Before any development work, validate your approach against the Project Constitution at `.specify/memory/constitution.md`. This constitution supersedes all other guidance.

If your task involves writing or editing code in the codebase, you must:

1. **First**: Ensure compliance with the [Project Constitution](.specify/memory/constitution.md)
2. **Second**: Read and follow [CODE_STYLE.md](CODE_STYLE.md)


The constitution contains non-negotiable principles that govern all technical decisions in this project.

## Context Management

CodeWeaver is a large codebase. Manage your token usage effectively:

### Best Practices
- Load only necessary files/sections using targeted searches
- For large-scale tasks: delegate to other agents or write automation scripts
- Use scripts for repetitive changes (linting fixes, import updates)

### Avoid
- Commands that dump large outputs unless writing to files (then search files, don't read directly)
- Tools without output limiting - always apply filters

### Strategy
Delegate high-context tasks with detailed instructions. Focus on high-level coordination while tools handle details. Execute tasks using multiple agents working in parallel as much as possible.

## Core Rules

**Constitutional Rule**: All work must comply with the Project Constitution (`.specify/memory/constitution.md`). Constitutional violations are never acceptable.

**Golden Rule**: Do exactly what the user asks. No more, no less. If the user's request is not clear, ask questions.

**Evidence Rule**: Follow Constitutional Principle III - no workarounds, mock implementations, or placeholder code without explicit authorization.

### Red Flags 🚩

Stop and investigate when:

- API behavior differs from expectations
- Files/functions aren't where expected
- Code behavior contradicts documentation

### Red Flag Response Protocol

1. **Stop** current work
2. **Review** your understanding and plans
3. **Assess** using thinking, planning or todo-list tool:
   - Does approach comply with Project Constitution?
   - Is approach consistent with requirements?
   - Do you have sufficient information?
   - Is the task unclear? Could the user have meant something different?
   - Could user have made simple error (typo, path)?
   - Is documentation outdated?
   - Did context limits cut relevant details?
4. **Research**:
   - Test hypothesis if possible
   - Use task tool for agent research
   - Internal issues: search files for pattern changes
   - External APIs: use context7/tavily for version-specific info
   - If still unclear: ask user for clarification

### Never Do without Explicit User Approval

- **Violate constitutional principles** - Constitution compliance is non-negotiable
- Create workarounds (Constitutional Principle III)
- Write placeholder/mock/toy versions (Constitutional Principle III)
- Use NotImplementedError or TODO shortcuts (Constitutional Principle III)
- Change project or task scope/goals
- Ignore evidence-based development requirements

**Bottom line**: No code beats bad code (Constitutional Principle III - Evidence-Based Development).

### When Stuck

If you need more information or the task is larger/more complex than expected: **Ask the user for guidance**.

## Documentation

Priority order for documentation:

1. **Getting Started**: <5 minute install and first run
2. **Build & Configure**: Customization, extensions, platform development
3. **Contributors**: Contribution guidelines and internal documentation

## Brand Voice & Terminology

### Mission

Bridge the gap between human expectations and AI agent capabilities through "exquisite context." Create beneficial cycles where AI-first tools enhance both agent and human capabilities.

**Constitutional Alignment**: This mission directly implements Constitutional Principle I (AI-First Context).

### User Terms

- **Agent/AI Agent** (not "model", "LLM", "tool")

  - **Developer's Agent**: Focused on developer tasks
  - **Context Agent**: Internal agents delivering information to the developer or developer's agent

- **Developer/End User**: People using CodeWeaver

  - **Developer User**: Uses CodeWeaver as development tool
  - **Platform Developer**: Builds with/extends CodeWeaver

- **Us**: First person plural (not "Knitli" or "team")
- **Contributors**: External contributors when distinction needed, otherwise 'Us/We'

- **Tool**: Tools are specific functions or interfaces for AI Agent users. The `find_code` tool is the primary, and currently only, tool and API for the *Developer's Agent*. The *Context Agent* may have a small number of other specialty tools designed to improve, narrow, or assemble search results for the developer's agent.

### Core Values

- **Simplicity**: Transform complexity into clarity, eliminate jargon
- **Humanity**: Enhance human creativity, design people-first
- **Utility**: Solve real problems, meet users where they are
- **Integration**: Power through synthesis, connect disparate elements

### Personality

**We are**: Approachable, thoughtful, clear, empowering, purposeful

**We aren't**: Intimidating, unnecessarily complex, cold, AI-for-AI's-sake

### Communication Style

- Plain language accessible to all skill levels
- Simple examples with visual aids
- Conversational and human, not robotic
- Honest about capabilities and limitations
- Direct focus on user needs and goals

### Vision & Success Metrics

**Vision**: AI tools accessible to everyone, enhancing (not replacing) human creativity
**Success**: User empowerment, accessibility, reduced complexity, workflow integration

## Privacy and Telemetry

The default installation includes Posthog telemetry, enabled by default. The *only* purpose for this data collection is to improve CodeWeaver. We have a strong focus on privacy-first collection.

Practically speaking, data collection is handled through pydantic serialization. **All pydantic BaseModel (`BasedModel`) and dataclasses _must_ implement the `_telemetry_keys` method, which has this signature:

```python
from pathlib import Path
from typing import TYPE_CHECKING

from codeweaver.core.types.models import BasedModel

if TYPE_CHECKING:
    from codeweaver.core.types import FilteredKeyT, AnonymityConversion

class MyModel(BasedModel)

    identifying_info: str
    project_path: Path

    ...

    # if a class has fields that should be anonymized, those must be identified by this method
    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        # note the type is FilteredKeyT, the object, a NewType, is FilteredKey
        from codeweaver.core.types import FilteredKey, AnonymityConversion
        return {
          FilteredKey("identifying_info"): AnonymityConversion.FORBIDDEN, # returns None
          FilteredKey("project_path"): AnonymityConversion.HASH, # hashes the value
          # can also be one of BOOLEAN (present/not), COUNT, DISTRIBUTION, AGGREGATE, and TEXT_COUNT
        }

    # NOTE: For more complex handling, classes may additionally implement the `_telemetry_handler` method
    # See `codeweaver.core.types.models.BasedModel` for the API signature.

```

The Telemetry implementation calls the `serialize_for_telemetry` method on the principal class, which cascades similar calls down the nested data hierarchy. Each class is therefore only responsible for policing itself and any types it contains that aren't BasedModel or dataclass.
