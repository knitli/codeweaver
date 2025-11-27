<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Implementation Plan: CodeWeaver v0.1 Release

**Branch**: `003-our-aim-to` | **Date**: 2025-10-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/home/knitli/codeweaver/specs/003-our-aim-to/spec.md`

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
**Feature**: CodeWeaver v0.1 MVP Release - Complete integration of indexing, search, and MCP/CLI interfaces with hybrid search and semantic ranking.

**Primary Requirements**:
- Full-stack integration: server startup → indexing → search → results
- Hybrid search combining dense (VoyageAI) + sparse (FastEmbed Splade) vectors
- Reranking with VoyageAI-rerank-2.5 and semantic classification weighting
- Dual interfaces: CLI commands and MCP `find_code` tool
- Health monitoring, error handling, graceful degradation
- Working Quickstart documentation with accurate feature representation

**Technical Approach** (from research):
- FastMCP server framework for MCP protocol
- Qdrant local vector store with persistence
- VoyageAI for embeddings and reranking (with FastEmbed fallback)
- AST-based chunking via ast-grep-py
- Constitutional compliance: AI-first context, proven patterns (pydantic ecosystem), evidence-based development

## Technical Context
**Language/Version**: Python 3.12+
**Primary Dependencies**: FastMCP, qdrant-client, voyageai, ast-grep-py, pydantic, cyclopts, fastembed, rignore
**Storage**: Qdrant vector database (local in-memory with persistence for dev)
**Testing**: pytest with markers (unit, integration, e2e, benchmark, network)
**Target Platform**: Linux/macOS servers (WSL2 supported), CLI and MCP server
**Project Type**: single (Python package with CLI and MCP server)
**Performance Goals**: <3s search for ≤10k files, <10s for ≤100k files, ≥100 files/min indexing
**Constraints**: <200ms p95 for health endpoint, 30s timeout for external APIs, 2GB max memory per indexing session
**Scale/Scope**: v0.1 target: ≤50k files (warn at 50k, error at 500k), single codebase, local deployment

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**AI-First Context**: ✅ PASS
- Feature delivers semantic code search optimized for AI agent consumption
- MCP `find_code` tool provides structured context with relevance scoring
- Semantic classification (AgentTask, IntentType) designed for AI workflows
- Response formats (FindCodeResponseSummary) optimized for agent parsing

**Proven Patterns**: ✅ PASS
- FastMCP framework (proven MCP server pattern from FastAPI creators)
- Pydantic ecosystem: BaseModel for all data structures, pydantic-settings for config
- Plugin architecture via Protocol-based interfaces (EmbeddingProvider, VectorStoreProvider)
- Cyclopts for CLI (established pattern for modern Python CLIs)
- Qdrant vector database (proven in production semantic search systems)

**Evidence-Based**: ✅ PASS
- All dependencies from existing pyproject.toml (verified installed)
- VoyageAI, FastEmbed, Qdrant integration patterns from official docs
- Performance targets based on spec requirements (FR-037, FR-038)
- Error handling patterns (circuit breaker, exponential backoff) from spec clarifications
- No mock implementations allowed per constitution

**Testing Philosophy**: ✅ PASS
- Reference test suite requirement (FR-036): 20+ real query/result pairs
- Integration tests for complete workflows: index → search → results
- Contract tests for API schemas (find_code tool interface)
- Focus on user-affecting behavior: search quality, error handling, graceful degradation
- Effectiveness metrics: Precision@3 ≥70%, Precision@5 ≥80%

**Simplicity**: ✅ PASS
- Flat package structure: src/codeweaver/{core,semantic,agent_api,server,cli,middleware}
- Single tool interface: `find_code` vs multiple specialized endpoints
- Plugin registry pattern for extensibility without complexity
- Clear separation: chunking → embedding → vector store → search → ranking
- Obvious purpose: each module name describes its function clearly

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

**Structure Decision**: Option 1 (Single project) - Python package with CLI and MCP server, no separate frontend/backend needed

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
- Load `.specify/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- **Contract Tests** (from contracts/):
  - find_code MCP tool contract test [P]
  - CLI commands contract tests [P]
  - Health endpoint contract test [P]
- **Entity Models** (from data-model.md):
  - Core entities: CodeChunk, DiscoveredFile, CodeMatch, FindCodeResponseSummary [P]
  - Intent system: IntentType, QueryIntent, AgentTask [P]
  - Semantic system: SemanticClass, ImportanceScores [P]
  - Enums and type aliases: Span, ChunkSource, CodeMatchType, SearchStrategy [P]
- **Integration Tests** (from quickstart.md scenarios):
  - Scenario 1: Server startup + indexing workflow
  - Scenario 2: CLI search workflow
  - Scenario 3: Health monitoring workflow
  - Scenario 4: MCP tool integration workflow
  - Scenario 5: Error recovery + graceful degradation
  - Scenario 6: Reference test suite (dogfooding)
- **Implementation Tasks** (to make tests pass):
  - Provider implementations (embedding, vector store, reranking)
  - Pipeline implementation (chunking → embedding → indexing → search → ranking)
  - CLI command handlers (server, search, config, status)
  - MCP find_code tool implementation
  - Health endpoint implementation
  - Error handling and circuit breaker logic

**Ordering Strategy**:
- **TDD order**: Contract tests → Entity models → Integration tests → Implementation
- **Dependency order**:
  1. Core models (CodeChunk, Span, enums)
  2. Provider interfaces and implementations
  3. Pipeline components (chunking, embedding, indexing)
  4. Search and ranking logic
  5. API layer (MCP tool, CLI commands)
  6. Health monitoring and error handling
- **Parallelization**: Mark [P] for independent tasks (different files/modules)

**Task Categories**:
1. **Setup & Configuration** (1-2 tasks)
   - Verify constitution compliance, validate dependencies
2. **Contract Tests** (3 tasks, all [P])
   - Create failing tests for MCP tool, CLI, health endpoint
3. **Core Models** (8-10 tasks, mostly [P])
   - Implement Pydantic models with validation
4. **Provider System** (6-8 tasks)
   - Implement plugin architecture and concrete providers
5. **Pipeline Implementation** (10-12 tasks)
   - Chunking, embedding, indexing, search, ranking
6. **API Layer** (6-8 tasks)
   - MCP tool, CLI commands, health endpoint
7. **Integration Tests** (6 tasks)
   - End-to-end scenario validation
8. **Documentation** (2-3 tasks)
   - Update README with Quickstart, verify accuracy

**Estimated Output**: 42-50 numbered, ordered tasks in tasks.md

**Quality Gates**:
- All contract tests must fail initially (no implementation)
- All entity models must have round-trip serialization tests
- Integration tests must cover all quickstart scenarios
- Reference test suite must be runnable (even if failing pre-implementation)

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
- [x] Phase 0: Research complete (/plan command) - ✅ research.md created
- [x] Phase 1: Design complete (/plan command) - ✅ data-model.md, contracts/, quickstart.md, agent context updated
- [x] Phase 2: Task planning complete (/plan command - describe approach only) - ✅ Approach documented below
- [ ] Phase 3: Tasks generated (/tasks command) - Next: Run /tasks command
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS - All constitutional principles verified
- [x] Post-Design Constitution Check: PASS - Design maintains constitutional compliance
- [x] All NEEDS CLARIFICATION resolved - No unknowns in Technical Context
- [x] Complexity deviations documented - No deviations, Complexity Tracking table empty

---
*Based on Constitution v2.0.0 - See `/memory/constitution.md`*
