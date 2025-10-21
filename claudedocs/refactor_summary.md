# CodeWeaver Structural Refactoring - Executive Summary

**Status**: Design Complete - Ready for Review
**Created**: 2025-10-21
**Context**: Pre-release architectural cleanup

## The Problem

CodeWeaver's source structure has accumulated inconsistencies as it progressed toward release:

1. **Type System Confusion**: Three overlapping locations for types (`_types/`, `_data_structures.py`, `models/`)
2. **Root Crowding**: 15+ files at package root with unclear organization
3. **Provider Fragmentation**: Provider code scattered across 4 locations
4. **Infrastructure Scattered**: Utility code spread across underscore-prefixed files
5. **Naming Inconsistencies**: References to non-existent `_common.py`, unclear module purposes

**Impact**: Makes it harder to find code, add features, onboard contributors, and maintain consistency.

## The Solution

Reorganize into a **layered architecture** following FastAPI/pydantic ecosystem patterns:

```
Foundation → Infrastructure → Application → Presentation
   core/    →  config/       →   domain/   →    api/
            →  providers/    →   semantic/ →    cli/
            →  infrastructure               →   tools/
```

## Key Changes

### 1. Foundation Layer: `core/` Package

**Consolidates**: `_types/`, most of `_data_structures.py`

**Structure**:
```
core/
├── types.py       # BasedModel, BaseEnum, Sentinel, type aliases
├── spans.py       # Span, SpanGroup (location primitives)
├── chunks.py      # CodeChunk, ChunkKind, ChunkSource
├── metadata.py    # SemanticMetadata, Metadata, ExtKind
├── discovery.py   # DiscoveredFile
└── stores.py      # UUIDStore, BlakeStore, hashing
```

**Purpose**: Domain primitives used everywhere. Zero dependencies on other packages.

### 2. Configuration Layer: `config/` Package

**Consolidates**: `settings.py` + splits 900-line `settings_types.py`

**Structure**:
```
config/
├── settings.py    # Main Settings class
├── types.py       # Common config types
├── middleware.py  # Middleware configuration
├── providers.py   # Provider configuration
└── logging.py     # Logging configuration
```

**Purpose**: All configuration in one place with logical decomposition.

### 3. API Layer: `api/` Package

**Consolidates**: `models/core.py`, `models/intent.py`

**Structure**:
```
api/
├── models.py      # CodeMatch, FindCodeResponseSummary
└── intent.py      # IntentResult, QueryIntent
```

**Purpose**: External interface models (what agents see via MCP).

### 4. Application Layer: `domain/` Package

**Renames**: `services/` → `domain/`

**Structure**:
```
domain/
├── indexer.py
├── discovery.py
├── textify.py
└── chunking/      # Nested subdomain
```

**Purpose**: Business logic and application services.

### 5. Infrastructure Layer: `infrastructure/` Package

**Consolidates**: `_logger.py`, `_registry.py`, `_statistics.py`, splits `_utils.py`

**Structure**:
```
infrastructure/
├── logging.py
├── registry.py
├── statistics.py
└── utils/
    ├── git.py
    ├── tokens.py
    └── hashing.py
```

**Purpose**: Cross-cutting technical infrastructure.

### 6. Provider Ecosystem: `providers/` Package

**Consolidates**: `provider.py`, `embedding/`, `reranking/`, `vector_stores/`

**Structure**:
```
providers/
├── base.py            # From provider.py
├── embedding/
├── reranking/
└── vector_stores/
```

**Purpose**: Unified provider system location.

## What Stays the Same

- `semantic/` - Already well-structured
- `middleware/` - Already well-structured
- `tokenizers/` - Already well-structured
- `cli/` - Entry point
- `tools/` - MCP tools
- Root singletons: `exceptions.py`, `language.py`, `_version.py`, etc.

## Impact Metrics

**Before**:
- 15+ root files
- 3 competing type locations
- 4 provider locations
- Unclear module purposes

**After**:
- 8 root files (47% reduction)
- 1 foundation type location
- 1 provider location
- Clear layered architecture

## File Decomposition

**`_data_structures.py`** (640 lines) → 6 focused modules averaging 110 lines each

**`settings_types.py`** (900+ lines) → 4 focused modules averaging 230 lines each

**Result**: No file >300 lines, clear single-responsibility modules

