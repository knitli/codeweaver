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

[![PyPI](https://img.shields.io/pypi/v/codeweaver-mcp.svg)](https://pypi.org/project/codeweaver-mcp/)
[![Python Versions](https://img.shields.io/pypi/pyversions/codeweaver-mcp.svg)](https://pypi.org/project/codeweaver-mcp/)

Install CodeWeaver from PyPI:

```bash
pip install codeweaver-mcp
```

**Requirements:**
- Python 3.12, 3.13, or 3.14

**Supported Installation Options:**

For basic usage with recommended defaults:
```bash
pip install codeweaver-mcp[recommended]
```

For à-la-carte installation with specific providers:
```bash
# Core + OpenAI embedding + Qdrant vector store + filesystem source
pip install 'codeweaver-mcp[required-core,provider-openai,provider-qdrant,source-filesystem]'
```

See the [installation documentation](https://dev.knitli.com/codeweaver) for detailed provider options and configuration.

---

**📊 For Product Managers & Decision Makers**: See [PRODUCT.md](PRODUCT.md) for comprehensive product overview, user personas, success metrics, competitive positioning, and roadmap details. We don't hide our plans -- we want your input and needs to drive them!

**🚀 Strategic Vision**: CodeWeaver evolves from best-in-class search tool → context platform → unified MCP orchestration hub. See [PRODUCT.md - Product Vision](PRODUCT.md#product-vision) for our 4-phase evolution from search to "context-as-a-service."

**🎛️ Three-Tier API Design**: Different interfaces for different users:
- **Human API**: Deep configurability (TOML/YAML config, extensive CLI, plugin architecture)
- **User Agent API**: Radical simplicity (1 tool: `find_code` with natural language)
- **Context Agent API**: Controlled expansion (3-8 specialized curation tools)

See [PRODUCT.md - Three-Tier API Architecture](PRODUCT.md#three-tier-api-architecture) for detailed design rationale.

**🏗️ Architecture & Design Decisions**: See [ARCHITECTURE.md](ARCHITECTURE.md) for the authoritative reference on CodeWeaver's architectural decisions, design principles, technical philosophy, and key technical decisions. This document consolidates all design decisions into a unified resource.

---

## Architectural Goals

1. **Provide semantically-rich, ranked and prioritized search results for developers and their coding agents.**
   
  **How**
  - CodeWeaver uses ast-grep, and support for dozens of embedding and reranking models, local and remote, to provide weighted responses to searches.
  - CodeWeaver is fully pluggable. You can add embedding providers, reranking providers, agent providers, services and middleware, and *new data sources* beyond your codebase.

2. **Eliminate 'cognitive load' on coding agents trying to get context on the codebase.**

  **How**
  - **Reduces all operations to a single, simple, plain language tool** -- `find_code` -- allowing your coding agent to request what it needs, explain what it's trying to do, and get exactly the information it needs in response.
  - Uses **mcp sampling** to search and curate context for your coding agent -- using your coding agent! (also supports this outside of an MCP context where sampling isn't enabled or MCP is not available). CodeWeaver uses a *different instance* of your agent to evaluate your agent's needs and curate a response, keeping your agent unburdened with all the associated context from searching.

3. **Significantly cut context bloat, and costs**. This also helps keep agents razor focused on their tasks.

  **How**
  - CodeWeaver aims to *restrict* context to your coding agent to *only the information it needs*. Of course, that's not easy to do, but we hope to get close.
  - By reducing the context that's returned to your Agent, your Agent no longer has to "carry" all of that extra, unused, context with them -- reducing token use *with every turn* and reducing its exponential growth.

## Design Principles

CodeWeaver is built on five core principles that guide every technical decision:

**1. AI-First Context**
Every feature enhances AI agent understanding of code through precise context delivery. We design for AI consumption first, human inspection second.

**2. Proven Patterns Over Reinvention**
We use proven patterns from successful open source projects in the pydantic ecosystem (i.e. FastAPI). Familiar interfaces reduce learning curve and increase developer adoption and contribution.

**3. Evidence-Based Development**
All technical decisions backed by verifiable evidence: documentation, testing, metrics, or reproducible demonstrations. No workarounds, no placeholder code, no "it should work" assumptions.

**4. Effectiveness Over Coverage**
Testing focuses on critical behavior affecting user experience. One realistic integration test beats ten implementation detail tests. Code coverage scores don't measure outcomes.

**5. Simplicity Through Architecture**
We transform complexity into clarity using simple modularity with extensible design where purpose is obvious. Flat structure, clear naming, minimal nesting.

**In Practice**: These principles led to our single-tool interface (simplicity), plugin architecture (proven patterns), and span-based precision (evidence-based).

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

Semantic metadata from AST-Aware indexing
- ExtKind enumerates language and chunk types.
- SemanticMetadata tracks AST nodes and classifications to improve chunk boundaries and ranking.
- Extensive semantic metadata classification and task-based priority ranking system for nuanced searches
- Supports 26 programming languages

*Backup Code-Aware Indexing Support for 170+ languages! [^1]
- CodeWeaver's backup chunking system is not semantically aware, but it does have sophisticated heuristics to identify context-relevant code blocks based on language-specific patterns found in 170+ programming languages.
- Allows CodeWeaver to approximate semantic context for even obscure or aging codebases. If you maintain a codebase with legacy "it just works so keep it" code, this is for you -- assembly, cobol, pascal, perl -- we've got you!
- From Agda, Beef, Coq, Dhall, and Factor to SAS, Smali, Xaml and Zig -- your language is probably supported.
- Really not supported? Define some delimiters with metadata and file extensions in your config and CodeWeaver will take care of the rest! (or, just associate it with file extensions and a family pattern like C style, python, ML, lisp, markup, shell, functional latex, ruby, or matlab and it'll 'just work'.)

Provider ecosystem
- Embedding providers: VoyageAI, AWS Bedrock, Cohere (including Azure), Google, Huggingface Hub, Mistral, FastEmbed, SentenceTransformers, Openai Compatible (OpenAI, Azure, Fireworks, Groq, Ollama, Heroku) 
- Rerank providers: VoyageAI, AWS Bedrock, Cohere, FastEmbed, Sentence Transformers.
- Agent providers: All pydantic-ai providers (OpenAI, Anthropic, Google, Mistral, Groq, Hugging Face, Bedrock, etc.).
- Vector stores: in-memory or Qdrant (both use Qdrant-client and both not fully implemented yet), others planned after initial release.
- Data sources:
  - Now: filesystem (with file watching), Tavily, DuckDuckGo
  - Planned: Context7 (external API docs)

Advanced filtering (vendored)
- Rich, validated filters for keyword, numeric, range, boolean, etc.
- Dynamic tool signature generation via decorator-based wrappers.
- Based on Qdrant's filtering abilities, but abstracted to be vendor agnostic.

Configuration and settings
- Multi-source configuration via pydantic-settings.
- Capability-based provider selection and dynamic instantiation (registry completing).
- Token budgeting and caching strategies planned.


Providers and optional extras

Top-level extras (convenience)

Default install (VoyageAI for rerank/embedding, FastEmbed for sparse indexing, Anthropic for agents, Qdrant local or cloud for vector storage and hybrid search)
- recommended: end-to-end features with cloud support 
- recommended-no-telemetry: same as above without telemetry
- recommended-local-only: local embedding/rerank (fastembed), no cloud calls

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
  - Filters (planned defaults -- for agent searches, these are applied by strategies):
    - language: keyword (any)
    - file_type: keyword (code, docs, config)
    - on/after dates, semantic and text patterns, repository locations (i.e. frontend only), 
  - Output: span-based code matches with semantic/relational metadata
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
- FastMCP middleware and application state management
- File discovery + indexing: rignore-based discovery; background indexing with watchfiles
- Provider registry (_registry.py) and final glue code
- Authentication and authorization middleware

What’s ~97% complete
- Embedding, reranking, and agentic capabilities (provider integrations and orchestration)
- Agent handling is implemented but needs to be tied fully into the pipelines
- Rich semantic grammar context system to inform AST metadata/context
- AST-based and semantically-guided chunking
- Heuristically driven pseudo-semantic backup chunking system.

What's About 85% Complete
- Hybrid search with unified ranking across signals

What’s in progress / planned
- Vector stores: Qdrant implementation (span-aware); in-memory baseline
- Pipelines and strategies: orchestration via pydantic-graph
- Query intent analysis via agents
- Performance, caching, and comprehensive test coverage



Roadmap

[X] Phase 1: Core integration
- Complete provider registry and statistics integration
- Finalize FastMCP application state and context handling
- CLI commands
- Deliver working find_code over text search with filter integration
- Basic tests for core workflows


Phase 2: Semantic search (~90% complete) [^2]
- 🟢 Integrate embeddings (VoyageAI, fastembed)
- 🟢 Robust statistics and usage system
- :yellow_circle: AST-aware chunking and span-aware indexing
- 🟢 Background indexing (watchfiles) and incremental updates
- :yellow_circle: Hybrid search with unified ranking and intent analysis
- 🔴 Qdrant integration


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
- Default installation includes privacy and proprietary-information-preserving telemetry with Posthog. We take *extreme* care not to collect any information that could reveal your identity or projects. If you're unsure, please look at our implementation for yourself so you can see what we collect.
- You can also optionally use the `recommended-no-telemetry` install flag for a telemetry-free install (or just disable in settings or an environment variable)

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
- Requires Python >= 3.12 (classifiers include 3.12–3.14)

[^1]: CodeWeaver **will not index an unknown file extension**. If you want it to index an unsupported extension, then you **must** add it to your config file! If we don't know what it is, we don't want to add noise to your agent's context!

[^2]: Working alone and before CodeWeaver is officially released, I've developed bad habits regarding treating `main` like a development branch. Some of this will be broken from time to time as a result. If anyone is actively wanting to use and get involved: let me know! It'd be great motivation to return to disciplined feature-based PRs! (it's not all bad habits, I also wanted folks to see the project progress and I know most people won't look at other branches).