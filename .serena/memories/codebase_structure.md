<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Codebase Structure and Organization

## Directory Layout

```
codeweaver/
├── src/codeweaver/              # Main source code
├── tests/                       # Test suite
├── scripts/                     # Development and build scripts
├── docs/                        # MkDocs documentation + archive
├── specs/                       # Detailed specifications
├── .specify/memory/             # Project memory and constitution
├── examples/                    # Usage examples
├── typings/                     # Type stub files
└── mise-tasks/                  # Mise task scripts
```

## Source Code Structure (`src/codeweaver/`)

### Core Modules (Root Level)
- `__init__.py` - Package initialization
- `main.py` - Application entry point
- `_version.py` - Version information (auto-generated)
- `py.typed` - PEP 561 marker for type stubs

### Major Packages

#### `cli/` - Command Line Interface
CLI commands and entry points.
- **Commands**: `server`, `search`, `config`, `doctor`, `index`, `init`, `ls`, `migrate`, `start`, `status`, `stop`
- **Entry Point**: `codeweaver.cli.__main__:main`
- **Framework**: cyclopts for argument parsing
- **UI**: `cli/ui/` with `StatusDisplay`, error handling, user interaction

#### `core/` - Core Domain Models, Business Logic, and Shared Infrastructure
Fundamental types, protocols, base classes, DI framework, configuration, telemetry, and utilities.
- **Key Classes**: `CodeChunk`, `DiscoveredFile`, `Span`, `SpanGroup`, `UUIDStore`, `BlakeStore`, `BasedModel`, `BaseEnum`
- **Sub-packages**:
  - `config/` - Core configuration (pydantic-settings based)
  - `dependencies/` - Core dependency injection bindings
  - `di/` - Dependency injection framework (container, dependency definitions)
  - `telemetry/` - PostHog usage tracking and analytics
  - `types/` - Type definitions (`Provider`, `ProviderCategory` enums, aliases, models, sentinel, etc.)
  - `utils/` - Common utilities (checks, environment, filesystem, introspection, process management, text)

#### `engine/` - Indexing and Search Engine
Core indexing, chunking, and search functionality.
- **Sub-packages**:
  - `chunker/` - Code chunking (AST-based semantic + delimiter-based for 150+ languages)
  - `config/` - Engine configuration (chunker, indexer, failover settings)
  - `managers/` - State managers (checkpoint, manifest, progress tracking)
  - `services/` - Engine services (chunking, indexing, watching, failover, migration, reconciliation, snapshot)
  - `watcher/` - File system watching for incremental indexing (`IgnoreFilter` wraps `rignore`)

#### `providers/` - Pluggable Provider System
Extensible provider implementations.
- **Embedding Providers**: 11+ providers (VoyageAI, OpenAI, fastembed, sentence-transformers, Bedrock, Cohere, Google, HuggingFace, LiteLLM, Mistral, and OpenAI-compatible factory)
- **Vector Stores**: Qdrant (local/cloud), in-memory (with search filtering)
- **Reranking**: VoyageAI, Cohere, Bedrock, fastembed, sentence-transformers
- **Agent Providers**: wraps pydantic-ai
- **Data Providers**: DuckDuckGo, Exa, Tavily
- **Sub-packages**:
  - `config/` - Provider configuration (categories, clients, SDK configs, profiles)
  - `dependencies/` - Provider DI (capabilities, registration, services)
  - `embedding/` - Embedding providers and 20+ model capability definitions
  - `env_registry/` - Environment-based provider registry
  - `reranking/` - Reranking providers and capabilities
  - `types/` - Provider type definitions (circuit breaker, embedding, resolvers, search, vectors)
  - `vector_stores/` - Vector database providers with search filtering

#### `semantic/` - AST and Semantic Analysis
Code understanding and analysis.
- **Purpose**: AST-based chunking, language detection, semantic classification
- **Tools**: ast-grep integration, tree-sitter grammars
- **Data**: Classification definitions and AST node type definitions

#### `server/` - Server Implementations
FastMCP server, HTTP management, and agent API.
- **Sub-packages**:
  - `agent_api/` - Tool interfaces (`find_code` tool in `search/` subpackage)
  - `config/` - Server configuration (MCP, middleware, settings)
  - `health/` - Health check system (endpoint, service, models)
  - `mcp/` - MCP protocol implementation (FastMCP server at port 9328, middleware, tools, user agent)
- **Key files**: `management.py` (Starlette at port 9329), `server.py` (entry point), `background_services.py`, `lifespan.py`

## Testing Structure (`tests/`)

