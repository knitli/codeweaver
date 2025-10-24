<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Structural Refactoring Design - 2025-10-21

## Overview

Comprehensive architectural refactoring design for CodeWeaver to align with constitutional principles and proven patterns from FastAPI/pydantic ecosystem.

## Problem Statement

Current structure has accumulated inconsistencies:
- Type system fragmented across `_types/`, `_data_structures.py`, `models/`
- 15+ root-level files with unclear organization
- Provider code scattered across 4 locations
- Infrastructure scattered in underscore-prefixed files
- References to non-existent `_common.py`

## Proposed Solution

Layered architecture with clear responsibilities:

```
src/codeweaver/
├── core/              # Foundation (BasedModel, Span, CodeChunk)
├── config/            # Configuration (Settings, types)
├── api/               # External interface (CodeMatch, QueryIntent)
├── domain/            # Business logic (indexer, chunking)
├── infrastructure/    # Cross-cutting (logging, registry, utils)
├── providers/         # Provider ecosystem (embedding, reranking, vector_stores)
├── semantic/          # AST/grammar (unchanged)
├── middleware/        # FastMCP middleware (unchanged)
├── tokenizers/        # Tokenization (unchanged)
├── tools/             # MCP tools
├── cli/               # CLI interface
└── [8 root files]     # exceptions, language, _version, etc.
```

## Key Reorganizations

### 1. `_data_structures.py` (640 lines) → `core/` (6 modules)
- `types.py` - Type aliases, BlakeKey
- `spans.py` - Span, SpanGroup
- `chunks.py` - CodeChunk, ChunkKind
- `metadata.py` - SemanticMetadata, ExtKind
- `discovery.py` - DiscoveredFile
- `stores.py` - UUIDStore, BlakeStore, hashing

### 2. `settings_types.py` (900+ lines) → `config/` (4 modules)
- `types.py` - Common config types
- `middleware.py` - Middleware settings
- `providers.py` - Provider settings
- `logging.py` - Logging settings

### 3. Provider Consolidation
- `provider.py` → `providers/base.py`
- `embedding/` → `providers/embedding/`
- `reranking/` → `providers/reranking/`
- `vector_stores/` → `providers/vector_stores/`

### 4. Infrastructure Consolidation
- `_logger.py` → `infrastructure/logging.py`
- `_registry.py` → `infrastructure/registry.py`
- `_statistics.py` → `infrastructure/statistics.py`
- `_utils.py` → `infrastructure/utils/{git,tokens,etc}.py`

## Constitutional Alignment

✅ Principle V (Simplicity Through Architecture) - Flat with purposeful grouping
✅ Principle II (Proven Patterns) - FastAPI/pydantic patterns
✅ Plugin Architecture - All providers unified
✅ Type System Discipline - Clear hierarchy

## Impact

- Root files: 15+ → 8 (47% reduction)
- Type locations: 3 → 1 (foundation)
- Provider locations: 4 → 1
- Clear layered dependencies

## Documentation Created

1. `claudedocs/structural_refactor_design.md` - Full design specification
2. `claudedocs/structural_refactor_diagram.md` - Visual diagrams and decomposition
3. `claudedocs/refactor_summary.md` - Executive summary
4. `claudedocs/refactor_quick_reference.md` - Migration quick reference

## Migration Phases

1. Create Structure
2. Move Foundation (core/)
3. Move Configuration (config/)
4. Reorganize Providers
5. Reorganize Domain
6. Consolidate Infrastructure
7. Finalize API
8. Validation

## Next Steps

1. Review design with stakeholders
2. Get approval
3. Create detailed implementation plan
4. Execute systematic migration
5. Validate with tests

## Design Session Context

- User started structural refactor, created `_types/` directory
- Realized need for overall design before proceeding
- Requested constraint-free architectural ideal
- Focus: structural clarity and roles, not implementation details
- Scope: `src/codeweaver/` only, high-level organization

## Key Decisions

- **Three-layer type system**: Foundation (core) → Domain → API
- **Infrastructure vs Domain split**: Technical vs business logic
- **Provider unification**: Single `providers/` package
- **Config decomposition**: Split 900-line file into 4 focused modules
- **Services → Domain**: Clearer DDD terminology

## References

- Project Constitution: `.specify/memory/constitution.md` v2.0.1
- Architecture Doc: `ARCHITECTURE.md`
- Previous memory: `architecture_review_analysis`
