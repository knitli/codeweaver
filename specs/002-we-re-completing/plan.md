<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Implementation Plan: Vector Storage Provider System

**Branch**: `002-we-re-completing` | **Date**: 2025-10-25 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/home/knitli/codeweaver-002-we-re-completing/specs/002-we-re-completing/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Fill the Constitution Check section based on the content of the constitution document.
4. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
5. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
6. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file (e.g., `CLAUDE.md` for Claude Code, `.github/copilot-instructions.md` for GitHub Copilot, `GEMINI.md` for Gemini CLI, `QWEN.md` for Qwen Code or `AGENTS.md` for opencode).
7. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
8. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
9. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
Complete the vector storage provider system for CodeWeaver, implementing Qdrant (database) and in-memory providers that store both sparse and dense embeddings for hybrid search. The system must integrate with existing CodeWeaver types, handle multiple indexes per project, support incremental updates, and enable both local and remote Qdrant deployments with configurable provider-specific settings.

## Technical Context
**Language/Version**: Python 3.11+ (supports 3.11, 3.12, 3.13, 3.14)
**Primary Dependencies**: FastAPI/FastMCP ecosystem, pydantic 2.12+, pydantic-settings, qdrant-client 1.15+, pydantic-graph 1.4+
**Storage**: Qdrant vector database (local/remote), JSON-based persistence for in-memory provider
**Testing**: pytest with contract tests, integration tests, async support
**Target Platform**: Linux/macOS/Windows servers, local development environments
**Project Type**: single (MCP server with plugin architecture)
**Performance Goals**: Support any codebase size; local deployment for <10k files, server deployment for 10k+ files or 1M+ embeddings; hybrid search latency flexible based on deployment
**Constraints**: Eventual consistency acceptable for background indexing; concurrent reads required; embedding dimension validation on upsert
**Scale/Scope**: 2 vector store providers (Qdrant, in-memory), hybrid search (sparse+dense indexes), incremental file updates, project-wide collections

## Constitution Check (Initial - Pre-Research)
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**AI-First Context**: ✅ PASS - Vector storage enables precise code context delivery to AI agents through semantic search. Plugin architecture supports AI consumption as primary interface.

**Proven Patterns**: ✅ PASS - Leverages qdrant-client (battle-tested vector DB), pydantic ecosystem patterns (BaseModel, Settings), FastMCP dependency injection. Follows established VectorStoreProvider abstract interface already in codebase.

**Evidence-Based**: ✅ PASS - Qdrant provider scaffolded in codebase (src/codeweaver/providers/vector_stores/qdrant.py), VectorStoreProvider abstract interface exists (base.py), qdrant-client in dependencies (pyproject.toml), technical docs available (data/context/apis/qdrant-client.md). Clarifications resolved in spec.md.

**Testing Philosophy**: ✅ PASS - Focus on integration tests for search/upsert/delete workflows, contract tests for provider interface compliance, realistic hybrid search scenarios. Effectiveness over coverage.

**Simplicity**: ✅ PASS - Flat provider structure (src/codeweaver/providers/vector_stores/), plugin registry pattern already established, single abstract interface with clear purpose. Two concrete implementations (Qdrant, in-memory) follow same pattern.

## Constitution Check (Post-Design - After Phase 1)
*Re-evaluation after completing research, data model, and contract design.*

**AI-First Context**: ✅ PASS - Design enhances AI agent context:
- Hybrid search (sparse+dense) provides both semantic and keyword matching
- Rich metadata payload enables precise filtering (language, file path, line ranges)
- SearchResult includes relevance scores and search metadata for AI decision-making
- Filter against current filesystem prevents stale results confusing agents

**Proven Patterns**: ✅ PASS - Design follows ecosystem patterns:
- Named vectors pattern from Qdrant best practices (research.md:Decision 1)
- AsyncQdrantClient aligns with FastMCP async-first patterns (research.md:Decision 2)
- Pydantic BaseSettings for hierarchical configuration (data-model.md:VectorStoreProviderSettings)
- Provider registry pattern matches existing embedding/reranking providers
- JSON persistence using pydantic serialization (proven pattern for config/state)

