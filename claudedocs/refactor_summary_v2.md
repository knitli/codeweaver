<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Structural Refactoring - Executive Summary v2

**Status**: Design Complete with Services Deep Dive
**Created**: 2025-10-21 (Updated after services analysis)
**Context**: Pre-release architectural cleanup

## Updates in v2

**Added**:
- Deep analysis of `services/` directory structure
- Specific recommendations for underscore-prefixed files
- `RepoTopography` identified as core domain primitive
- Search/filter infrastructure properly categorized
- Chunking subdomain analysis and recommendations

**Key insight**: `services/` mixes three patterns (orchestrators, subdomains, utilities) that belong in different layers.

---

## The Problem (Updated)

CodeWeaver's source structure has accumulated inconsistencies as it progressed toward release:

1. **Type System Confusion**: Three overlapping locations for types (`_types/`, `_data_structures.py`, `models/`)
2. **Root Crowding**: 15+ files at package root with unclear organization
3. **Provider Fragmentation**: Provider code scattered across 4 locations
4. **Infrastructure Scattered**: Utility code spread across underscore-prefixed files
5. **Services Mixed Concerns**: Orchestrators + subdomains + utilities + infrastructure all in `services/`
6. **Underscore Confusion**: 4 files in services with `_` prefix hiding important domain concepts
7. **Naming Inconsistencies**: References to non-existent `_common.py`, unclear module purposes

**Impact**: Makes it harder to find code, add features, onboard contributors, and maintain consistency.

## The Solution

Reorganize into a **layered architecture** following FastAPI/pydantic ecosystem patterns with proper domain decomposition:

```
Foundation → Infrastructure → Application → Presentation
   core/    →  config/       →   domain/   →    api/
            →  providers/    →   semantic/ →    cli/
            →  infrastructure               →   tools/
```

## Key Changes (Updated with Services Analysis)

### 1. Foundation Layer: `core/` Package

**Consolidates**: `_types/`, most of `_data_structures.py`, **+ `services/_repo_environment.py`**

**Structure**:
```
core/
├── types.py       # BasedModel, BaseEnum, Sentinel, type aliases
├── spans.py       # Span, SpanGroup (location primitives)
├── chunks.py      # CodeChunk, ChunkKind, ChunkSource
├── metadata.py    # SemanticMetadata, Metadata, ExtKind
├── discovery.py   # DiscoveredFile
├── stores.py      # UUIDStore, BlakeStore, hashing
└── topology.py    # ← NEW: RepoTopography, DirectoryPurpose (from services/_repo_environment.py)
```

**Purpose**: Domain primitives used everywhere. Zero dependencies on other packages.

**New in v2**: `topology.py` recognized as foundational domain model (400+ lines of repo structure knowledge).

### 2. Infrastructure Layer: `infrastructure/` Package (Updated)

**Consolidates**: `_logger.py`, `_registry.py`, `_statistics.py`, splits `_utils.py`, **+ search/filter code from services**

**Structure**:
```
infrastructure/
├── logging.py
├── registry.py
├── statistics.py
├── search/                        # ← NEW: Qdrant-adapted search infrastructure
│   ├── __init__.py
│   ├── models.py                 # From services/_match_models.py
│   ├── filters.py                # From services/_filter.py
│   └── decorators.py             # From services/_wrap_filters.py
└── utils/
    ├── git.py
    ├── tokens.py
    ├── hashing.py
    └── formatting.py              # ← NEW: From services/textify.py
```

**Purpose**: Cross-cutting technical infrastructure.

**New in v2**:
- Search/filter primitives grouped as infrastructure subdomain
- Formatting utilities properly categorized
- Clear separation: infrastructure provides tools, domain uses them

### 3. Application Layer: `domain/` Package (Updated)

**Consolidates**: `services/` (renamed and reorganized)

**Structure**:
```
domain/
├── __init__.py
├── indexer.py                     # From services/indexer.py (orchestrator)
├── discovery.py                   # From services/discovery.py (orchestrator)
└── chunking/                      # From services/chunker/ (subdomain, renamed)
    ├── __init__.py
    ├── base.py
    ├── router.py
    ├── semantic.py
    ├── registry.py
    └── delimiters/
        ├── __init__.py
        ├── kinds.py               # From kind.py (renamed to plural for consistency)
        ├── families.py
        ├── patterns.py
        └── custom.py
```

