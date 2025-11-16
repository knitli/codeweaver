<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Codebase Structure and Organization

## Directory Layout

```
codeweaver-mcp/
├── src/codeweaver/              # Main source code
├── tests/                       # Test suite
├── scripts/                     # Development and build scripts
├── docs/                        # MkDocs documentation
├── plans/                       # Architecture specifications
├── specs/                       # Detailed specifications
├── .specify/memory/             # Project memory and constitution
├── claudedocs/                  # Claude-specific documentation
├── examples/                    # Usage examples
├── typings/                     # Type stub files
└── mise-tasks/                  # Mise task scripts
```

## Source Code Structure (`src/codeweaver/`)

### Core Modules (Root Level)
- `__init__.py` - Package initialization
- `main.py` - Application entry point
- `exceptions.py` - Custom exception definitions
- `_version.py` - Version information (auto-generated)
- `py.typed` - PEP 561 marker for type stubs

### Major Packages

#### `agent_api/` - MCP Agent Interface
MCP tool interface and agent-facing API.
- **Purpose**: `find_code` tool implementation for MCP agents
- **Key**: Single tool interface for semantic code search

#### `cli/` - Command Line Interface
CLI commands and entry points.
- **Commands**: `server`, `search`, `config`
- **Entry Point**: `codeweaver.cli.__main__:main`
- **Framework**: cyclopts for argument parsing

#### `common/` - Shared Utilities
Cross-cutting utilities and helpers.
- **Contents**: Logging, telemetry, statistics, utilities

#### `config/` - Configuration Management
Settings and configuration handling.
- **Framework**: pydantic-settings
- **Formats**: TOML, YAML, environment variables
- **Hierarchy**: Multi-source configuration with validation

#### `core/` - Core Types and Abstractions
Fundamental types, protocols, and base classes.
- **Key Classes**: `BasedModel`, `BaseEnum`, type definitions
- **Purpose**: Foundation for all other modules

#### `engine/` - Indexing and Search Engine
Core indexing, chunking, and search functionality.
- **Components**: 
  - Indexer: File processing and chunk creation
  - Chunking service: AST-based code segmentation
  - Search pipeline: Query execution
  - Progress tracking: Indexing progress monitoring
  - Checkpointing: Resume interrupted operations

#### `middleware/` - FastMCP Middleware
FastMCP middleware components.
- **Components**:
  - `chunking.py` - Code chunking middleware
  - `filtering.py` - File discovery with gitignore
  - `telemetry.py` - PostHog usage tracking

#### `providers/` - Pluggable Provider System
Extensible provider implementations.
- **Embedding Providers**: VoyageAI, OpenAI, fastembed, sentence-transformers
- **Vector Stores**: Qdrant, in-memory
- **Reranking**: VoyageAI rerank
- **Pattern**: Protocol-based interfaces with registry

#### `semantic/` - AST and Semantic Analysis
Code understanding and analysis.
- **Purpose**: AST-based chunking, language detection, semantic classification
- **Tools**: ast-grep integration, tree-sitter grammars

#### `server/` - MCP Server Implementation
FastMCP server and HTTP endpoints.
- **Server**: MCP protocol server
- **Health Service**: Health monitoring endpoint
- **Framework**: FastMCP + uvicorn

#### `tokenizers/` - Token Counting
Token calculation utilities.
- **Purpose**: Context budget management, chunk sizing

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
- `ARCHITECTURE.md` - Design decisions and principles
- `PRODUCT.md` - Product overview and roadmap
- `CODE_STYLE.md` - Code style guide
- `AGENTS.md` - Agent development guidance and context
- `.specify/memory/constitution.md` - Project constitution (v2.0.1)

### API Documentation (`context/apis/`)
- External API references
- Complete documentation for select libraries:
  - `pydantic-evals`, `pydantic-graph`, `fastmcp`

### MkDocs Site (`docs/`)
Run local documentation server: `mise run docs-serve`

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
from codeweaver.exceptions import CodeWeaverError
```

### Internal Package Structure
- **Public API**: Exposed through `__init__.py`
- **Private modules**: Prefixed with `_` (e.g., `_chunking.py`)
- **Internals**: Complex logic in `_internals/` subpackage

## Flat Structure Philosophy

Following pydantic ecosystem patterns:
- **Group related modules**: In packages (e.g., all providers together)
- **Keep root-level otherwise**: Avoid unnecessary nesting

This structure balances discoverability with organization.