**Evidence-Based**: ✅ PASS - All design decisions backed by evidence:
- Qdrant named vectors documented in qdrant-client.md:76-87
- In-memory mode confirmed in qdrant-client.md:52
- Hybrid search API verified in qdrant-client.md:154-157
- Performance characteristics researched and documented (data-model.md:Performance Characteristics)
- All technical decisions in research.md include evidence section

**Testing Philosophy**: ✅ PASS - Test strategy focuses on effectiveness:
- Quickstart.md contains 9 executable integration test scenarios
- Each scenario maps to specific acceptance criteria from spec
- Contract tests verify provider interface compliance (contracts/*.yaml)
- No mock-heavy unit tests - focus on realistic workflows
- Performance validation scenarios included (scale limits, search latency)

**Simplicity**: ✅ PASS - Design maintains simplicity:
- Single VectorStoreProvider abstract interface (7 methods total)
- Two concrete providers: QdrantVectorStoreProvider, MemoryVectorStoreProvider
- Flat structure: no deep inheritance hierarchies
- Clear separation: Qdrant for production, Memory for dev/testing
- Configuration follows pydantic-settings patterns (simple hierarchy)
- No unnecessary abstractions: leverages Qdrant's own in-memory mode for Memory provider

**No New Constitutional Violations Identified** - Design adheres to all constitutional principles.

## Project Structure

### Documentation (this feature)
```
specs/[###-feature]/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
# Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure]
```

**Structure Decision**: Option 1 (Single project) - MCP server with plugin architecture. Source in `src/codeweaver/providers/vector_stores/`, tests in `tests/`.

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context** above:
   - For each NEEDS CLARIFICATION → research task
   - For each dependency → best practices task
   - For each integration → patterns task

2. **Generate and dispatch research agents**:
   ```
   For each unknown in Technical Context:
     Task: "Research {unknown} for {feature context}"
   For each technology choice:
     Task: "Find best practices for {tech} in {domain}"
   ```

3. **Consolidate findings** in `research.md` using format:
   - Decision: [what was chosen]
   - Rationale: [why chosen]
   - Alternatives considered: [what else evaluated]

**Output**: research.md with all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - One test file per endpoint
   - Assert request/response schemas
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Each story → integration test scenario
   - Quickstart test = story validation steps

5. **Update agent file incrementally** (O(1) operation):
   - Run `.specify/scripts/bash/update-agent-context.sh roo`
     **IMPORTANT**: Execute it exactly as specified above. Do not add or remove any arguments.
   - If exists: Add only NEW tech from current plan
   - Preserve manual additions between markers
   - Update recent changes (keep last 3)
   - Keep under 150 lines for token efficiency
   - Output to repository root

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, agent-specific file

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:

1. **Contract Test Tasks** (from contracts/*.yaml):
   - Task per provider: QdrantVectorStoreProvider contract tests [P]
   - Task per provider: MemoryVectorStoreProvider contract tests [P]
   - Task: VectorStoreProvider abstract interface validation
   - Each verifies all methods match contract specifications

2. **Data Model Tasks** (from data-model.md):
   - Task: Create QdrantConfig pydantic model
   - Task: Create MemoryConfig pydantic model
   - Task: Create VectorStoreProviderSettings for unified configuration
   - Task: Create CollectionMetadata model for validation
   - Task: Extend CodeChunk metadata for embedding completeness tracking
   - Mark [P] for independent model files

3. **Core Implementation Tasks** (TDD order):
   - Task: Implement QdrantVectorStoreProvider._initialize() (connection + collection setup)
   - Task: Implement QdrantVectorStoreProvider.search() with hybrid support
   - Task: Implement QdrantVectorStoreProvider.upsert() with batch processing
   - Task: Implement QdrantVectorStoreProvider.delete_by_file/id/name()
   - Task: Implement QdrantVectorStoreProvider._validate_provider_compatibility()
   - Task: Implement MemoryVectorStoreProvider._persist_to_disk()
   - Task: Implement MemoryVectorStoreProvider._restore_from_disk()
   - Task: Implement MemoryVectorStoreProvider periodic persistence task

4. **Integration Test Tasks** (from quickstart.md):
   - Task: Scenario 1 - Hybrid embeddings storage and search
   - Task: Scenario 2 - Persistence across restarts
   - Task: Scenario 3 - Hybrid search ranking
   - Task: Scenario 4 - In-memory provider with disk persistence
   - Task: Scenario 5 - Incremental file updates
   - Task: Scenario 6 - Custom configuration
   - Task: Scenario 8 - Provider switch detection
   - Task: Scenario 9 - Partial embeddings handling
   - Mark [P] for independent test files

5. **Supporting Infrastructure Tasks**:
   - Task: Integrate VectorStoreProviderSettings into CodeWeaverSettings
   - Task: Create provider registry integration for vector stores
   - Task: Implement provider factory/builder pattern
   - Task: Add error types (ProviderSwitchError, DimensionMismatchError)
   - Task: Create migration utilities (memory → qdrant)

6. **Documentation Tasks**:
   - Task: Update ARCHITECTURE.md with vector store system
   - Task: Create provider configuration examples
   - Task: Document provider switching workflow
   - Task: Create troubleshooting guide

**Ordering Strategy**:
1. **Phase 1: Foundation** (Parallel)
   - Data models [P]
   - Error types [P]
   - Contract test setup [P]

2. **Phase 2: Qdrant Provider** (Sequential with parallel tests)
   - Qdrant implementation (sequential: init → search → upsert → delete)
   - Qdrant contract tests (can run in parallel with implementation)

3. **Phase 3: Memory Provider** (Sequential with parallel tests)
   - Memory implementation (sequential: init → persist → restore)
   - Memory contract tests (parallel with implementation)

4. **Phase 4: Integration** (Sequential)
   - Settings integration
   - Provider registry
   - Factory pattern

5. **Phase 5: Validation** (Parallel)
   - Integration tests [P]
   - Documentation [P]

**Dependency Graph**:
```
Models → [Qdrant Impl, Memory Impl] → Integration → Tests
   ↓                                        ↓
Error Types                         Documentation
```

**Estimated Task Count**: ~35-40 tasks
- 10 data model tasks
- 8 Qdrant implementation tasks
- 6 Memory implementation tasks
- 8 integration test tasks
- 4 infrastructure tasks
- 4 documentation tasks

**Parallel Execution Opportunities**: ~18 tasks marked [P]
- All data model tasks can run in parallel
- Contract tests can run in parallel with implementation
- Integration test files can run in parallel
- Documentation tasks can run in parallel

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |


## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command) ✅
- [x] Phase 1: Design complete (/plan command) ✅
- [x] Phase 2: Task planning complete (/plan command - describe approach only) ✅
- [ ] Phase 3: Tasks generated (/tasks command) - NOT IN SCOPE FOR /plan
- [ ] Phase 4: Implementation complete - NOT IN SCOPE FOR /plan
- [ ] Phase 5: Validation passed - NOT IN SCOPE FOR /plan

**Gate Status**:
- [x] Initial Constitution Check: PASS ✅
- [x] Post-Design Constitution Check: PASS ✅
- [x] All NEEDS CLARIFICATION resolved ✅
- [x] Complexity deviations documented: NONE (no deviations) ✅

**Artifacts Generated**:
- [x] plan.md (this file) ✅
- [x] research.md ✅
- [x] data-model.md ✅
- [x] contracts/vector-store-provider.yaml ✅
- [x] contracts/qdrant-provider.yaml ✅
- [x] contracts/memory-provider.yaml ✅
- [x] quickstart.md ✅
- [x] .roo/rules/specify-rules.md (agent context updated) ✅

**Execution Summary**:
- Feature: Vector Storage Provider System
- Branch: 002-we-re-completing
- Technical decisions: 8 major decisions documented with evidence
- Contract specifications: 3 provider contracts defined
- Test scenarios: 9 integration test scenarios in quickstart
- Estimated implementation tasks: 35-40 tasks
- Parallel execution opportunities: ~18 tasks

**Next Steps** (for /tasks command):
1. Run `/tasks` to generate tasks.md from this plan
2. Tasks will be ordered by dependency with [P] markers for parallelization
3. Implementation follows TDD: tests before code
4. Validation via quickstart scenarios and contract tests

---
*Based on Constitution v2.0.1 - See `.specify/memory/constitution.md`*

**STATUS**: ✅ PLAN COMPLETE - Ready for /tasks command
