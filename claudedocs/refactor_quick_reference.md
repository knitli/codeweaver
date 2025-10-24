# CodeWeaver Refactor - Quick Reference Guide

**Purpose**: Fast lookup for "where does X go?" during migration

## File Location Mapping

### From `_types/`

| Current | New Location | Notes |
|---------|-------------|-------|
| `_types/base.py` | `core/types.py` | Merge with type aliases |
| `_types/sentinel.py` | `core/types.py` | Include in foundation types |
| `_types/__init__.py` | `core/__init__.py` | Export core types |

### From `_data_structures.py`

| Component | New Location | Reason |
|-----------|-------------|--------|
| Type aliases (BlakeKey, etc.) | `core/types.py` | Foundation types |
| `Span`, `SpanGroup` | `core/spans.py` | Location primitives |
| `CodeChunk`, `ChunkKind`, `ChunkSource` | `core/chunks.py` | Chunk domain |
| `SemanticMetadata`, `Metadata`, `ExtKind` | `core/metadata.py` | Metadata domain |
| `DiscoveredFile` | `core/discovery.py` | Discovery domain |
| `UUIDStore`, `BlakeStore`, hashing | `core/stores.py` | Storage utilities |

### From `settings_types.py`

| Component | New Location | Reason |
|-----------|-------------|--------|
| Common types, base settings | `config/types.py` | Foundation config types |
| `*MiddlewareSettings` | `config/middleware.py` | Middleware config |
| `*ProviderSettings` | `config/providers.py` | Provider config |
| `LoggingSettings`, handlers, etc. | `config/logging.py` | Logging config |
| `UvicornServerSettings` | `config/types.py` | Server config |

### From `models/`

| Current | New Location | Reason |
|---------|-------------|--------|
| `models/core.py` | `api/models.py` | External API models |
| `models/intent.py` | `api/intent.py` | API intent types |

### From Root `_*` Files

| Current | New Location | Reason |
|---------|-------------|--------|
| `_logger.py` | `infrastructure/logging.py` | Logging infrastructure |
| `_registry.py` | `infrastructure/registry.py` | Registry system |
| `_statistics.py` | `infrastructure/statistics.py` | Statistics tracking |
| `_utils.py` (git functions) | `infrastructure/utils/git.py` | Git utilities |
| `_utils.py` (token functions) | `infrastructure/utils/tokens.py` | Token utilities |
| `_utils.py` (other) | `infrastructure/utils/*.py` | Other utilities |

### Provider Files

| Current | New Location | Reason |
|---------|-------------|--------|
| `provider.py` | `providers/base.py` | Provider base |
| `embedding/*` | `providers/embedding/*` | Group providers |
| `reranking/*` | `providers/reranking/*` | Group providers |
| `vector_stores/*` | `providers/vector_stores/*` | Group providers |

### Services → Domain

| Current | New Location | Reason |
|---------|-------------|--------|
| `services/*` | `domain/*` | Rename for clarity |
| `services/chunker/*` | `domain/chunking/*` | Same subdomain |

## Import Path Quick Reference

### Before → After

```python
# Foundation Types
from codeweaver._types import BasedModel, BaseEnum
→ from codeweaver.core.types import BasedModel, BaseEnum

from codeweaver._types import Sentinel, UNSET
→ from codeweaver.core.types import Sentinel, UNSET

# Data Structures
from codeweaver._data_structures import Span, SpanGroup
→ from codeweaver.core.spans import Span, SpanGroup

from codeweaver._data_structures import CodeChunk
→ from codeweaver.core.chunks import CodeChunk

from codeweaver._data_structures import SemanticMetadata
→ from codeweaver.core.metadata import SemanticMetadata

from codeweaver._data_structures import DiscoveredFile
→ from codeweaver.core.discovery import DiscoveredFile

from codeweaver._data_structures import UUIDStore, BlakeStore
→ from codeweaver.core.stores import UUIDStore, BlakeStore

# Configuration
from codeweaver.settings_types import EmbeddingProviderSettings
→ from codeweaver.config.providers import EmbeddingProviderSettings

from codeweaver.settings_types import LoggingMiddlewareSettings
→ from codeweaver.config.middleware import LoggingMiddlewareSettings

from codeweaver.settings_types import LoggingSettings
→ from codeweaver.config.logging import LoggingSettings

# API Models
from codeweaver.models.core import CodeMatch, FindCodeResponseSummary
→ from codeweaver.api.models import CodeMatch, FindCodeResponseSummary

from codeweaver.models.intent import QueryIntent, IntentResult
→ from codeweaver.api.intent import QueryIntent, IntentResult

# Infrastructure
from codeweaver._logger import get_logger
→ from codeweaver.infrastructure.logging import get_logger

from codeweaver._registry import ProviderRegistry
→ from codeweaver.infrastructure.registry import ProviderRegistry

from codeweaver._statistics import SessionStatistics
→ from codeweaver.infrastructure.statistics import SessionStatistics

from codeweaver._utils import get_repo_root
→ from codeweaver.infrastructure.utils.git import get_repo_root

from codeweaver._utils import count_tokens
→ from codeweaver.infrastructure.utils.tokens import count_tokens

# Providers
from codeweaver.provider import BaseProvider
→ from codeweaver.providers.base import BaseProvider

from codeweaver.providers.embedding.providers.voyage import VoyageProvider
→ from codeweaver.providers.embedding.providers.voyage import VoyageProvider

# Domain
from codeweaver.services.indexer import Indexer
→ from codeweaver.domain.indexer import Indexer

from codeweaver.services.chunker import ChunkRouter
→ from codeweaver.domain.chunking import ChunkRouter

# Unchanged (well-structured already)
from codeweaver.semantic import Grammar, Category
from codeweaver.middleware.statistics import StatisticsMiddleware
from codeweaver.tokenizers import TikTokenizer
from codeweaver.cli.app import main
```

