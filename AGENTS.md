<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CodeWeaver is an extensible MCP (Model Context Protocol) server for semantic code search. It provides intelligent codebase context discovery through a single `find_code` tool interface, supporting multiple embedding providers, vector databases, and data sources through a plugin architecture.

**Current Status**: Nearing Alpha release. Most core features complete; completing integration and testing.

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

### Testing
```bash
# Run tests
mise run test

# Run with coverage
mise run test-cov

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
├── _common.py           # BaseEnum utilities
├── _utils.py            # Git, token helpers  
├── language.py          # Language detection (20+ languages)
└── middleware/          # FastMCP middleware components
    ├── chunking.py      # AST-based code segmentation
    ├── filtering.py     # File discovery with gitignore support
    └── telemetry.py     # PostHog usage tracking
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

### Phase 2: Core Functionality  ✅ **complete - integrating/testing**
5. Implement background indexing with watchfiles
6. Add comprehensive error handling and graceful degradation
7. Integrate telemetry and observability
8. Build comprehensive test suite

### Phase 3: Advanced Orchestration ❌ **Planned for Next Two Major Alpha Releases**
9. Integrate agentic handling of query response (Context agent and Context agent API)
10. Add Context agent tools
11. Pluggable pipeline orchestration with `pydantic-graph`
12. Pipeline/response evaluation and validation with `pydantic-eval`
13. Expanded testing
14. Replace registry system with dependency injection pattern, deprecate existing system ~4th major alpha release

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
