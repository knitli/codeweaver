<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CodeWeaver is an extensible MCP (Model Context Protocol) server for semantic code search. It provides intelligent codebase context discovery through a single `find_code` tool interface, supporting multiple embedding providers, vector databases, and data sources through a plugin architecture.

**Current Status**: Early development phase with foundational components partially implemented. The core MCP server, CLI, and provider system are not yet implemented.

## Project Constitution (DEFINITIVE GUIDANCE)

**This project is governed by the CodeWeaver Constitution at `.specify/memory/constitution.md`.**

All development decisions, code reviews, and technical choices MUST comply with the constitutional principles. When in doubt, consult the constitution first.

### Constitutional Requirements Summary

1. **AI-First Context**: Enhance AI agent understanding of code through precise context delivery
2. **Proven Patterns**: Use FastAPI/pydantic ecosystem patterns over reinvention
3. **Evidence-Based Development (NON-NEGOTIABLE)**: All decisions backed by verifiable evidence
4. **Testing Philosophy**: Effectiveness over coverage - focus on user-affecting behavior
5. **Simplicity Through Architecture**: Clear, flat structure with obvious purpose

**Full Constitutional Text**: See `.specify/memory/constitution.md` v2.0.0

## Development Commands

### Environment Setup
```bash
# Set up development environment
mise run setup

# Install dependencies
uv sync --all-groups

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

# Clean build artifacts
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
- **Type hints**: Modern Python ≥3.11 syntax (`int | str`, `typing.Self`)
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

### Phase 1: Core Infrastructure
1. Implement CLI entry point (`src/codeweaver/cli/app.py`)
2. Create main FastMCP server with `find_code` tool
3. Build provider abstractions and concrete implementations
4. Add basic pipeline orchestration

### Phase 2: Full Functionality  
5. Implement background indexing with watchfiles
6. Add comprehensive error handling and graceful degradation
7. Integrate telemetry and observability
8. Build comprehensive test suite

### Key Implementation Notes
- Entry point in pyproject.toml: `codeweaver = "codeweaver.cli.app:main"`
- Main tool interface: `find_code(query: str, intent: Optional[Literal[...]] = None, ...)`
- Provider system: Abstract `EmbeddingProvider` and `VectorStoreProvider` classes
- Settings: Unified config via `pydantic-settings` with env vars and TOML files

## Documentation
- Architecture specs in `plans/` directory
- API documentation in `context/apis/` 
- Complete docs for select external libraries are available in `context/apis/complete_docs`, currently include:
  - [`pydantic-evals`](context/apis/complete_docs/pydantic-evals.md) (744 lines)
  - [`pydantic-graph`](context/apis/complete_docs/pydantic-graph.md) (1052 lines)
  - [complete `fastmcp`](context/apis/complete_docs/fast-mcp-VERY-LARGE.md) (23,000 lines)
  - [`fastmcp` overview](context/apis/complete_docs/fast-mcp-summary.md) (140 lines) - contains section references with URLs.
- MkDocs configuration for documentation site
- Use `mise run docs-serve` for local documentation development

## Instructions

**CONSTITUTIONAL COMPLIANCE REQUIRED**: Before any development work, validate your approach against the Project Constitution at `.specify/memory/constitution.md`. This constitution supersedes all other guidance.

If your task involves writing or editing code in the codebase, you must:

1. **First**: Ensure compliance with the [Project Constitution](.specify/memory/constitution.md)
2. **Second**: Read the instructions in [the AGENTS file](AGENTS.md)

The constitution contains non-negotiable principles that govern all technical decisions in this project.