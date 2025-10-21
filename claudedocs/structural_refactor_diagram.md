# CodeWeaver Architecture Diagram

## Current Structure (Simplified)

```
src/codeweaver/
├── _types/                    ❓ New, incomplete
│   ├── base.py               (BaseEnum, BasedModel)
│   └── sentinel.py           (Sentinel, UNSET)
├── _data_structures.py       ⚠️  640 lines, mixed concerns
├── settings_types.py         ⚠️  900+ lines, needs decomposition
├── models/                    ❓ Unclear boundary with _types
│   ├── core.py
│   └── intent.py
├── services/                  ✅ Well-organized
├── middleware/                ✅ Well-organized
├── semantic/                  ✅ Well-organized
├── embedding/                 ⚠️  Should group with providers
├── reranking/                 ⚠️  Should group with providers
├── vector_stores/             ⚠️  Should group with providers
├── _logger.py                 ⚠️  Infrastructure scattered
├── _registry.py               ⚠️  Infrastructure scattered
├── _utils.py                  ⚠️  Infrastructure scattered
├── _statistics.py             ⚠️  Infrastructure scattered
├── provider.py                ⚠️  Should be with providers
├── settings.py                ✅ OK
├── language.py                ✅ OK
├── exceptions.py              ✅ OK
└── ... (8 more root files)

Issues:
- 15+ root-level files (too crowded)
- Unclear type system boundaries (_types vs models vs _data_structures)
- Provider code scattered (embedding/, reranking/, vector_stores/, provider.py)
- Infrastructure scattered (_logger, _registry, _utils, _statistics)
- Massive files need decomposition
```

## Proposed Structure

```
src/codeweaver/
│
├── 📦 core/                           Foundation Layer (no dependencies)
│   ├── types.py                      ← BasedModel, BaseEnum, Sentinel, type aliases
│   ├── spans.py                      ← Span, SpanGroup (location primitives)
│   ├── chunks.py                     ← CodeChunk, ChunkKind, ChunkSource
│   ├── metadata.py                   ← SemanticMetadata, Metadata, ExtKind
│   ├── discovery.py                  ← DiscoveredFile
│   └── stores.py                     ← UUIDStore, BlakeStore, hashing
│
├── 📦 config/                         Configuration Layer
│   ├── settings.py                   ← Main Settings class
│   ├── types.py                      ← Common config types (was settings_types.py)
│   ├── middleware.py                 ← Middleware config types
│   ├── providers.py                  ← Provider config types
│   └── logging.py                    ← Logging config types
│
├── 📦 api/                            External Interface Layer
│   ├── models.py                     ← CodeMatch, FindCodeResponseSummary
│   └── intent.py                     ← IntentResult, QueryIntent
│
├── 📦 domain/                         Business Logic Layer
│   ├── indexer.py                    ← From services/indexer.py
│   ├── discovery.py                  ← From services/discovery.py
│   ├── textify.py                    ← From services/textify.py
│   └── chunking/                     ← From services/chunker/
│       ├── router.py
│       ├── semantic.py
│       ├── registry.py
│       └── delimiters/
│
├── 📦 infrastructure/                 Cross-Cutting Infrastructure
│   ├── logging.py                    ← From _logger.py
│   ├── registry.py                   ← From _registry.py
│   ├── statistics.py                 ← From _statistics.py
│   └── utils/
│       ├── git.py
│       ├── tokens.py
│       └── hashing.py
│
├── 📦 providers/                      Provider Ecosystem
│   ├── base.py                       ← From provider.py
│   ├── embedding/                    ← Existing embedding/
│   ├── reranking/                    ← Existing reranking/
│   └── vector_stores/                ← Existing vector_stores/
│
├── 📦 semantic/                       AST/Grammar Analysis (unchanged)
│   └── ... (well-structured already)
│
├── 📦 middleware/                     Middleware (unchanged)
│   └── ...
│
├── 📦 tokenizers/                     Tokenization (unchanged)
│   └── ...
│
├── 📦 tools/                          MCP Tools
│   └── ...
│
├── 📦 cli/                            CLI Interface
│   └── ...
│
├── 📄 exceptions.py                   All exceptions (root)
├── 📄 language.py                     Language detection (root)
├── 📄 _capabilities.py                Capabilities system (root)
├── 📄 _constants.py                   Constants (root)
├── 📄 _version.py                     Version info (root)
├── 📄 main.py                         Entry point (root)
└── 📄 __init__.py                     Public API (root)

Benefits:
✅ 8 root files (down from 15+)
✅ Clear type hierarchy (core → domain → API)
✅ Unified provider location
✅ Grouped infrastructure
✅ Obvious module purposes
```

## Dependency Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    External Consumers                        │
│                  (Agents, CLIs, Tests)                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   PUBLIC API (__init__.py)                   │
│   Re-exports: BasedModel, Span, CodeMatch, Settings, etc.   │
└─────────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    ┌─────────┐      ┌─────────┐     ┌─────────┐
    │   api/  │      │  tools/ │     │   cli/  │
    └─────────┘      └─────────┘     └─────────┘
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                     ┌──────────┐
                     │  domain/ │◄────────────┐
                     └──────────┘             │
                           │                  │
          ┌────────────────┼─────────┐        │
          ▼                ▼         ▼        │
    ┌──────────┐    ┌──────────┐ ┌────────┐  │
    │ semantic/│    │middleware│ │tokenize│  │
    └──────────┘    └──────────┘ └────────┘  │
          │                │         │        │
          └────────────────┼─────────┘        │
                           ▼                  │
                  ┌────────────────┐          │
                  │  providers/    │──────────┘
                  └────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
    ┌─────────┐      ┌─────────┐     ┌────────────┐
    │ config/ │      │  core/  │     │infrastructure│
    └─────────┘      └─────────┘     └────────────┘

