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
mise run fix

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

# Full CI pipeline
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
├── agent_api/           # Tool interfaces and implementations for agents
│   ├── __init__.py      # Exported API for User Agent and Context Agent
│   └── find_code/       # Primary `find_code` tool - exposed to User Agent and CLI
│       ├── __init__.py           # Tool interface and entry point
│       ├── conversion.py         # Convert between result/response objects and API CodeMatch
│       ├── filters.py            # Search filtering logic
│       ├── intent.py             # Query intent classification
│       ├── pipeline.py           # Search execution pipeline
│       ├── response.py           # Response formatting and assembly
│       ├── results.py            # Result processing and ranking
│       ├── scoring.py            # Result scoring and relevance calculation
│       ├── types.py              # Type definitions for find_code API
│       ├── ARCHITECTURE.md       # Architecture documentation for find_code
│       └── README.md             # Usage guide
│
├── cli/                 # Command-line interface
│   ├── __main__.py      # CLI entry point
│   ├── __init__.py
│   ├── utils.py         # CLI utilities
│   └── ui/              # CLI/TUI UI management
        ├── __init__.py
        ├── status_display.py # main StatusDisplay class
        ├── error_handler.py # class to filter and display errors for the UI
│   └── commands/        # CLI command implementations
│       ├── __init__.py
│       ├── config.py    # Configuration management commands
│       ├── context.py   # Context exploration commands *scaffolding*
│       ├── doctor.py    # Health check and diagnostics
│       ├── index.py     # Indexing commands
│       ├── init.py      # Project initialization + service persistence
│       ├── list.py      # List resources (models, providers, etc.)
│       ├── search.py    # Search command (wraps find_code)
│       ├── server.py    # MCP server management (stdio/HTTP transports)
│       ├── start.py     # Start daemon in background (or --foreground)
│       └── stop.py      # Stop the running daemon
│
├── common/              # Shared utilities and infrastructure
│   ├── __init__.py
│   ├── logging.py       # Centralized logging configuration
│   ├── statistics.py    # Statistics collection and reporting
│   ├── types.py         # Common type definitions
│   ├── registry/        # Provider and component registry system
│   │   ├── __init__.py
│   │   ├── models.py    # Registry data models
│   │   ├── provider.py  # Provider registration
│   │   ├── services.py  # Registry services
│   │   ├── types.py     # Registry type definitions
│   │   └── utils.py     # Registry utilities
│   ├── telemetry/       # Usage tracking and analytics
│   │   ├── __init__.py
│   │   ├── client.py    # PostHog telemetry client
│   │   ├── events.py    # Event definitions and tracking
│   │   └── README.md
│   └── utils/           # Common utility functions
│       ├── __init__.py
│       ├── checks.py    # Validation and checking utilities
│       ├── git.py       # Git repository and file utilities
│       ├── introspect.py # Reflection and introspection
│       ├── lazy_importer.py # Lazy dependency and module loading
│       ├── normalize.py # Data normalization utilities
        ├── procs.py     # process management utilities
        ├── textify.py   # text manipulation utilities