**Purpose**: Business logic and application services.

**New in v2**:
- Removed `_` prefix files (moved to appropriate layers)
- Kept orchestrators flat (`indexer`, `discovery`)
- Kept subdomain nested (`chunking/`)
- Clear pattern: flat for simple, nested for complex

### 4-6. Other Layers (Unchanged from v1)

See original summary for:
- Configuration Layer: `config/` Package
- API Layer: `api/` Package
- Provider Ecosystem: `providers/` Package

## Services Decomposition Details

### What Moved Where

| From `services/` | To | Layer | Reason |
|------------------|-----|-------|--------|
| `_repo_environment.py` | `core/topology.py` | Foundation | Fundamental domain model |
| `_match_models.py` | `infrastructure/search/models.py` | Infrastructure | Qdrant primitives |
| `_filter.py` | `infrastructure/search/filters.py` | Infrastructure | Filter construction |
| `_wrap_filters.py` | `infrastructure/search/decorators.py` | Infrastructure | Decorator utilities |
| `textify.py` | `infrastructure/utils/formatting.py` | Infrastructure | Text utilities |
| `indexer.py` | `domain/indexer.py` | Application | Orchestrator |
| `discovery.py` | `domain/discovery.py` | Application | Orchestrator |
| `chunker/` | `domain/chunking/` | Application | Subdomain (renamed) |

### Nesting Decision Pattern

**Keep Flat** (single module):
- `indexer.py` - Single orchestrator class
- `discovery.py` - Single service class

**Nest as Subdomain** (multiple related modules):
- `chunking/` - 7 modules forming coherent area (strategies, delimiters, registry)

**Future guideline**: Nest when >3 related modules form coherent subdomain, otherwise keep flat.

## Impact Metrics (Updated)

**Before**:
- 15+ root files
- 3 competing type locations
- 4 provider locations
- 4 underscore-prefixed files in services
- Unclear module purposes

**After**:
- 8 root files (47% reduction)
- 1 foundation type location (`core/`)
- 1 provider location (`providers/`)
- 0 underscore-prefixed mysteries
- Clear layered architecture with obvious purposes

## File Decomposition (Updated)

**`_data_structures.py`** (640 lines) → 6 focused modules in `core/` averaging 110 lines each

**`settings_types.py`** (900+ lines) → 4 focused modules in `config/` averaging 230 lines each

**`services/_repo_environment.py`** (400 lines) → `core/topology.py` (recognized as core domain model)

**`services/` flat structure** → Decomposed across three layers:
- Core: `topology.py`
- Infrastructure: `search/` subdomain, `utils/formatting.py`
- Domain: `indexer.py`, `discovery.py`, `chunking/` subdomain

**Result**: No file >400 lines, clear single-responsibility modules, proper layering

## Import Path Changes (Updated with Services)

### Public API (Stable)

```python
# No change for public consumers
from codeweaver import BasedModel, Span, CodeChunk, CodeMatch
```

### Internal Imports (Updated)

```python
# Foundation types
from codeweaver._types import BasedModel
→ from codeweaver.core.types import BasedModel

from codeweaver._data_structures import Span, CodeChunk
→ from codeweaver.core.spans import Span
→ from codeweaver.core.chunks import CodeChunk

# Domain models (NEW)
from codeweaver.services._repo_environment import RepoTopography
→ from codeweaver.core.topology import RepoTopography

# Infrastructure (NEW)
from codeweaver.services._match_models import Filter
→ from codeweaver.infrastructure.search.models import Filter

from codeweaver.services.textify import humanize
→ from codeweaver.infrastructure.utils.formatting import humanize

# Domain services
from codeweaver.services.indexer import Indexer
→ from codeweaver.domain.indexer import Indexer

from codeweaver.services.chunker import ChunkRouter
→ from codeweaver.domain.chunking import ChunkRouter

# API models
from codeweaver.models.core import CodeMatch
→ from codeweaver.api.models import CodeMatch
```

## Constitutional Alignment (Validated)

✅ **Principle V - Simplicity Through Architecture**
- Flat structure with purposeful grouping
- Clear module boundaries
- Obvious responsibilities
- Nest only when complexity warrants it (proven with chunking analysis)

