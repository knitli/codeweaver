<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Implementation Plan: PyPI Build and Publishing System

**Branch**: `004-we-re-preparing` | **Date**: 2025-10-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-we-re-preparing/spec.md`

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
Create a reliable, reproducible build and publishing system for CodeWeaver v0.1.0 release to PyPI. The system must automate package building with correct metadata, support version management integrated with existing uv-versioning and changeset workflows, and enable CI/CD automation with GitHub Actions OAuth-based trusted publishing. All packages must be tested across Python 3.12-3.14 before publication.

## Technical Context
**Language/Version**: Python 3.12+ (minimum supported version per project requirements)
**Primary Dependencies**: uv (package manager), uv-versioning (automatic versioning), build backends (to be determined in research), changesets (version management workflow), GitHub Actions (CI/CD)
**Storage**: N/A (build artifacts are ephemeral, cleaned after publication)
**Testing**: pytest (existing test framework, CI validates Python 3.12-3.14 compatibility)
**Target Platform**: PyPI (production), TestPyPI (testing), GitHub Actions runners (build environment)
**Project Type**: single (Python package library)
**Performance Goals**: Build completion in "reasonable time" (baseline to be measured during research, optimization targets TBD)
**Constraints**: Must integrate with existing uv-versioning (automatic per-commit versions), must integrate with existing changeset workflow, must use GitHub Actions OAuth trusted publishing (already configured), CI testing must pass on Python 3.12-3.14 before publication allowed
**Scale/Scope**: Single package (codeweaver-mcp), initial v0.1.0 release, support for automated releases on tagged commits

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**AI-First Context**: ✓ Build system enables reliable package distribution, allowing AI agents and users to install and use CodeWeaver consistently. Clear metadata and documentation enhance discoverability.

**Proven Patterns**: ✓ Leverages Python packaging ecosystem standards (PEP 517/518/621), uv tooling, GitHub Actions workflows, and PyPI trusted publishing - all proven, widely-adopted patterns.

**Evidence-Based**: ✓ All decisions will be backed by research into Python packaging best practices, existing uv-versioning integration points, and GitHub Actions OAuth documentation. No placeholder implementations.

**Testing Philosophy**: ✓ Integration testing approach: CI validates package installation and compatibility across Python 3.12-3.14 before allowing publication. Contract tests verify package metadata correctness.

**Simplicity**: ✓ Single-purpose build system with clear integration points. Flat structure using existing project conventions. Delegates version management to uv-versioning, authentication to GitHub Actions OAuth, testing to existing CI pipeline.

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

**Structure Decision**: Option 1 (Single project) - This is a Python package library, not a web or mobile application

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

The `/tasks` command will create tasks.md following TDD approach, organized into clear phases:

### Configuration Tasks
1. **Update pyproject.toml metadata** - Add all PEP 621 required fields
2. **Configure build backend** - Set up hatchling with uv-versioning plugin
3. **Configure GitHub Actions workflows** - Create publish.yml for PyPI, publish-test.yml for TestPyPI

### Contract Test Tasks (must be written BEFORE implementation)
4. **[P] Contract test: validate_build_output** - Test build creates 2 artifacts with correct names
5. **[P] Contract test: validate_twine_check** - Test metadata validation passes
6. **[P] Contract test: validate_version_derivation** - Test version derived from git state correctly
7. **[P] Contract test: validate_publish_output** - Test package installable from PyPI/TestPyPI

### Implementation Tasks
8. **Ensure build dependencies installed** - Add hatchling, uv-versioning to build-system.requires
9. **Configure metadata validation** - Set up twine check in CI workflow
10. **Configure artifact cleanup** - Add dist/ to .gitignore, use uv build --clean
11. **Implement GitHub Actions publish workflow** - PyPI trusted publishing with gh-action-pypi-publish
12. **Implement GitHub Actions test-publish workflow** - TestPyPI variant for dry runs
13. **Add CI validation gate** - Prevent publishing unless tests pass on Python 3.12-3.14

### Integration Test Tasks
14. **Integration test: build_and_validate_flow** - End-to-end build → validate → check flow
15. **Integration test: publish_to_testpypi** - Publish to TestPyPI and verify installable
16. **Integration test: version_scenarios** - Test tagged release, pre-release, dirty versions

### Smoke Test Tasks
17. **[P] Smoke test: install_from_testpypi** - Install from TestPyPI, import, verify version
18. **[P] Smoke test: install_from_pypi** - Install from PyPI, import, verify version (runs post-publish)

### Documentation Tasks
19. **Update README.md** - Add installation instructions, PyPI badge
20. **Document version workflow** - Explain tagging, changeset integration, version derivation
21. **Document publishing process** - GitHub Actions workflows, trusted publishing setup

### Validation Tasks
22. **Execute quickstart.md validation** - Follow all quickstart steps, verify success criteria
23. **Measure baseline build performance** - Time build, identify optimization opportunities if needed
24. **Verify all acceptance scenarios** - Validate all 10 acceptance scenarios from spec

**Ordering Strategy**:
- **Phase A: Configuration** (Tasks 1-3) - Must complete before tests can run
- **Phase B: Contract Tests** (Tasks 4-7, [P] parallel) - Write tests before implementation (TDD)
- **Phase C: Implementation** (Tasks 8-13) - Make contract tests pass
- **Phase D: Integration Tests** (Tasks 14-16) - Validate end-to-end flows
- **Phase E: Smoke Tests** (Tasks 17-18, [P] parallel) - Real-world installation validation
- **Phase F: Documentation** (Tasks 19-21, [P] parallel) - User-facing documentation
- **Phase G: Final Validation** (Tasks 22-24) - Quickstart and acceptance testing

**Dependencies**:
- Contract tests (Phase B) depend on configuration (Phase A)
- Implementation (Phase C) follows tests (Phase B) per TDD
- Integration tests (Phase D) require implementation (Phase C) complete
- Smoke tests (Phase E) require TestPyPI publish working
- Final validation (Phase G) requires everything else complete

**Estimated Output**: 24 numbered, ordered tasks across 7 phases in tasks.md

**Parallel Execution Markers**: Tasks marked [P] can run in parallel (independent files/operations)

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Post-Design Constitution Re-Evaluation

**AI-First Context**: ✅ PASS - Build artifacts enable consistent package distribution, clear metadata enhances discoverability. No changes from initial evaluation.

**Proven Patterns**: ✅ PASS - Design leverages hatchling (standard build backend), uv-versioning (proven plugin), PyPA official actions (trusted publishing standard), PEP 621 metadata (ecosystem standard). All research-backed decisions.

**Evidence-Based**: ✅ PASS - All design decisions documented in research.md with official documentation references. Contract tests define validation criteria. No placeholder implementations.

**Testing Philosophy**: ✅ PASS - Contract tests validate build/publish interfaces. Integration tests validate installation across Python versions. Smoke tests verify real-world usage. Focus on user-affecting behavior (installability, metadata correctness).

**Simplicity**: ✅ PASS - Single-purpose design delegates to existing tools: uv-versioning for versions, GitHub Actions for auth, hatchling for building, CI for testing. Flat structure with clear integration points. No unnecessary abstractions.

**Conclusion**: No constitutional violations. Design maintains all principles from initial check.

## Complexity Tracking
*No violations to document - all constitutional principles upheld*


## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command) - ✅ research.md created
- [x] Phase 1: Design complete (/plan command) - ✅ data-model.md, contracts/, quickstart.md, CLAUDE.md updated
- [x] Phase 2: Task planning complete (/plan command - describe approach only) - ✅ 24 tasks across 7 phases planned
- [ ] Phase 3: Tasks generated (/tasks command) - ⏳ Next step: Run `/tasks` command
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS ✅ All principles upheld
- [x] Post-Design Constitution Check: PASS ✅ No violations introduced
- [x] All NEEDS CLARIFICATION resolved ✅ All unknowns resolved in research.md
- [x] Complexity deviations documented ✅ None to document - simple design

**Artifacts Generated** (/plan command):
- [x] `/specs/004-we-re-preparing/plan.md` - This file (updated)
- [x] `/specs/004-we-re-preparing/research.md` - Research findings with evidence
- [x] `/specs/004-we-re-preparing/data-model.md` - Entity models and validation rules
- [x] `/specs/004-we-re-preparing/contracts/build-interface.yaml` - Build and publish contracts
- [x] `/specs/004-we-re-preparing/quickstart.md` - End-to-end validation guide
- [x] `/home/knitli/004-build-codeweaver/CLAUDE.md` - Agent context updated

**Ready for Next Phase**: ✅ YES - Run `/tasks` command to generate tasks.md

---
*Based on Constitution v2.0.0 - See `/memory/constitution.md`*