│       └── utils.py     # General utilities
│
├── config/              # Configuration system (pydantic-settings based)
│   ├── __init__.py
│   ├── _project.py      # Project-specific configuration
│   ├── chunker.py       # Chunker configuration
│   ├── envs.py          # environment variable definitions
│   ├── indexer.py       # Indexer configuration
│   ├── logging.py       # Logging configuration
│   ├── mcp.py           # MCP server configuration (supports cli/commands/init.py)
│   ├── middleware.py    # Middleware configuration
│   ├── profiles.py      # Configuration profiles
│   ├── providers.py     # Provider configuration including default settings
│   ├── server_defaults.py # Server default settings
│   ├── settings.py      # Main settings class
│   ├── telemetry.py     # Telemetry configuration
│   └── types.py         # Configuration type definitions
│
├── core/                # Core domain models and business logic
│   ├── __init__.py
│   ├── chunks.py        # Immutable CodeChunk model and data structure (principal data object in the codebase)
│   ├── discovery.py     # DiscoveredFile model and data structure (created from indexing and watch operations)
│   ├── file_extensions.py # File extension mappings (150+ languages)
│   ├── language.py      # Language detection for AST-based semantic support (20+ languages)
│   ├── metadata.py      # Metadata models supporting `CodeChunk`
│   ├── repo.py          # Repository abstraction *scaffolding*
│   ├── secondary_languages.py # script-generated literal types for all supported languages
│   ├── spans.py         # `Span` (immutable) and `SpanGroup` (mutable) objects provide context-aware set-like operations for code spans and groups of code spans
│   ├── stores.py        # Data store abstractions - `UUIDStore` for storage/caching and `BladeStore` for deduplication
│   ├── utils.py         # utilities for core packages
│   └── types/           # Core type definitions for codebase
│       ├── __init__.py
│       ├── aliases.py   # Primarily newtype definitions for string types used across the codebase, other aliases
│       ├── dictview.py  # the serializable `DictView` type which is used for readonly views in the codebase, particularly of TypedDicts
│       ├── enum.py      # The `BaseEnum` and `BaseDataclassEnum` objects subclassed throughout the codebase.
│       ├── models.py    # `BasedModel`, `RootedRoot` pydantic models subclassed throughout codebase, and the `DataclassSerializationMixin`, which adapts dataclasses throughout the codebase
│       └── sentinel.py  # A base `Sentinel` type with serialization support
│
├── engine/              # Core indexing and search engine
│   ├── __init__.py
│   ├── chunking_service.py # Chunking service coordination
│   ├── chunker/         # Code chunking implementations
│   │   ├── __init__.py
│   │   ├── base.py      # Base chunker interface
│   │   ├── delimiter.py # Delimiter-based chunking (150+ languages)
│   │   ├── delimiter_model.py # Delimiter models
│   │   ├── exceptions.py # Chunker exceptions
│   │   ├── governance.py # Chunking governance and rules
│   │   ├── logging.py   # Chunker-specific logging
│   │   ├── parallel.py  # Parallel chunking
│   │   ├── registry.py  # Chunker registry
│   │   ├── selector.py  # Chunker selection logic
│   │   ├── semantic.py  # Semantic/AST-based chunking
│   │   └── delimiters/  # Delimiter definitions for delimiter-based chunker
│   │       ├── __init__.py
│   │       ├── custom.py # Custom delimiter patterns
│   │       ├── families.py # Delimiter families by language
│   │       ├── category.py   # Delimiter category classification
│   │       └── patterns.py # Delimiter pattern definitions
│   ├── indexer/         # Indexing engine
│   │   ├── __init__.py
│   │   ├── checkpoint.py # Indexing checkpoint management
│   │   ├── indexer.py   # Main indexer implementation
│   │   ├── manifest.py  # Index manifest management for state between sessions
│   │   └── progress.py  # Progress tracking
│   ├── search/          # Search filtering and matching **not integrated**
│   │   ├── __init__.py
│   │   ├── condition.py # Search condition builders
│   │   ├── filter_factory.py # Filter creation
│   │   ├── geo.py       # Geospatial filters (if applicable)
│   │   ├── match.py     # Match filters
│   │   ├── payload.py   # Payload filtering
│   │   ├── range.py     # Range filters
│   │   └── wrap_filters.py # Filter wrappers
│   └── watcher/         # File system watching for incremental indexing
│       ├── __init__.py
│       ├── logging.py   # Watcher-specific logging
│       ├── types.py     # Watcher type definitions
│       ├── watch_filters.py # File filtering for watching, primarily `IgnoreFilter`, which wraps `rignore`
│       └── watcher.py   # File system watcher implementation
│
├── middleware/          # FastMCP middleware components (legacy/minimal)
│   ├── __init__.py
│   └── statistics.py    # Statistics middleware (times MCP request/response)
│
├── providers/           # Provider implementations for embeddings, vector stores, reranking, agents, data sources.
│   ├── __init__.py
│   ├── capabilities.py  # Provider capability definitions/constants
│   ├── optimize.py      # optimization utilities for sentence-transformers and fastembed
│   ├── provider.py      # `Provider` and `ProviderCategory` enums
│   ├── types.py         # *general* provider type definitions
│   ├── agent/           # Agent providers (Context Agent, etc.) -- wraps `pydantic-ai`
│   │   ├── __init__.py
│   │   ├── agent_models.py # Re-exports pydantic-ai models
│   │   └── agent_providers.py # Re-exports pydantic-ai provider implementations
│   ├── data/            # Data providers, currently re-exports from `pydantic-ai`
│   │   └── __init__.py
│   ├── embedding/       # Embedding providers
│   │   ├── __init__.py
│   │   ├── fastembed_extensions.py # FastEmbed extensions (adds additional model support)
│   │   ├── registry.py  # Registry for *embedding results* -- a temporary store/backup
│   │   ├── types.py     # Embedding types for *embedding results*
│   │   ├── capabilities/ # Model capability definitions by model creator
│   │   │   ├── __init__.py
│   │   │   ├── alibaba_nlp.py
│   │   │   ├── amazon.py
│   │   │   ├── baai.py
│   │   │   ├── base.py
│   │   │   ├── cohere.py
│   │   │   ├── google.py
│   │   │   ├── ibm_granite.py
│   │   │   ├── intfloat.py
│   │   │   ├── jinaai.py
│   │   │   ├── mistral.py
│   │   │   ├── mixedbread_ai.py
│   │   │   ├── nomic_ai.py
│   │   │   ├── openai.py
│   │   │   ├── qwen.py
│   │   │   ├── sentence_transformers.py
│   │   │   ├── snowflake.py
│   │   │   ├── thenlper.py
│   │   │   ├── types.py
│   │   │   ├── voyage.py
│   │   │   └── whereisai.py
│   │   └── providers/   # Provider implementations by client interface
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── bedrock.py # AWS Bedrock
│   │       ├── cohere.py  # also includes Azure and Heroku cohere providers
│   │       ├── fastembed.py
│   │       ├── google.py
│   │       ├── huggingface.py
│   │       ├── litellm.py  **scaffolding**
│   │       ├── mistral.py
│   │       ├── openai_factory.py  # provider class *factory* for ~8 openai API-compatible providers
│   │       ├── sentence_transformers.py
│   │       └── voyage.py
│   ├── reranking/       # Reranking providers
│   │   ├── __init__.py
│   │   ├── capabilities/ # Reranker model capability definitions by model creator
│   │   │   ├── __init__.py
│   │   │   ├── alibaba_nlp.py
│   │   │   ├── amazon.py
│   │   │   ├── baai.py
│   │   │   ├── base.py
│   │   │   ├── cohere.py
│   │   │   ├── jinaai.py
│   │   │   ├── mixed_bread_ai.py
│   │   │   ├── ms_marco.py
│   │   │   ├── qwen.py
│   │   │   ├── types.py
│   │   │   └── voyage.py
│   │   └── providers/   # Provider implementations
│   │       ├── __init__.py
│   │       ├── base.py
│   │       ├── bedrock.py
│   │       ├── cohere.py  (cohere only)
│   │       ├── fastembed.py
│   │       ├── sentence_transformers.py
│   │       └── voyage.py
│   └── vector_stores/   # Vector database providers
│       ├── __init__.py
│       ├── base.py      # Base vector store interface
│       ├── inmemory.py  # In-memory vector store (qdrant_client w/ json persistence)
│       ├── metadata.py  # Vector metadata handling
│       ├── qdrant_base.py # Qdrant base class for all common function to inmemory and qdrant
│       ├── qdrant.py    # Qdrant vector database (local and cloud/remote)
│       └── utils.py     # Vector store utilities
│
├── semantic/            # Semantic Grammar characterization and normalization
│   ├── __init__.py
│   ├── ast_grep.py      # AST-grep integration
│   ├── classifications.py # Code classification definitions
│   ├── classifier.py    # Code classifier implementation
│   ├── grammar.py       # Grammar definitions for semantic analysis
│   ├── node_type_parser.py # AST node-type.json parsing
│   ├── registry.py      # Node characterization and classifications by language
│   ├── scoring.py       # Semantic scoring (node, purpose and objective layered weighting)
│   ├── token_patterns.py # Token pattern matching for cross-language token identification
│   └── types.py         # Semantic analysis types
│
├── server/              # Server implementations
│   ├── __init__.py
│   ├── app_bindings.py  # Application dependency bindings and http admin endpoints
│   ├── health_endpoint.py # Health check endpoint
│   ├── health_models.py # Health check data models
│   ├── health_service.py # Health check service
│   ├── management.py    # Management server (Starlette, port 9329)
│   ├── mcp_http.py      # MCP HTTP server (FastMCP, port 9328)
│   ├── server.py        # Main MCP server entry point
│   └── stdio_proxy.py   # stdio-to-HTTP proxy for MCP clients
│
├── tokenizers/          # Token counting for various models
│   ├── __init__.py
│   ├── base.py          # Base tokenizer interface
│   ├── tiktoken.py      # OpenAI tiktoken integration
│   └── tokenizers.py    # Tokenizers implementation (most models use this tokenizer)
│
├── __init__.py          # Package root
├── _version.py          # Version information
├── exceptions.py        # Global exception definitions
├── main.py              # Application entry point
└── py.typed             # PEP 561 marker for type checking
```

### Key Dependencies
- **FastMCP**: MCP server framework
- **ast-grep-py**: Semantic code analysis
- **qdrant-client**: Vector database
- **voyageai**: Code embeddings (primary provider)
- **rignore**: File discovery with gitignore support
- **cyclopts**: CLI framework (for future CLI implementation)

### Missing Components (Implementation Needed)
- Provider system (vector store)
- Pipeline orchestration with pydantic-graph
- Comprehensive testing framework

## Code Style Guidelines

**PRIMARY**: Follow the Project Constitution at `.specify/memory/constitution.md` for all architectural and development decisions.

### Follow CODE_STYLE.md Principles
- **Line length**: 100 characters
- **Docstrings**: Google convention, active voice, start with verbs
- **Type hints**: Modern Python ≥3.12 syntax (`int | str`, `typing.Self`)
- **Models**: Prefer `pydantic.BaseModel` with `frozen=True` for immutable data
- **Lazy evaluation and immutables**: Use generators, tuples, frozensets when appropriate

### Architecture Patterns
- **Flat Structure**: Avoid deep nesting, group related modules in packages
- **Dependency Injection**: FastMCP Context pattern for providers (think: FastAPI patterns if unfamiliar)
- **Provider Pattern**: Abstract base classes for pluggable backends
- **Graceful Degradation**: AST → text fallback, AI → NLP → rule-based fallback

### Typing Requirements
- **Strict typing** with opinionated pyright rules
- Use `TypedDict`, `Protocol`, `NamedTuple`, `enum.Enum` for structured data
- Prefer domain-specific dataclasses/BaseModels over `dict[str, Any]`
- Define proper generic types using `ParamSpec`/`Concatenate`

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
14. Replace registry system with dependency injection pattern, deprecate existing system ~0.4.0

### Key Implementation Notes
- Entry point in pyproject.toml: `codeweaver = "codeweaver.cli.app:main"`
- Main tool interface: `find_code(query: str, intent: IntentType | None = None, ...)`
- Provider system: Abstract `EmbeddingProvider`, `SparseEmbeddingProvider`, `RerankingProvider` and `VectorStoreProvider` classes
- Settings: Unified hierarchical config via `pydantic-settings` with env vars and TOML files and cloud secret integration (pydantic settings handles all the heavy lifting here)

## Documentation
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Unified architectural decisions and design principles (authoritative reference)
- Architecture high-level plans in `plans/` directory
- Specifications, tasks, and associated files in `specs`
- External API documentation in `data/context/apis/` API (summaries and practical guides)
- Complete docs for select external libraries are available in `context/apis/
- MkDocs configuration for documentation site
- Use `mise run docs-serve` for local documentation development

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
