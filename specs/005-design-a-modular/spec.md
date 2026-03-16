<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Feature Specification: Modular Indexing Pipeline

**Feature Branch**: `005-design-a-modular`
**Created**: 2025-12-27
**Status**: Draft
**Input**: User description: "design a modular indexing capability that can: 1) Identify failures in providers and reroute to backup providers, 2) work with different chunkers, embedding providers, vector stores and databases, and non-file sources, 3) Integrate with file watchers and similar utilities to maintain continuous updates 4) Smartly deduplicates at a granular level (i.e. chunk vice source/file), 5) is fully decoupled from its associated machinery (data sources, chunkers, embedders or specific indexes, storage, watchers/updater triggers)"

## Execution Flow (main)
```
1. Parse user description from Input
   → COMPLETE: Description specifies 5 key capabilities
2. Extract key concepts from description
   → Identified: provider resilience, modularity, continuous updates, deduplication, decoupling
3. For each unclear aspect:
   → Marked with [NEEDS CLARIFICATION] in requirements
4. Fill User Scenarios & Testing section
   → COMPLETE: User flows defined for indexing operations
5. Generate Functional Requirements
   → COMPLETE: Each requirement testable
6. Identify Key Entities
   → COMPLETE: Core abstractions identified
7. Run Review Checklist
   → Status: Spec has some uncertainties marked for clarification
8. Return: SUCCESS (spec ready for planning)
```

---

## ⚡ Quick Guidelines
- ✅ Focus on WHAT users need and WHY
- ❌ Avoid HOW to implement (no tech stack, APIs, code structure)
- 👥 Written for business stakeholders, not developers

---

## User Scenarios & Testing *(mandatory)*

### Primary User Story
As a CodeWeaver operator, I need the indexing system to reliably process code from various sources, automatically recover from component failures, maintain up-to-date indexes through continuous monitoring, avoid duplicate processing of identical content, and allow me to swap out any component (data source, chunker, embedder, storage) without affecting other parts of the system.

### Acceptance Scenarios

1. **Given** the system is indexing a codebase with the primary embedding provider, **When** that provider fails, **Then** the system automatically switches to a backup provider without losing data or requiring manual intervention

2. **Given** a file is being monitored for changes, **When** the file content is updated, **Then** only the changed chunks are re-processed and duplicate content is detected to avoid redundant storage

3. **Given** the system is configured with a specific chunker, **When** the operator switches to a different chunking strategy, **Then** existing indexed content remains accessible and new content uses the new chunker without data loss

4. **Given** multiple data sources are configured (files, databases, APIs), **When** indexing runs, **Then** each source is processed independently with source-appropriate handling while maintaining consistent chunk-level deduplication

5. **Given** the system is running with specific vector store A, **When** the operator migrates to vector store B, **Then** the indexing pipeline continues operating without code changes to chunking or embedding logic

### Edge Cases
- What happens when all configured providers (primary and backups) fail simultaneously?
- How does the system handle partial failures where some chunks succeed and others fail?
- What happens when a file watcher detects rapid successive changes to the same file?
- How does deduplication behave when identical content appears in different files or sources?
- What happens when a provider becomes available again after being marked as failed?
- How does the system handle migration scenarios where both old and new components need to coexist temporarily?

## Requirements *(mandatory)*

### Functional Requirements

#### Provider Resilience & Routing
- **FR-001**: System MUST detect when any provider (chunker, embedder, vector store, data source) fails during operation
- **FR-002**: System MUST automatically route operations to configured backup providers when primary providers fail
- **FR-003**: System MUST track provider health status and availability
- **FR-004**: System MUST support configurable retry policies for transient failures [NEEDS CLARIFICATION: retry count limits, backoff strategies, timeout durations]
- **FR-005**: System MUST log all provider failures and routing decisions for operational visibility
- **FR-006**: System MUST continue processing remaining items when individual items fail [NEEDS CLARIFICATION: error threshold before stopping entire batch?]

#### Multi-Provider Modularity
- **FR-007**: System MUST support multiple interchangeable chunker implementations operating on the same data
- **FR-008**: System MUST support multiple embedding provider types (sparse, dense, hybrid)
- **FR-009**: System MUST support multiple vector store backends simultaneously
- **FR-010**: System MUST support non-file data sources (databases, APIs, streams) in addition to file-based sources
- **FR-011**: System MUST allow operators to add new provider types without modifying core indexing logic
- **FR-012**: System MUST validate provider compatibility before accepting configuration [NEEDS CLARIFICATION: what compatibility checks are required?]