## Import Path Changes

### Public API (Stable)

```python
# No change for public consumers
from codeweaver import BasedModel, Span, CodeChunk, CodeMatch
```

### Internal Imports (Updated)

```python
# Before
from codeweaver._types import BasedModel
from codeweaver._data_structures import Span, CodeChunk
from codeweaver.models.core import CodeMatch

# After
from codeweaver.core.types import BasedModel
from codeweaver.core.spans import Span
from codeweaver.core.chunks import CodeChunk
from codeweaver.api.models import CodeMatch
```

## Constitutional Alignment

✅ **Principle V - Simplicity Through Architecture**
- Flat structure with purposeful grouping
- Clear module boundaries
- Obvious responsibilities

✅ **Principle II - Proven Patterns**
- Matches FastAPI layering
- Follows pydantic organization
- Standard DDD terminology

✅ **Plugin Architecture Requirements**
- All providers unified
- Clear extension points
- Registry pattern maintained

✅ **Type System Discipline**
- Foundation types clearly defined
- Clear hierarchy: foundation → domain → API
- Structured data organization

## Benefits

1. **Clarity**: Purpose obvious from structure
2. **Maintainability**: Related concerns grouped
3. **Scalability**: Room to grow in each package
4. **Discoverability**: Know where to find/add things
5. **Testing**: Clear boundaries enable focused tests
6. **Onboarding**: Structure teaches architecture

## Risks & Mitigations

**Risk**: Large refactor could introduce bugs
**Mitigation**: Comprehensive test coverage, systematic migration

**Risk**: Import path changes break things
**Mitigation**: Public API stays stable, internal imports validated via tests

**Risk**: Temporary disruption during transition
**Mitigation**: Clear migration plan, phased approach possible

## Migration Strategy

### Incremental Approach (8 Phases)

1. **Create Structure** - New directories and placeholders
2. **Move Foundation** - `core/` package
3. **Move Configuration** - `config/` package
4. **Reorganize Providers** - `providers/` package
5. **Reorganize Domain** - `services/` → `domain/`
6. **Consolidate Infrastructure** - `infrastructure/` package
7. **Finalize API** - `models/` → `api/`
8. **Validation** - Tests, imports, public API check

### Validation Gates

After each phase:
- ✅ All tests pass
- ✅ Type checking passes
- ✅ Imports resolve correctly
- ✅ Public API unchanged

## Success Criteria

### Structural
- [ ] <10 root-level files
- [ ] No file >300 lines
- [ ] Clear dependency flow
- [ ] All providers in `providers/`

### Quality
- [ ] All tests pass
- [ ] Type checking passes
- [ ] Linting passes
- [ ] Public API stable

### Documentation
- [ ] Architecture docs updated
- [ ] Import guides updated
- [ ] Contributing guide updated
- [ ] Migration notes complete

## Design Patterns Applied

### Hexagonal Architecture
- **Core** = Domain model
- **Infrastructure** = Technical adapters
- **API** = Driving adapters (MCP)
- **Domain** = Application services

### Dependency Inversion
- Foundation (core) → no dependencies
- Infrastructure → depends on core
- Domain → depends on core + infrastructure
- API → depends on core

### Single Responsibility
- Each package has one clear purpose
- Each module <300 lines
- Clear boundaries prevent mixing concerns

## Next Actions

1. **Review** - Validate design with stakeholders
2. **Approve** - Get go/no-go decision
3. **Plan** - Create detailed implementation plan
4. **Execute** - Systematic migration
5. **Validate** - Comprehensive testing

## Questions for Review

1. ✅ Does the layered architecture make sense?
2. ✅ Are module names clear and intuitive?
3. ✅ Is the foundation/infrastructure/domain/API split logical?
4. ✅ Any concerns about the migration approach?
5. ✅ Should any packages be further subdivided?

## Appendices

- **Full Design**: See `structural_refactor_design.md`
- **Visual Diagrams**: See `structural_refactor_diagram.md`
- **Architecture Reference**: See `../ARCHITECTURE.md`
- **Project Constitution**: See `../.specify/memory/constitution.md`

---

**Recommendation**: Proceed with refactoring. The design aligns with constitutional principles, follows proven patterns, and sets up CodeWeaver for long-term maintainability and growth.
