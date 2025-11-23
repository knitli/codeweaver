<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Tasks: PyPI Build and Publishing System

**Input**: Design documents from `/specs/004-we-re-preparing/`
**Prerequisites**: plan.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

## Execution Flow
```
1. Load plan.md from feature directory ✅
   → Tech stack: hatchling, uv-versioning, GitHub Actions, twine
   → Libraries: PyPA gh-action-pypi-publish, astral-sh/setup-uv
   → Structure: Single project (Option 1)
2. Load optional design documents ✅
   → data-model.md: 5 entities (PackageMetadata, VersionIdentifier, BuildArtifact, BuildManifest, PublishRequest)
   → contracts/: build-interface.yaml → 3 validation contracts
   → research.md: Build backend (hatchling), version management (uv-versioning), publishing (trusted publishing)
3. Generate tasks by category (below)
4. Apply task rules:
   → Different files/operations = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001-T024)
6. Validate task completeness ✅
   → All contracts have tests ✅
   → All quickstart scenarios covered ✅
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Exact file paths included in descriptions

## Path Conventions
Single project structure (per plan.md):
- Configuration: `pyproject.toml` at repository root
- Tests: `tests/contract/`, `tests/integration/`, `tests/smoke/`
- Workflows: `.github/workflows/`
- Documentation: `README.md`, repository root

---

## Phase A: Configuration

**Goal**: Set up pyproject.toml, build backend, and CI workflows

- [X] **T001** Update `pyproject.toml` metadata with all required PEP 621 fields (name, description, readme, requires-python, license, authors, keywords, classifiers, urls)

- [X] **T002** Configure build backend in `pyproject.toml` - add hatchling and uv-versioning to `[build-system]`, set `[tool.hatch.version]` source to "vcs"

- [X] **T003** [P] Create `.github/workflows/publish.yml` for PyPI publishing with trusted publishing (triggered on `v*` tags)

- [X] **T004** [P] Create `.github/workflows/publish-test.yml` for TestPyPI publishing (manual workflow_dispatch trigger)

- [X] **T005** Add `dist/` to `.gitignore` to prevent committing build artifacts

---

## Phase B: Contract Tests (TDD - MUST COMPLETE BEFORE PHASE C)

**CRITICAL**: These tests MUST be written and MUST FAIL before ANY implementation

- [X] **T006** [P] Contract test: validate_build_output in `tests/contract/test_build_output.py` - verify `uv build` creates exactly 2 artifacts (wheel + sdist) with correct naming conventions and non-empty sizes

- [X] **T007** [P] Contract test: validate_twine_check in `tests/contract/test_metadata_validation.py` - verify `twine check dist/*` passes for both artifacts with "PASSED" output

- [X] **T008** [P] Contract test: validate_version_derivation in `tests/contract/test_version_derivation.py` - verify version derived correctly from git state (tagged release vs pre-release vs dirty)

- [X] **T009** [P] Contract test: validate_publish_output in `tests/contract/test_publish_validation.py` - verify package installable from PyPI/TestPyPI with correct version and importable

---

## Phase C: Implementation (ONLY after tests are failing)

**Goal**: Make contract tests pass by implementing build and publish configuration

- [X] **T010** Install build dependencies - add `hatchling>=1.18.0` and `uv-versioning>=0.1.0` to `[build-system.requires]` in `pyproject.toml`

- [X] **T011** Configure dynamic version - set `version` to "dynamic" in `[project]` table and configure `[tool.uv-versioning]` for automatic git-based version detection

- [X] **T012** Implement metadata validation step in `.github/workflows/publish.yml` and `.github/workflows/publish-test.yml` - add `uv pip install twine && twine check dist/*` step after build

- [X] **T013** Configure artifact cleanup in workflows - use `uv build --clean` flag in both publish workflows to remove previous artifacts before building

- [X] **T014** Implement PyPI publish workflow logic in `.github/workflows/publish.yml` - build step, twine check, pypa/gh-action-pypi-publish@release/v1 with production repository URL

- [X] **T015** Implement TestPyPI publish workflow logic in `.github/workflows/publish-test.yml` - same as T014 but with test.pypi.org repository URL and workflow_dispatch trigger

- [X] **T016** Add CI validation gate to `.github/workflows/publish.yml` - add `needs: tests` dependency to ensure Python 3.12-3.14 tests pass before publishing

---

## Phase D: Integration Tests

**Goal**: Validate end-to-end build and publish workflows

- [X] **T017** Integration test: build_and_validate_flow in `tests/integration/test_build_flow.py` - end-to-end test: clean dist, run `uv build`, verify artifacts, run `twine check`, confirm success

- [X] **T018** Integration test: publish_to_testpypi in `tests/integration/test_testpypi_publish.py` - trigger TestPyPI publish workflow, wait for completion, verify package appears on test.pypi.org

- [X] **T019** Integration test: version_scenarios in `tests/integration/test_version_scenarios.py` - test all 3 version scenarios (tagged release "0.1.0", pre-release "0.1.0rcN+gHASH", dirty "0.1.0rcN+gHASH.dirty")

---

## Phase E: Smoke Tests

**Goal**: Verify real-world package installation and usability

- [X] **T020** [P] Smoke test: install_from_testpypi in `tests/smoke/test_testpypi_install.py` - create venv, install from test.pypi.org with extra-index-url, import codeweaver, verify version matches

- [X] **T021** [P] Smoke test: install_from_pypi in `tests/smoke/test_pypi_install.py` - create venv, install from pypi.org, import codeweaver, verify version, run basic functionality test (runs after production publish)

---

## Phase F: Documentation

**Goal**: User-facing documentation for installation and publishing

- [X] **T022** [P] Update `README.md` with installation instructions - add `pip install codeweaver` example, PyPI badge, supported Python versions section

- [X] **T023** [P] Create version workflow documentation in `docs/versioning.md` or `CONTRIBUTING.md` - explain git tagging workflow, changeset integration, version derivation from git state

- [X] **T024** [P] Document publishing process in `docs/publishing.md` or `CONTRIBUTING.md` - explain GitHub Actions trusted publishing setup, TestPyPI vs PyPI workflows, release process

---

## Phase G: Final Validation

**Goal**: Execute quickstart validation and verify all acceptance scenarios

- [X] **T025** Execute quickstart.md validation - follow all quickstart steps manually or via automation, verify all success criteria met (local build, metadata validation, installation tests, version scenarios)

- [X] **T026** Measure baseline build performance - time `uv build` execution, record baseline, identify optimization opportunities if build time exceeds 30 seconds (✅ 1.8 seconds - well under threshold)

- [X] **T027** Verify all 10 acceptance scenarios from spec.md - validate each scenario passes (build artifacts creation, version derivation, metadata validation, TestPyPI publish, PyPI publish, installation, version management, CI integration, cleanup, troubleshooting)

---

## Dependencies

### Critical Path (Sequential)
```
Configuration (T001-T005)
  → Contract Tests (T006-T009) [P]
  → Implementation (T010-T016)
  → Integration Tests (T017-T019)
  → Smoke Tests (T020-T021) [P] (T020 requires TestPyPI, T021 requires PyPI)
  → Documentation (T022-T024) [P]
  → Final Validation (T025-T027)
```

### Specific Dependencies
- **Phase B (Contract Tests)** depends on **Phase A (Configuration)** - need pyproject.toml structure to write tests against
- **Phase C (Implementation)** depends on **Phase B (Contract Tests)** - TDD: tests must fail first
- **Phase D (Integration Tests)** depends on **Phase C (Implementation)** - need working build/publish flows
- **Phase E (Smoke Tests)** depends on **Phase D (Integration Tests)** - need TestPyPI/PyPI packages published
- **Phase F (Documentation)** can start after **Phase C (Implementation)** - can document while integration tests run
- **Phase G (Final Validation)** depends on **all previous phases** - validates complete system

### File-Level Dependencies
- T001-T002: Same file (`pyproject.toml`) → Sequential
- T003-T004: Different files → [P] Parallel
- T006-T009: Different test files → [P] Parallel
- T010-T011: Same file (`pyproject.toml`) → Sequential (but after config phase)
- T012-T013: Same workflow files → Sequential per file (T012 both workflows, T013 both workflows)
- T014-T015: Different workflow files → Sequential order ensures production workflow (T014) validated before test variant (T015)
- T016: Modifies T014's file → Sequential after T014
- T017-T019: Different test files → Sequential (each builds on previous validation)
- T020-T021: Different test files → [P] Parallel (T020=TestPyPI, T021=PyPI post-publish)
- T022-T024: Different files → [P] Parallel
- T025-T027: Sequential validation steps

---

## Parallel Execution Examples

### Phase B: All Contract Tests (After Configuration Complete)
```bash
# Launch T006-T009 together (all independent test files):
Task: "Write failing contract test validate_build_output in tests/contract/test_build_output.py"
Task: "Write failing contract test validate_twine_check in tests/contract/test_metadata_validation.py"
Task: "Write failing contract test validate_version_derivation in tests/contract/test_version_derivation.py"
Task: "Write failing contract test validate_publish_output in tests/contract/test_publish_validation.py"

# Expected outcome: 4 failing tests that define success criteria for Phase C
```

### Phase E: Smoke Tests (After Packages Published)
```bash
# Launch T020-T021 together (independent installation tests):
Task: "Smoke test install from TestPyPI in tests/smoke/test_testpypi_install.py"
Task: "Smoke test install from PyPI in tests/smoke/test_pypi_install.py"  # Only after production publish

# Note: T021 can only run after successful PyPI publish (post-T014 success)
```

### Phase F: Documentation (After Implementation Complete)
```bash
# Launch T022-T024 together (all independent documentation files):
Task: "Update README.md with installation instructions and PyPI badge"
Task: "Document version workflow in docs/versioning.md"
Task: "Document publishing process in docs/publishing.md"
```

---

## Task Generation Rules Applied

1. **From Contracts** (contracts/build-interface.yaml):
   - Build Command Contract → T006 (validate_build_output)
   - Publish Command Contract → T009 (validate_publish_output)
   - Verification Command Contract → T007 (validate_twine_check)
   - Version derivation (implied) → T008 (validate_version_derivation)

2. **From Data Model** (data-model.md):
   - PackageMetadata entity → T001 (pyproject.toml metadata)
   - VersionIdentifier entity → T011 (dynamic version config)
   - BuildArtifact entity → T010 (build dependencies)
   - PublishRequest entity → T014, T015 (publish workflows)
   - BuildManifest entity → Captured in build process (no separate task)

3. **From Quickstart** (quickstart.md):
   - Local Development Flow → T017 (build_and_validate_flow)
   - Publishing Flow → T018 (publish_to_testpypi)
   - Version Management Scenarios → T019 (version_scenarios)
   - Smoke Tests → T020, T021 (installation validation)
   - Final validation → T025 (execute quickstart end-to-end)

4. **From Research** (research.md):
   - Build backend decision → T002 (hatchling configuration)
   - uv-versioning integration → T011 (version config)
   - Publishing workflow → T014, T015 (GitHub Actions)
   - Performance baseline → T026 (measure build time)

5. **Ordering**:
   - Setup (Phase A) → Tests (Phase B) → Implementation (Phase C) → Integration (Phase D) → Smoke (Phase E) → Documentation (Phase F) → Validation (Phase G)
   - TDD enforced: Contract tests (T006-T009) MUST be written and failing before implementation (T010-T016)

---

## Validation Checklist

- [x] All contracts have corresponding tests
  - build-interface.yaml Build Command → T006 ✅
  - build-interface.yaml Publish Command → T009 ✅
  - build-interface.yaml Verification Command → T007 ✅
  - Version derivation contract → T008 ✅

- [x] All entities have tasks
  - PackageMetadata → T001 ✅
  - VersionIdentifier → T011 ✅
  - BuildArtifact → T010 ✅
  - PublishRequest → T014, T015 ✅
  - BuildManifest → Captured in build ✅

- [x] All tests come before implementation
  - Phase B (T006-T009) before Phase C (T010-T016) ✅

- [x] Parallel tasks truly independent
  - T003-T004: Different workflow files ✅
  - T006-T009: Different test files ✅
  - T020-T021: Different test files, different PyPI instances ✅
  - T022-T024: Different documentation files ✅

- [x] Each task specifies exact file path ✅

- [x] No task modifies same file as another [P] task ✅

---

## Notes

- **[P] tasks** = different files or operations, no dependencies
- **TDD enforcement**: Verify T006-T009 fail before starting T010
- **Commit strategy**: Commit after each task completion
- **CI gate**: T016 ensures tests pass on Python 3.12-3.14 before PyPI publish
- **Version immutability**: PyPI versions cannot be deleted/overwritten - careful with T014 production publish
- **Trusted publishing**: GitHub Actions OAuth already configured (per spec), no API token setup needed

---

## Execution Guidance

**For Manual Execution**:
1. Start with Phase A (Configuration): T001-T005 sequentially
2. Phase B (Contract Tests): Can launch T006-T009 in parallel
3. Verify all contract tests FAIL before proceeding to Phase C
4. Phase C (Implementation): T010-T016 sequentially (some modify same files)
5. Phases D-G: Follow dependency order, leverage [P] parallelism where possible

**For Automated Execution**:
```bash
# Example: Launch Phase B contract tests in parallel
Task agent T006 &
Task agent T007 &
Task agent T008 &
Task agent T009 &
wait

# Verify all failed
pytest tests/contract/ --expect-fail

# Proceed to Phase C implementation
Task agent T010  # Sequential from here
```

**Success Criteria**:
- All 27 tasks completed
- All contract tests passing (T006-T009)
- All integration tests passing (T017-T019)
- All smoke tests passing (T020-T021)
- Package published to PyPI (T014) and installable
- Documentation complete (T022-T024)
- Quickstart validation successful (T025)
- All 10 acceptance scenarios verified (T027)