## Package Purposes Cheat Sheet

| Package | Purpose | Example Contents |
|---------|---------|------------------|
| `core/` | Domain primitives (foundation) | BasedModel, Span, CodeChunk |
| `config/` | Configuration layer | Settings, provider config |
| `api/` | External interface models | CodeMatch, QueryIntent |
| `domain/` | Business logic | Indexer, chunking, discovery |
| `infrastructure/` | Cross-cutting infrastructure | Logging, registry, utils |
| `providers/` | Provider ecosystem | Embedding, reranking, vector stores |
| `semantic/` | AST/grammar analysis | Grammar, classifier, scorer |
| `middleware/` | FastMCP middleware | Statistics, error handling |
| `tokenizers/` | Tokenization | TikToken, base tokenizer |
| `tools/` | MCP tools | find_code tool |
| `cli/` | CLI interface | CLI app |

## Dependency Rules

```
✅ Allowed Dependencies:

core/          → (nothing - foundation layer)
config/        → core/
api/           → core/
infrastructure → core/, config/
providers/     → core/, config/
domain/        → core/, config/, providers/, infrastructure/
semantic/      → core/, infrastructure/
middleware/    → core/, config/
tools/         → api/, domain/
cli/           → everything (entry point)

❌ Forbidden Dependencies:

core/          ❌→ anything (must be foundation)
config/        ❌→ domain/, api/, providers/
api/           ❌→ domain/, providers/, infrastructure/
infrastructure ❌→ domain/, api/, providers/
```

## Module Size Guidelines

| Target | Purpose |
|--------|---------|
| <100 lines | Type definitions, simple utilities |
| 100-200 lines | Focused modules with single responsibility |
| 200-300 lines | Complex modules with multiple related functions |
| >300 lines | ⚠️ Consider splitting into sub-modules |

## Common Patterns

### Creating New Types

**Foundation types** (used everywhere):
```python
# Add to core/types.py
from typing import NewType
from codeweaver.core.types import LiteralStringT

MyType = NewType("MyType", LiteralStringT)
```

**Domain models** (core concepts):
```python
# Add to core/{domain}.py (e.g., core/chunks.py)
from codeweaver.core.types import BasedModel

class MyDomainModel(BasedModel):
    ...
```

**Configuration types**:
```python
# Add to config/{category}.py
from codeweaver.core.types import BasedModel

class MyConfigSettings(BasedModel):
    ...
```

**API models** (external interface):
```python
# Add to api/models.py
from codeweaver.core.types import BasedModel

class MyAPIResponse(BasedModel):
    ...
```

### Adding New Utilities

**Git-related**: `infrastructure/utils/git.py`
**Token-related**: `infrastructure/utils/tokens.py`
**Hashing-related**: `core/stores.py`
**General**: `infrastructure/utils/{category}.py`

### Adding New Providers

```python
# New embedding provider
providers/embedding/providers/{name}.py

# New reranking provider
providers/reranking/providers/{name}.py

# New vector store
providers/vector_stores/{name}.py
```

## Testing Strategy

### Test File Locations Mirror Source

```
tests/
├── core/              # Tests for core/
├── config/            # Tests for config/
├── api/               # Tests for api/
├── domain/            # Tests for domain/
├── infrastructure/    # Tests for infrastructure/
├── providers/         # Tests for providers/
└── integration/       # Cross-package integration tests
```

### Import Testing

After each migration phase, run:
```bash
# Type checking
mise run check

# Import verification
python -c "from codeweaver.core import *"
python -c "from codeweaver.config import *"
python -c "from codeweaver.api import *"

# Full test suite
mise run test
```

## Migration Checklist

For each file being moved:

- [ ] Create target directory structure
- [ ] Move file to new location
- [ ] Update imports within moved file
- [ ] Update imports in files that import from moved file
- [ ] Update `__init__.py` exports
- [ ] Run tests for affected modules
- [ ] Update documentation if public API
- [ ] Commit changes with clear message

## Common Gotchas

1. **Circular imports**: `core/` must have zero dependencies
2. **Public API**: Maintain exports in `codeweaver/__init__.py`
3. **Type imports**: Use `from __future__ import annotations` for forward refs
4. **Re-exports**: Update all `__init__.py` files in modified packages

## Quick Decision Tree

**"Where does this code go?"**

```
Is it a foundational type/primitive?
├─ Yes → core/
└─ No
   ├─ Is it configuration?
   │  ├─ Yes → config/
   │  └─ No
   │     ├─ Is it external API model?
   │     │  ├─ Yes → api/
   │     │  └─ No
   │     │     ├─ Is it business logic?
   │     │     │  ├─ Yes → domain/
   │     │     │  └─ No
   │     │     │     ├─ Is it infrastructure?
   │     │     │     │  ├─ Yes → infrastructure/
   │     │     │     │  └─ No → Ask for clarification
```

---

**Last Updated**: 2025-10-21
**For**: CodeWeaver Structural Refactoring
**See Also**: `structural_refactor_design.md`, `structural_refactor_diagram.md`