### Test Organization
```
tests/
├── unit/              # Unit tests for individual components
├── integration/       # Integration tests for component interactions
├── contract/          # Contract tests for provider interfaces
├── performance/       # Performance and benchmark tests
└── fixtures/          # Test fixtures and data
```

### Test Markers (from pyproject.toml)
Tests use extensive pytest markers for granular execution:
- **Categories**: `unit`, `integration`, `e2e`, `validation`
- **Performance**: `benchmark`, `slow`, `performance`
- **Dependencies**: `network`, `external_api`, `real_providers`
- **Features**: `embeddings`, `search`, `indexing`, `mcp`, `server`
- **Stability**: `flaky`, `timeout`, `retry`

### Running Tests
```bash
pytest -m "unit"                    # Unit tests only
pytest -m "integration"             # Integration tests
pytest -m "not network"             # Skip network tests
pytest -m "not external_api"        # Skip external API tests
pytest tests/specific_test.py       # Specific test file
```

## Scripts Structure (`scripts/`)

### Categories
```
scripts/
├── build/              # Build and packaging scripts
├── code-quality/       # Linting, formatting, license headers
├── dev-env/           # Development environment setup
├── docs/              # Documentation generation
├── language-support/  # Language grammar and delimiter generation
├── model-data/        # Model data conversion utilities
├── testing/           # Test utilities and markers
└── utils/             # General utilities
```

### Key Scripts
- `scripts/code-quality/fix-ruff-patterns.sh` - Fix ruff patterns
- `scripts/code-quality/update-licenses.py` - Update license headers
- `scripts/dev-env/install-mise.sh` - Install mise tool
- `scripts/language-support/download-ts-grammars.py` - Download grammars
- `scripts/testing/apply-test-marks.py` - Apply pytest markers

## Documentation Structure

### Primary Documentation Files
- `README.md` - Project overview and quickstart
- `CODE_STYLE.md` - Code style guide
- `AGENTS.md` - Agent development guidance and context (CLAUDE.md symlinks here)
- `.specify/memory/constitution.md` - Project constitution (v2.0.1)

### Archived Documentation
- `docs/archive/ARCHITECTURE.md` - Design decisions and principles (stale, archived)
- `docs/archive/PRODUCT.md` - Product overview and roadmap (stale, archived)

### Documentation Site (`docs-site/`)
Astro/Starlight based documentation at docs.knitli.com/codeweaver.

### Internal Development Docs (`docs/`)
Smattering of internal development docs (migration guides, research, troubleshooting). May be stale in places.

## Configuration Files

### Project Configuration
- `pyproject.toml` - Python project metadata, dependencies, tool config
- `mise.toml` - Task runner configuration
- `ruff.toml` - Ruff linter/formatter configuration
- `mkdocs.yml` - Documentation site configuration
- `codeweaver.toml` - CodeWeaver application configuration

### Development Configuration
- `.python-version` - Python version (3.13)
- `.editorconfig` - Editor configuration
- `.gitignore` - Git ignore patterns
- `.gitattributes` - Git attributes
- `uv.lock` - Locked dependency versions

## Build Artifacts and Directories

### Generated/Excluded Directories (in .gitignore)
- `.venv/` - Virtual environment
- `.pytest_cache/` - Pytest cache
- `.ruff_cache/` - Ruff cache
- `htmlcov/` - Coverage HTML reports
- `dist/` - Build distributions
- `__pycache__/` - Python bytecode cache

### Documentation Output
- `site/` - MkDocs built site (generated)
- `coverage.xml` - Coverage report
- `test-results.xml` - JUnit test results

## Module Import Patterns

### Preferred Import Style
```python
# 'import' separated from 'from x import' statements at all levels
# Standard library
import sys

from typing import Any

# Third-party (grouped by category)
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# Local imports (absolute from package root)
from codeweaver.core.types import BasedModel
from codeweaver.core import CodeWeaverError
```

### Internal Package Structure
- **Public API**: Exposed through `__init__.py`
- **Private modules**: Prefixed with `_` (e.g., `_logging.py`)
- **Internals**: Complex logic in `_internals/` subpackage

## Flat Structure Philosophy

Following pydantic ecosystem patterns:
- **Group related modules**: In packages (e.g., all providers together)
- **Keep root-level otherwise**: Avoid unnecessary nesting
- **Configuration distributed**: Each domain package owns its config (core/config/, engine/config/, server/config/, providers/config/)
- **Dependency injection**: Each domain has dependencies.py for DI bindings

This structure balances discoverability with organization.
