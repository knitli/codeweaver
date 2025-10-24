<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Services Directory Decomposition Analysis

## Key Findings

### Current Structure Problems

**Services directory mixes three patterns**:
1. **Orchestrators**: `indexer.py`, `discovery.py` (high-level coordination)
2. **Subdomains**: `chunker/` (7 modules, complex internal organization)
3. **Utilities**: `textify.py`, filter code (helpers and infrastructure)

**Underscore-prefix confusion**:
- `_repo_environment.py` (400 lines) - Actually core domain model, not implementation detail
- `_match_models.py` - Qdrant-adapted filter models
- `_filter.py` - Filter construction logic
- `_wrap_filters.py` - Decorator infrastructure
- `textify.py` - Text formatting utilities (no underscore, but utility)

### Recommended Decomposition

**Core layer** (`core/topology.py`):
- `_repo_environment.py` → `core/topology.py`
- Rationale: `RepoTopography` is foundational domain primitive (what a repo IS)

**Infrastructure layer** (`infrastructure/`):
- `_match_models.py` → `infrastructure/search/models.py`
- `_filter.py` → `infrastructure/search/filters.py`
- `_wrap_filters.py` → `infrastructure/search/decorators.py`
- `textify.py` → `infrastructure/utils/formatting.py`
- Rationale: Qdrant-adapted tools and utilities support domain, not part of it

**Domain layer** (`domain/`):
- `indexer.py` → `domain/indexer.py` (keep flat - single orchestrator)
- `discovery.py` → `domain/discovery.py` (keep flat - single orchestrator)
- `chunker/` → `domain/chunking/` (keep nested - complex subdomain)
- Rationale: Business logic orchestrators and subdomains

### Nesting Decision Framework

**Established pattern from analysis**:
- **Flat**: Single orchestrator or <3 related modules
- **Nested subdomain**: >3 related modules forming coherent area
- **Example**: Chunking (7 modules) nested ✓, Indexer (1 module) flat ✓

**Future guideline**:
When adding new domain area, nest if:
- Multiple strategies/implementations
- Registry or factory pattern
- >3 closely related modules
- Clear internal boundaries

Otherwise keep flat.

### Attribution vs Organization

**Important principle**: Qdrant-adapted code attribution != organization

**Qdrant copyright preserved** in headers:
- `_match_models.py` 
- `_filter.py`
- `_wrap_filters.py`

**But organized by purpose**:
- Models = domain models for search
- Filters = filter construction
- Decorators = decorator infrastructure

Moved to `infrastructure/search/` as coherent subdomain.

### Key Insights

1. **RepoTopography is core**: 400 lines of repository structure knowledge - foundational concept
2. **Search is infrastructure**: Qdrant-specific primitives supporting domain
3. **Services = domain**: After decomposition, what remains is application logic
4. **Underscore removal**: All files get clear, positive names
5. **Chunking pattern works**: Proven model for future subdomains

## Documents Created

1. `services_analysis_addendum.md` - Deep analysis with rationale
2. `refactor_summary_v2.md` - Updated executive summary

## Impact

**Services files**: 11 → Decomposed to 3 layers
**Underscore files**: 4 → 0
**Clear nesting pattern**: Established for future development
**RepoTopography**: Elevated to core domain primitive

## Constitutional Compliance

✅ Simplicity: Flat when simple, nested when complex (proven pattern)
✅ Proven Patterns: Hexagonal architecture (core/infrastructure/domain)
✅ Type Discipline: Foundation in core, infrastructure separate, domain builds on both
