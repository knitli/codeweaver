<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Structural Refactoring Design

**Status**: Design Proposal
**Created**: 2025-10-21
**Context**: Pre-release architectural cleanup

## Constitutional Alignment

This refactoring aligns with:
- **Principle V (Simplicity Through Architecture)**: Flat structure grouping related modules, obvious purpose
- **Principle II (Proven Patterns)**: FastAPI/pydantic ecosystem patterns
- **Architecture Standards**: Clear module organization with extensibility

## Current State Analysis

### Structural Issues

1. **Type System Fragmentation**
   - `_types/` - Base types and sentinel (new, incomplete)
   - `_data_structures.py` - Core data structures (Span, CodeChunk)
   - `settings_types.py` - Configuration types
   - `models/` - MCP response models
   - **Problem**: No clear categorization principle

2. **Naming Inconsistencies**
   - `_types.base` has `BasedModel` and `BaseEnum`
   - ARCHITECTURE.md references `_common.py` (doesn't exist)
   - `_data_structures.py` mixes concerns (hashing, stores, chunks)

3. **Root-Level Crowding**
   - 15+ files in `src/codeweaver/` root
   - Mix of infrastructure (`_logger`, `_registry`, `_utils`)
   - Mix of configuration (`settings`, `settings_types`)
   - Mix of core domain (`provider`, `language`)

4. **Unclear Module Purposes**
   - What belongs in `models/` vs `_types/`?
   - Where do core domain concepts go?
   - What's the difference between `_utils` and helper modules?

## Ideal Architecture

### Guiding Principles

**From FastAPI/pydantic patterns:**
- Flat when possible, grouped when necessary
- Clear naming reveals purpose
- Domain concepts separate from infrastructure
- Types close to usage, except foundations

**Key insight**: CodeWeaver has THREE distinct type layers:
1. **Foundation types** - Used everywhere (`BaseEnum`, `BasedModel`, type aliases)
2. **Domain models** - Core concepts (`CodeChunk`, `Span`, `SemanticMetadata`)
3. **API models** - External interfaces (`CodeMatch`, `FindCodeResponseSummary`)

### Proposed Structure

```
src/codeweaver/
├── core/                       # Core domain models and types
│   ├── __init__.py            # Export public core API
│   ├── types.py               # Foundation types (BaseEnum, BasedModel, Sentinel, type aliases)
│   ├── spans.py               # Span, SpanGroup (location primitives)
│   ├── chunks.py              # CodeChunk, ChunkKind, ChunkSource
│   ├── metadata.py            # SemanticMetadata, Metadata, ExtKind
│   ├── discovery.py           # DiscoveredFile
│   └── stores.py              # UUIDStore, BlakeStore, hashing utilities
│
├── config/                     # All configuration
│   ├── __init__.py            # Export Settings and main types
│   ├── settings.py            # Main Settings class
│   ├── types.py               # Configuration types (was settings_types.py)
│   ├── middleware.py          # Middleware settings
│   ├── providers.py           # Provider settings
│   └── logging.py             # Logging configuration
│
├── api/                        # External API models (MCP interface)
│   ├── __init__.py
│   ├── models.py              # CodeMatch, FindCodeResponseSummary
│   └── intent.py              # IntentResult, QueryIntent
│
├── domain/                     # Business logic services
│   ├── __init__.py
│   ├── indexer.py             # From services/indexer.py
│   ├── discovery.py           # From services/discovery.py
│   ├── textify.py             # From services/textify.py
│   └── chunking/              # From services/chunker/
│       ├── __init__.py
│       ├── router.py
│       ├── semantic.py
│       ├── registry.py
│       └── delimiters/
│
├── infrastructure/             # Cross-cutting infrastructure
│   ├── __init__.py
│   ├── logging.py             # From _logger.py
│   ├── registry.py            # From _registry.py
│   ├── statistics.py          # From _statistics.py
│   └── utils/
│       ├── __init__.py
│       ├── git.py             # Git utilities from _utils
│       ├── tokens.py          # Token utilities from _utils
│       └── hashing.py         # From _data_structures if not in core
│
├── providers/                  # All providers grouped
│   ├── __init__.py
│   ├── base.py                # From provider.py
│   ├── embedding/
│   ├── reranking/
│   └── vector_stores/
│
├── semantic/                   # Unchanged (well-structured already)
│   └── ...
│
├── middleware/                 # Unchanged
│   └── ...
│
├── tokenizers/                 # Unchanged
│   └── ...
│
├── tools/                      # MCP tools
│   └── ...
│
├── cli/                        # CLI interface
│   └── ...
│
├── exceptions.py               # All exceptions
├── language.py                 # Language detection
├── _capabilities.py            # Capabilities system
├── _constants.py               # Constants
├── _version.py                 # Version info
├── main.py                     # Entry point
└── __init__.py                 # Public API surface
```

### Key Changes Explained

#### 1. `core/` Package - Domain Primitives

**Purpose**: Fundamental types and models that define CodeWeaver's domain

**Contents**:
- `types.py` - Consolidates `_types/base.py`, `_types/sentinel.py`, and type aliases
- `spans.py` - Span-based location system (from `_data_structures`)
- `chunks.py` - CodeChunk and related (from `_data_structures`)
- `metadata.py` - Semantic metadata types (from `_data_structures`)
- `stores.py` - Hash stores and utilities (from `_data_structures`)

**Rationale**:
- These are CodeWeaver's fundamental concepts
- Used across all layers
- Clear naming: "core" = foundational to understanding system
- Follows pydantic pattern of core types package

#### 2. `config/` Package - Configuration Layer

**Purpose**: All configuration concerns in one place

**Contents**:
- Splits massive `settings_types.py` into logical groupings
- `settings.py` remains main Settings class
- Type definitions organized by concern

**Rationale**:
- Configuration is infrastructure, not core domain
- Current `settings_types.py` is 900+ lines - needs decomposition
- Follows pydantic-settings pattern

#### 3. `api/` Package - External Interface

**Purpose**: MCP tool response models

**Contents**:
- `models.py` - CodeMatch, FindCodeResponseSummary (from `models/core.py`)
- `intent.py` - QueryIntent models (from `models/intent.py`)

**Rationale**:
- These models define external API contract
- Separate from internal domain models
- Clear distinction: API = what agents see, Core = how we work internally

#### 4. `domain/` Package - Business Logic

**Purpose**: Application services and business logic

**Contents**:
- Services from `services/` package
- Renamed from "services" to "domain" for clarity

**Rationale**:
- "Domain" clearer than "services" (follows DDD terminology)
- Groups application logic separate from infrastructure
- Chunking remains nested (well-structured subdomain)

#### 5. `infrastructure/` Package - Cross-Cutting Concerns

**Purpose**: Technical infrastructure used across layers

**Contents**:
- Logging, registry, statistics, utilities
- Things prefixed with `_` that aren't types

**Rationale**:
- Clear separation: infrastructure vs domain vs core
- Removes underscore-prefixed files from root
- Follows hexagonal architecture pattern

#### 6. `providers/` Package - Provider Ecosystem

**Purpose**: Unified provider location

**Contents**:
- `base.py` - From `provider.py`
- Existing `embedding/`, `reranking/`, `vector_stores/`

**Rationale**:
- All provider-related code in one place
- Clear entry point for provider system
- Matches constitutional plugin architecture requirement

### What Stays Flat

These remain in root because:
- **High-level entry points**: `main.py`, `cli/`, `tools/`
- **Well-bounded domains**: `semantic/`, `middleware/`, `tokenizers/`
- **True singletons**: `exceptions.py`, `language.py`, `_version.py`, `_constants.py`

Root stays clean (8 files + 8 packages vs current 15+ files + 9 packages).

## Module Responsibility Matrix

| Module | Responsibility | Dependencies |
|--------|---------------|--------------|
| `core/` | Domain primitives, fundamental types | None (foundation layer) |
| `config/` | All configuration | `core/` only |
| `api/` | External interface models | `core/` for types |
| `domain/` | Business logic, services | `core/`, `config/`, `providers/` |
| `infrastructure/` | Cross-cutting concerns | `core/`, `config/` |
| `providers/` | Provider implementations | `core/`, `config/` |
| `semantic/` | AST/grammar analysis | `core/`, `infrastructure/` |

## Implementation Notes

### Import Path Changes

**Before**:
```python
from codeweaver._types import BasedModel, BaseEnum
from codeweaver._data_structures import Span, CodeChunk
from codeweaver.models.core import CodeMatch
from codeweaver.settings_types import EmbeddingProviderSettings
```

**After**:
```python
from codeweaver.core.types import BasedModel, BaseEnum
from codeweaver.core.spans import Span
from codeweaver.core.chunks import CodeChunk
from codeweaver.api.models import CodeMatch
from codeweaver.config.types import EmbeddingProviderSettings
```

### Re-Export Strategy

Public API in `codeweaver/__init__.py` remains stable:
```python
# Stable public API
from codeweaver.core.types import BasedModel, BaseEnum
from codeweaver.core.spans import Span, SpanGroup
from codeweaver.core.chunks import CodeChunk
from codeweaver.api.models import CodeMatch, FindCodeResponseSummary
from codeweaver.exceptions import CodeWeaverError, ...

__all__ = (
    "BasedModel",
    "BaseEnum",
    "Span",
    "SpanGroup",
    "CodeChunk",
    "CodeMatch",
    ...
)
```

### File Decomposition Strategy

**`_data_structures.py` (640 lines) splits into**:
- `core/types.py` - Type aliases, BlakeKey, HashKeyKind
- `core/spans.py` - Span, SpanGroup
- `core/chunks.py` - CodeChunk, ChunkKind, ChunkSource
- `core/metadata.py` - SemanticMetadata, Metadata, ExtKind
- `core/discovery.py` - DiscoveredFile
- `core/stores.py` - UUIDStore, BlakeStore, hashing functions

**`settings_types.py` (900+ lines) splits into**:
- `config/types.py` - Base types, common type definitions
- `config/middleware.py` - Middleware configuration types
- `config/providers.py` - Provider configuration types
- `config/logging.py` - Logging configuration types

## Alignment with Design Patterns

### FastAPI Pattern Matching

**FastAPI structure**:
```
fastapi/
├── routing/       # Domain concern
├── middleware/    # Cross-cutting
├── dependencies/  # Infrastructure
└── types.py       # Foundation types
```

**CodeWeaver (after refactor)**:
```
codeweaver/
├── domain/        # Business logic (like routing/)
├── middleware/    # Cross-cutting (same)
├── infrastructure/# Support systems (like dependencies/)
├── core/         # Foundation types (like types.py)
├── config/       # Configuration layer
└── providers/    # Plugin system
```

### Pydantic Pattern Matching

**Pydantic structure**:
```
pydantic/
├── types.py           # Core types
├── fields.py          # Field definitions
├── main.py            # BaseModel
└── config.py          # Configuration
```

**Influence on CodeWeaver**:
- Foundation types in dedicated module
- Core models separate from configuration
- Clear layering: types → models → config

## Constitutional Compliance Checklist

✅ **Simplicity Through Architecture** (Principle V)
- Flat structure with purposeful grouping
- Clear module boundaries
- Obvious responsibilities

✅ **Proven Patterns** (Principle II)
- Follows FastAPI layering
- Matches pydantic organization
- Standard DDD terminology (domain, infrastructure)

✅ **Plugin Architecture Requirements**
- All providers unified under `providers/`
- Clear extension points
- Registry pattern maintained

✅ **Type System Discipline**
- Foundation types in `core/types.py`
- Clear hierarchy: foundation → domain → API
- Structured data organization

## Benefits

1. **Clarity**: Purpose obvious from structure
2. **Maintainability**: Related concerns grouped
3. **Scalability**: Room to grow in each package
4. **Discoverability**: Know where to find things
5. **Testing**: Clear boundaries enable focused tests
6. **Onboarding**: Structure teaches architecture

## Trade-offs

**Costs**:
- Large refactor requiring import path updates across codebase
- Temporary disruption during transition
- Risk of introducing bugs during restructuring

**Mitigations**:
- Comprehensive testing before/after
- Incremental migration strategy possible
- Clear mapping from old to new structure

**Justification**:
- Pre-release timing minimizes external impact
- Constitutional alignment essential for long-term success
- Establishes clear patterns for future development

## Next Steps

1. **Validation**: Confirm design aligns with vision
2. **Planning**: Create detailed migration plan
3. **Tooling**: Prepare automated refactoring scripts
4. **Testing**: Ensure comprehensive test coverage exists
5. **Execution**: Systematic package-by-package migration
6. **Verification**: Validate all tests pass after changes

---

**Questions for Review**:
1. Does `core/` vs `api/` vs `domain/` distinction make sense?
2. Is `infrastructure/` the right name (vs `utils/` or `internal/`)?
3. Should `config/` and `providers/` merge or stay separate?
4. Any concerns about import path changes?
