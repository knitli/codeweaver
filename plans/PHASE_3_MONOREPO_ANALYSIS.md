<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Claude (Anthropic AI Assistant)

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Phase 3 Monorepo Structure - Analysis & Readiness Assessment

**Issue:** #204
**Date:** 2025-12-11
**Status:** BLOCKED - Awaiting Phase 1 (#117) and Phase 2 (#118) completion

## Executive Summary

Phase 3 aims to organize CodeWeaver into a clean monorepo structure with 9 independently-buildable packages. The issue is **well-planned and well-documented**, but currently **blocked** by incomplete prerequisite work.

**Key Finding:** The 5-7 day timeline is realistic **only after** Phases 1-2 are complete. Current state requires 3-4 weeks of prerequisite work before Phase 3 can begin.

## Current Status

### ✅ What Exists
- Clear architectural vision (CLAUDE.md)
- Comprehensive DI planning docs (`plans/` directory)
- Well-defined package structure proposal
- Current monolithic structure in `src/codeweaver/`

### ❌ What's Missing (Blockers)
1. **Phase 1 (#117) not completed** - DI foundation
2. **Phase 2 (#118) not completed** - Core migration to DI
3. **No `packages/` directory exists**
4. **No validation script** (`scripts/validate_proposed_structure.py`)
5. **Referenced documentation missing:**
   - `INTEGRATED_DI_MONOREPO_STRATEGY.md`
   - `DI_IMPACT_VISUALIZATION.md`
   - `REFINED_MONOREPO_ANALYSIS.md`

## Dependency Analysis

### Hard Dependencies (MUST Complete First)

**Phase 1 (#117): DI Foundation + Monorepo Prep**
- Build core DI infrastructure (Container, Depends(), factories)
- Extract tokenizers and daemon packages
- Move SearchResult types to core
- **Status:** OPEN, not started
- **Duration:** 5-7 days

**Phase 2 (#118): Core Migration - Breaking Circular Dependencies**
- Migrate Indexer and search services to DI
- Eliminate 120-130 violations (75% reduction)
- Validate package boundaries
- **Status:** OPEN, in progress
- **Duration:** 7-10 days

### Soft Dependencies (Should Have)

- Validation tooling to measure circular dependencies
- Baseline measurement of current violations
- Documentation of eliminated dependencies

## Timeline Reconciliation

### Issue Claims vs Reality

**Issue States:**
> ✅ Circular dependencies broken (75% eliminated)
> ✅ Services don't import across packages
> ✅ Clean dependency flow established
> ✅ Just need to organize files into packages

**Actual Status:**
- ❌ DI infrastructure doesn't exist yet
- ❌ Services still use manual registry access
- ❌ Circular dependencies still present (164 violations)
- ❌ Phase 1 and 2 checklists show all tasks incomplete

### Realistic Timeline

**From Current State:**
```
Week 1 (5-7 days):   Phase 1 - DI Foundation
Week 2 (7-10 days):  Phase 2 - Core Migration
Week 3 (5-7 days):   Phase 3 - Monorepo Structure
─────────────────────────────────────────────────
Total: 17-24 days (3-4 weeks)
```

**Phase 3 Only (after prerequisites):**
- Package setup: 2 days
- Code migration: 2 days
- Build system: 2 days
- Testing: 1 day
- **Total: 5-7 days** ✅ (as stated)

## Validation Requirements

### Missing Tooling

The issue references `scripts/validate_proposed_structure.py`, which doesn't exist. This tool should:

1. **Analyze imports** across codebase
2. **Detect circular dependencies** between modules
3. **Calculate violations** against proposed package structure
4. **Generate reports** showing:
   - Current violation count
   - Violations by package pair
   - Recommended fixes
   - Progress tracking

### Baseline Metrics Needed

Before Phase 3:
- [ ] Confirm current violations = 164
- [ ] Identify which 120-130 will be eliminated by DI
- [ ] Validate remaining ~30-40 violations
- [ ] Define what counts as a "violation"

## Package Structure Validation

### Proposed 9 Packages

```
packages/
  codeweaver-core/          # Foundation (no external deps)
  codeweaver-tokenizers/    # Token counting
  codeweaver-daemon/        # Background services
  codeweaver-utils/         # Common utilities
  codeweaver-semantic/      # Semantic chunking
  codeweaver-telemetry/     # Analytics (DI-enabled)
  codeweaver-providers/     # All providers
  codeweaver-engine/        # Indexing, search
  codeweaver/               # CLI, server, MCP
```

### Dependency Flow (Must be Acyclic)

```
codeweaver-core (foundation)
  ↑
  ├── codeweaver-tokenizers
  ├── codeweaver-daemon
  ├── codeweaver-utils
  ├── codeweaver-telemetry
  ↑
  ├── codeweaver-semantic (depends on: core, utils, tokenizers)
  ├── codeweaver-providers (depends on: core, telemetry)
  ↑
  ├── codeweaver-engine (depends on: core, utils, semantic, providers)
  ↑
  └── codeweaver (depends on: ALL)
```

**Critical:** No circular dependencies between packages.

## Implementation Risks

### Even After Phase 2 Completion

1. **Import Path Updates**
   - Risk: Missing updates break runtime
   - Mitigation: Automated search/replace + validation

2. **Test Suite Breakage**
   - Risk: Tests have hardcoded import paths
   - Mitigation: Comprehensive test run after each package move

3. **Build System Complexity**
   - Risk: uv workspace misconfiguration
   - Mitigation: Incremental testing, package-by-package

4. **Version Management**
   - Risk: 9 packages need coordinated versioning
   - Mitigation: Define versioning strategy upfront

5. **CI/CD Updates**
   - Risk: Build pipeline doesn't handle workspace
   - Mitigation: Update CI config alongside package creation

6. **Documentation Drift**
   - Risk: Docs reference old import paths
   - Mitigation: Migration guide + documentation pass

## Recommendations

### 1. Update Issue #204

Add prominent status note:
```markdown
> **⚠️ BLOCKED:** This issue depends on #117 and #118 completion.
> **Current Status:** Phases 1-2 in progress. Cannot start until DI
> infrastructure is implemented and circular dependencies are broken.
>
> **Estimated Start Date:** After 12-17 days of prerequisite work.
```

### 2. Create Validation Tooling (Priority: HIGH)

Create `scripts/validate_proposed_structure.py` that:
- Analyzes current import structure
- Detects circular dependencies
- Reports violations against proposed structure
- Tracks progress

**Suggested for:** Phase 1 or early Phase 2

### 3. Create Missing Documentation

Either:
- **Option A:** Update issue to reference existing docs in `plans/`
- **Option B:** Create the referenced strategy documents:
  - `INTEGRATED_DI_MONOREPO_STRATEGY.md`
  - `DI_IMPACT_VISUALIZATION.md`
  - `REFINED_MONOREPO_ANALYSIS.md`

**Recommended:** Option A (docs already exist with different names)

### 4. Split Phase 3 into Sub-Issues (Optional)

For better tracking, consider creating 4 sub-issues:
- [ ] #204.1 - Package structure setup (Days 1-2)
- [ ] #204.2 - Move code to packages (Days 3-4)
- [ ] #204.3 - Build system configuration (Days 5-6)
- [ ] #204.4 - Testing & validation (Day 7)

### 5. Define Success Criteria More Precisely

Current: "< 50 violations"
Better:
- Zero circular dependencies between packages
- All packages build independently
- All tests pass
- Type checking passes
- Performance within 5% baseline
- Documentation complete

## Labels Recommendation

**Suggested labels for #204:**
- `enhancement` ✅
- `architecture` ✅
- `blocked` ← Add this
- `monorepo` ← Add if exists, or create
- `refactor` ← Add this
- `dependency-injection` (related)

## Constitutional Compliance

This phase aligns with CodeWeaver Constitution v2.0.1:

✅ **Principle II (Proven Patterns):** Uses uv workspace, standard monorepo patterns
✅ **Principle III (Evidence-Based):** Requires validation script and metrics
✅ **Principle V (Simplicity):** Clear package boundaries, flat structure

⚠️ **Minor Concern:** Issue description presents work as "done" when blocked by prerequisites. This should be clarified to maintain evidence-based accuracy.

## Conclusion

**Phase 3 is well-designed** and will be straightforward to implement **after** the prerequisite DI work is complete. The 5-7 day estimate is realistic for the file organization work, but the issue should be updated to reflect its blocked status.

**Action Items:**
1. Complete Phase 1 (#117) - ~5-7 days
2. Complete Phase 2 (#118) - ~7-10 days
3. Create validation tooling
4. Verify 75% reduction in violations
5. Update issue status
6. Proceed with Phase 3 - ~5-7 days

**Total Time to Monorepo:** 3-4 weeks from current state.

---

**See Also:**
- Issue #204 - [Monorepo Phase 3] Organize into clean package structure
- Issue #116 - [EPIC] DI + Monorepo: Unified architecture transformation
- Issue #117 - [DI Phase 1] Foundation + monorepo prep
- Issue #118 - [DI Phase 2] Core migration
- `plans/dependency-injection-architecture-plan.md` - Full DI strategy
- `plans/DI_ARCHITECTURE_SUMMARY.md` - Executive summary