Legend:
─────►  Depends on
═════►  Foundation (no external dependencies)
```

## Layer Responsibilities

```
┌─────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │   cli/   │  │  tools/  │  │   api/   │                  │
│  │          │  │  (MCP)   │  │ (models) │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
│  External interfaces - what users/agents interact with      │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  APPLICATION LAYER                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │ domain/  │  │ semantic/│  │middleware│                  │
│  │indexer   │  │classifier│  │          │                  │
│  │discovery │  │  scorer  │  │          │                  │
│  │chunking  │  │          │  │          │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
│  Business logic - how the system works                      │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  INFRASTRUCTURE LAYER                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │providers/│  │  config/ │  │infra/    │                  │
│  │embedding │  │ settings │  │ logging  │                  │
│  │reranking │  │  types   │  │ registry │                  │
│  │vector_db │  │          │  │  utils   │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
│  Technical services - supports application layer            │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  FOUNDATION LAYER                                            │
│  ┌─────────────────────────────────────────────┐            │
│  │              core/                          │            │
│  │  types.py    spans.py    chunks.py         │            │
│  │  metadata.py stores.py   discovery.py      │            │
│  └─────────────────────────────────────────────┘            │
│  Domain primitives - fundamental concepts                   │
│  ══► NO DEPENDENCIES (foundation for everything)            │
└─────────────────────────────────────────────────────────────┘
```

## File Decomposition Examples

### Before: `_data_structures.py` (640 lines)

```
_data_structures.py
├── Imports (30 lines)
├── Type Aliases (20 lines)
├── Hashing Functions (50 lines)
├── Span Classes (120 lines)
├── Metadata Classes (80 lines)
├── CodeChunk (150 lines)
├── DiscoveredFile (40 lines)
├── ExtKind Enum (80 lines)
└── Store Classes (70 lines)
```

### After: Split Across `core/`

```
core/
├── types.py          (50 lines)
│   ├── Type aliases
│   ├── BlakeKey, HashKeyKind
│   └── Re-exports from base.py
│
├── spans.py          (150 lines)
│   ├── SpanTuple
│   ├── Span
│   └── SpanGroup
│
├── chunks.py         (180 lines)
│   ├── ChunkKind
│   ├── ChunkSource
│   └── CodeChunk
│
├── metadata.py       (120 lines)
│   ├── SemanticMetadata
│   ├── Metadata
│   └── ExtKind
│
├── discovery.py      (50 lines)
│   └── DiscoveredFile
│
└── stores.py         (120 lines)
    ├── Hashing functions
    ├── UUIDStore
    └── BlakeStore
```

### Before: `settings_types.py` (900+ lines)

```
settings_types.py
├── Imports (40 lines)
├── Middleware Types (200 lines)
├── Provider Types (400 lines)
├── Logging Types (150 lines)
├── Server Types (80 lines)
└── Main Settings Types (30 lines)
```

### After: Split Across `config/`

```
config/
├── types.py          (100 lines)
│   ├── Common types
│   ├── Base settings
│   └── Type unions
│
├── middleware.py     (200 lines)
│   ├── ErrorHandlingMiddlewareSettings
│   ├── RetryMiddlewareSettings
│   ├── LoggingMiddlewareSettings
│   └── RateLimitingMiddlewareSettings
│
├── providers.py      (450 lines)
│   ├── BaseProviderSettings
│   ├── EmbeddingProviderSettings
│   ├── RerankingProviderSettings
│   ├── AgentProviderSettings
│   └── Provider-specific settings
│
└── logging.py        (180 lines)
    ├── LoggingSettings
    ├── HandlersDict
    ├── LoggersDict
    └── Logging configuration types
```

## Migration Path

```
Phase 1: Create Structure
├── Create new directories
├── Create placeholder __init__.py files
└── Verify imports work

Phase 2: Move Foundation
├── Move _types/ → core/types.py
├── Split _data_structures.py → core/*
└── Update imports in moved files

Phase 3: Move Configuration
├── Split settings_types.py → config/*
├── Move settings.py → config/
└── Update imports

Phase 4: Reorganize Providers
├── Create providers/ package
├── Move provider.py → providers/base.py
├── Move embedding/, reranking/, vector_stores/
└── Update imports

Phase 5: Reorganize Domain
├── Rename services/ → domain/
├── Update imports
└── Update references

Phase 6: Consolidate Infrastructure
├── Move _logger.py → infrastructure/logging.py
├── Move _registry.py → infrastructure/registry.py
├── Move _statistics.py → infrastructure/statistics.py
├── Split _utils.py → infrastructure/utils/*
└── Update imports

Phase 7: Finalize API
├── Move models/ → api/
├── Update exports
└── Verify public API stable

Phase 8: Validation
├── Run all tests
├── Verify imports
├── Check public API
└── Update documentation
```

## Success Metrics

✅ **Structural Clarity**
- Module purpose obvious from name and location
- <10 root-level files
- Clear hierarchy of concerns

✅ **Constitutional Alignment**
- Flat structure with purposeful grouping
- FastAPI/pydantic patterns followed
- Plugin architecture clear

✅ **Maintainability**
- Related code grouped together
- No file >300 lines (decomposed appropriately)
- Clear dependency flow

✅ **Discoverability**
- Know where to find things
- Know where to add new things
- Obvious boundaries

---

**Legend**:
- 📦 Package (directory with __init__.py)
- 📄 Module (single .py file)
- ✅ Well-organized
- ⚠️  Needs reorganization
- ❓ Unclear purpose/boundaries
- ◄─ Depends on
- ═► Foundation (no dependencies)