#### Continuous Updates & Integration
- **FR-013**: System MUST integrate with file watching utilities to detect source changes in real-time
- **FR-014**: System MUST process detected changes incrementally without full re-indexing
- **FR-015**: System MUST handle change events from multiple simultaneous sources
- **FR-016**: System MUST support configurable update triggers beyond file watching (scheduled, event-driven, manual)
- **FR-017**: System MUST maintain index consistency during concurrent update operations
- **FR-018**: System MUST provide visibility into update processing status and queue depth

#### Granular Deduplication
- **FR-019**: System MUST identify duplicate chunks based on content, not source location
- **FR-020**: System MUST avoid storing or processing identical chunk content multiple times
- **FR-021**: System MUST maintain references from multiple sources to the same deduplicated chunk
- **FR-022**: System MUST handle chunk deduplication across different data sources (files, databases, etc.)
- **FR-023**: System MUST support configurable deduplication strategies [NEEDS CLARIFICATION: exact match, fuzzy match, semantic similarity?]
- **FR-024**: System MUST update chunk reference counts when sources are added or removed

#### Component Decoupling
- **FR-025**: System MUST operate the indexing pipeline without direct dependencies between components (data source ↔ chunker ↔ embedder ↔ storage)
- **FR-026**: System MUST allow component replacement (swap chunker, embedder, vector store) without affecting other components
- **FR-027**: System MUST use standard data formats for communication between pipeline stages [NEEDS CLARIFICATION: what constitutes "standard" - internal protocol, external format?]
- **FR-028**: System MUST isolate component failures to prevent cascade failures across the pipeline
- **FR-029**: System MUST support running multiple pipeline configurations simultaneously with different component combinations
- **FR-030**: System MUST provide clear boundaries and contracts for component integration

#### Operational Requirements
- **FR-031**: System MUST provide operational controls for pausing, resuming, and canceling indexing operations
- **FR-032**: System MUST report progress metrics for long-running indexing operations
- **FR-033**: System MUST support graceful shutdown that preserves partial indexing state
- **FR-034**: System MUST allow configuration changes without requiring system restart [NEEDS CLARIFICATION: which configuration changes can be applied dynamically?]
- **FR-035**: System MUST maintain audit logs of all indexing operations and configuration changes

### Key Entities *(data involved)*

- **IndexingPipeline**: Represents a complete flow from data source through chunking, embedding, deduplication, to storage. Can be composed of different provider implementations at each stage. Multiple pipelines can run concurrently with different configurations.

- **Provider**: Abstract representation of any pluggable component (data source, chunker, embedder, vector store). Has health status, capabilities description, and failure/success history. Providers are registered and can be designated as primary or backup.

- **Chunk**: Atomic unit of code content with normalized representation. Contains content hash for deduplication, source references (potentially multiple), and processing metadata. Chunks are the primary unit of deduplication.

- **DataSource**: Represents origin of content (file system, database, API, stream). Supports change detection and can emit update events. Independent of downstream processing components.

- **ProviderHealth**: Tracks availability, failure counts, last success/failure timestamps, and routing status for each provider. Used to make automatic failover decisions.

- **UpdateTrigger**: Represents mechanisms for detecting when re-indexing is needed (file watcher events, scheduled tasks, manual requests, external signals). Decoupled from the indexing execution.

- **DeduplicationIndex**: Maintains mapping between chunk content identifiers and storage locations. Tracks reference counts from multiple sources to the same deduplicated content.

- **PipelineConfiguration**: Defines the specific combination of providers for a pipeline instance, including primary and backup providers, retry policies, and deduplication strategies.

---

## Review & Acceptance Checklist
*GATE: Automated checks run during main() execution*

### Content Quality
- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

### Requirement Completeness
- [ ] No [NEEDS CLARIFICATION] markers remain (4 clarifications needed)
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

---

## Execution Status
*Updated by main() during processing*

- [x] User description parsed
- [x] Key concepts extracted
- [x] Ambiguities marked (4 items)
- [x] User scenarios defined
- [x] Requirements generated (35 functional requirements)
- [x] Entities identified (8 key entities)
- [ ] Review checklist passed (pending clarifications)

---

## Open Questions for Clarification

1. **Retry Policies (FR-004)**: What are the acceptable retry count limits, backoff strategies, and timeout durations for transient failures?

2. **Error Thresholds (FR-006)**: Should there be an error threshold (e.g., 10% failure rate) that stops an entire batch, or should processing always continue?

3. **Provider Compatibility (FR-012)**: What specific compatibility checks are required before accepting a provider configuration? (e.g., embedding dimension matching, data format compatibility)

4. **Deduplication Strategies (FR-023)**: Should the system support only exact content match, or also fuzzy matching and semantic similarity for deduplication?

5. **Dynamic Configuration (FR-034)**: Which configuration changes can be applied dynamically without restart, and which require restart?

6. **Communication Formats (FR-027)**: Should components communicate via internal protocol optimized for performance, or external standard formats for maximum interoperability?