✅ **Principle II - Proven Patterns**
- Matches FastAPI layering
- Follows pydantic organization
- Hexagonal architecture (core/infrastructure/domain)
- Standard DDD terminology

✅ **Plugin Architecture Requirements**
- All providers unified
- Clear extension points
- Registry pattern maintained

✅ **Type System Discipline**
- Foundation types clearly defined in `core/`
- Clear hierarchy: foundation → domain → API
- Structured data organization
- No underscore-prefix mysteries

## Deep Dive Documents

1. **`structural_refactor_design.md`** - Full specification
2. **`structural_refactor_diagram.md`** - Visual diagrams
3. **`services_analysis_addendum.md`** - Services deep dive (NEW)
4. **`refactor_quick_reference.md`** - Migration guide

## Benefits (Enhanced)

1. **Clarity**: Purpose obvious from structure
2. **Maintainability**: Related concerns grouped by layer
3. **Scalability**: Room to grow in each package
4. **Discoverability**: Know where to find/add things
5. **Testing**: Clear boundaries enable focused tests
6. **Onboarding**: Structure teaches architecture
7. **No Underscore Mysteries**: All files have clear, positive names (NEW)
8. **Proper Layering**: Core → Infrastructure → Domain clearly enforced (NEW)
9. **Domain Recognition**: Important concepts like RepoTopography properly elevated (NEW)

## Risks & Mitigations

**Risk**: Large refactor could introduce bugs
**Mitigation**: Comprehensive test coverage, systematic migration, phase-by-phase validation

**Risk**: Import path changes break things
**Mitigation**: Public API stays stable, internal imports validated via tests

**Risk**: Deeper nesting increases complexity
**Mitigation**: Only nest when warranted (chunking = 7 modules), keep simple things flat

**Risk**: Team disagrees on layering decisions
**Mitigation**: Constitutional principles provide clear decision framework

## Migration Strategy (Updated)

### Incremental Approach (9 Phases - Updated)

1. **Create Structure** - New directories and placeholders
2. **Move Foundation** - `core/` package (including topology from services)
3. **Move Configuration** - `config/` package
4. **Reorganize Providers** - `providers/` package
5. **Reorganize Infrastructure** - `infrastructure/` package (including search from services)
6. **Reorganize Domain** - `services/` → `domain/` (remaining orchestrators and subdomains)
7. **Finalize API** - `models/` → `api/`
8. **Validation** - Tests, imports, public API check
9. **Documentation** - Update all architectural docs

### Validation Gates

After each phase:
- ✅ All tests pass
- ✅ Type checking passes
- ✅ Imports resolve correctly
- ✅ Public API unchanged
- ✅ No `_` prefix files without justification

## Success Criteria (Updated)

### Structural
- [ ] <10 root-level files
- [ ] No file >400 lines (relaxed from 300 given topology complexity)
- [ ] Clear dependency flow
- [ ] All providers in `providers/`
- [ ] Zero underscore-prefixed files (except true internals like `_version.py`)
- [ ] RepoTopography in `core/` as foundational model

### Quality
- [ ] All tests pass
- [ ] Type checking passes
- [ ] Linting passes
- [ ] Public API stable
- [ ] Import paths validated

### Documentation
- [ ] Architecture docs updated
- [ ] Import guides updated
- [ ] Contributing guide updated
- [ ] Migration notes complete
- [ ] Layering principles documented

## Key Decisions Summary

### Services Decomposition Decisions

1. **RepoTopography → Core**: Foundational domain primitive, not service detail
2. **Search/Filter → Infrastructure**: Qdrant-adapted tools, not domain logic
3. **Textify → Infrastructure Utils**: Pure formatting utilities
4. **Indexer/Discovery → Domain Flat**: Simple orchestrators, don't need nesting
5. **Chunking → Domain Nested**: Complex subdomain with 7 modules
6. **No Underscore Prefixes**: Everything has clear, positive name

### Nesting Guidelines Established

- **Flat**: Single orchestrator or <3 related modules
- **Nested**: >3 related modules forming coherent subdomain
- **Example**: Chunking (7 modules) nested, Indexer (1 module) flat

---

**Recommendation**: Proceed with refactoring. The design aligns with constitutional principles, follows proven patterns, and sets up CodeWeaver for long-term maintainability and growth.

**v2 Enhancement**: Services analysis validates layering approach and provides concrete examples of when to nest vs. keep flat.
