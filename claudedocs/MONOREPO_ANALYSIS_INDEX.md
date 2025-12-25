<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Monorepo Split Analysis - Index

**Analysis Date:** 2025-12-11
**Analyst:** Claude Sonnet 4.5
**Status:** Complete ✅

---

## Executive Summary

**Question:** Can CodeWeaver be split into a monorepo with separately installable packages?

**Answer:** ✅ **YES** - And integrating with DI architecture makes it even better!

**Key Discovery:** Dependency Injection plan (in `/plans`) **eliminates 70-75% of circular dependencies**

**Revised Strategy:**
- ✅ 2 packages ready for immediate extraction (tokenizers, daemon)
- ✅ **DI architecture eliminates 120-130 of 164 violations**
- ✅ Remaining ~40 violations are minor (type movements)
- ⏱️ **2-3 weeks** with integrated DI + Monorepo approach (vs. 3-4 weeks standalone)

**Two Birds, One Stone:** DI solves registry coupling + enables clean package separation

---

## Document Guide

### Start Here 📍

**[INTEGRATED_DI_MONOREPO_STRATEGY.md](INTEGRATED_DI_MONOREPO_STRATEGY.md)** ⭐⭐ **READ THIS FIRST**
- **NEW:** Combined DI + Monorepo strategy
- How DI eliminates 75% of violations
- 2-3 week integrated timeline
- Registry coupling solved by DI
- **Recommended approach**

**[DI_IMPACT_VISUALIZATION.md](DI_IMPACT_VISUALIZATION.md)** ⭐ **Visual Guide**
- Before/after architecture diagrams
- Violation reduction breakdown
- Specific code examples
- Testing impact comparison

**[QUICK_START_GUIDE.md](QUICK_START_GUIDE.md)** ⚠️ **Superseded by Integrated Strategy**
- Original standalone monorepo plan
- Still useful for reference
- Use integrated strategy instead

### Deep Dive Analysis 📊

**[REFINED_MONOREPO_ANALYSIS.md](REFINED_MONOREPO_ANALYSIS.md)** ⭐ **MAIN ANALYSIS**
- Complete validation of user-proposed structure
- Detailed breakdown of 164 violations by severity
- Layer-by-layer package specifications
- Priority refactoring tasks with code examples
- Implementation roadmap
- Cost-benefit analysis

**[monorepo_split_analysis.md](monorepo_split_analysis.md)**
- Initial conservative analysis (before user input)
- Comprehensive dependency metrics
- Circular dependency analysis (133 cycles)
- Tier-based separation strategy
- Architectural issues and patterns

**[EXECUTIVE_SUMMARY.md](EXECUTIVE_SUMMARY.md)**
- Original TL;DR (before refined analysis)
- Three-phase approach recommendation
- Decision matrix
- Supporting visualizations

### Raw Data & Tools 🔧

**[dependency_analysis.json](dependency_analysis.json)** (37KB)
- Complete dependency mapping
- Metrics for all packages
- Circular dependency list
- Package file listings

**[proposed_structure_validation.json](proposed_structure_validation.json)** (48KB)
- Validation results for user-proposed structure
- Detailed violation breakdown by package
- File-level import tracking
- Target package analysis

### Visualizations 📈

**[proposed_structure.dot](proposed_structure.dot)** ⭐ **RECOMMENDED**
- Clean layered architecture (post-refactoring)
- Shows intended package structure
- No circular dependencies
- View at: https://dreampuf.github.io/GraphvizOnline/

**[dependency_graph.dot](dependency_graph.dot)**
- Current state (all dependencies)
- Shows all 133 circular dependencies
- Color-coded by stability
- Complex but comprehensive

**[simplified_graph.dot](simplified_graph.dot)**
- Major circular dependencies only
- Easier to understand
- Highlights critical cycles
- Good for presentations

---

## Analysis Scripts

### Main Analysis Script
**[scripts/analyze_dependencies.py](../scripts/analyze_dependencies.py)**
```bash
python scripts/analyze_dependencies.py
```
- Maps all cross-package dependencies
- Calculates coupling metrics (afferent, efferent, instability)
- Identifies circular dependencies
- Generates dependency_analysis.json

### Validation Script
**[scripts/validate_proposed_structure.py](../scripts/validate_proposed_structure.py)**
```bash
python scripts/validate_proposed_structure.py
```
- Validates user-proposed structure against actual imports
- Identifies dependency violations
- Provides refactoring priorities
- Generates proposed_structure_validation.json

---

## Key Metrics

### Current State (Before Refactoring)

| Metric | Value |
|--------|-------|
| Total packages | 15 |
| Circular dependencies | 133 |
| High coupling packages | 9 of 15 |
| Average instability | 0.41 |

### Proposed State (After Refactoring)

| Metric | Value |
|--------|-------|
| Total packages | 9 |
| Circular dependencies | 0 ✅ |
| Extraction-ready packages | 2 ✅ |
| Estimated effort | 3-4 weeks |

---

## Package Structure Comparison

### Initial Conservative Recommendation

**Tier 1 - Ready (1 week):**
- codeweaver-exceptions
- codeweaver-tokenizers
- codeweaver-daemon

**Tier 2+ - Not Recommended** (8-12 weeks):
- Everything else due to 133 circular dependencies

### User-Proposed Structure (VALIDATED ✅)

**Layer 1 - Foundation:**
- codeweaver-core (types, exceptions, registry, search types, provider configs)
- codeweaver-tokenizers
- codeweaver-daemon

**Layer 2 - Utilities:**
- codeweaver-utils
- codeweaver-semantic
- codeweaver-telemetry

**Layer 3 - Services:**
- codeweaver-providers

**Layer 4 - Business Logic:**
- codeweaver-engine

**Layer 5 - Application:**
- codeweaver (CLI, server, MCP, agent API)

---

## Critical Refactorings Required

### Priority 1: Break Provider → Engine Dependency (1 week)
- Move `common/registry` → `core/registry`
- Extract search types from `agent_api` → `core/types/search.py`
- Extract provider config types → `core/provider_config.py`

### Priority 2: Fix Core → Utils Circular Dependency (2-3 days)
- Move core-specific utilities to `core/utils.py`
- Keep generic utilities in `common/utils`

### Priority 3: Fix Telemetry → Engine Dependency (2-3 days)
- Make telemetry configuration injectable
- Remove direct config imports

### Priority 4: Fix Engine → CLI Dependency (1 day)
- Move CLI utilities to `common/utils`

### Priority 5: Fix Core → Providers Dependency (1 day)
- Use lazy imports or move registry to core

**Total Refactoring Effort:** 3-4 weeks

---

## Implementation Phases

### Phase 1: Foundation Layer (Week 1)
- Extract tokenizers and daemon ✅
- Refactor core (move registry, extract types)
- Publish initial packages

### Phase 2: Service Layer (Week 2)
- Refactor providers (update imports)
- Refactor telemetry (make injectable)
- Refactor utils (remove circular deps)

### Phase 3: Business Layer (Week 3)
- Refactor semantic (integrate utilities)
- Refactor engine (remove CLI deps)

### Phase 4: Application Layer (Week 4)
- Refactor main app (update all imports)
- Full integration testing
- Update documentation
- Publish all packages

---

## Success Criteria

**Technical:**
- [ ] Zero circular dependencies between packages
- [ ] All packages build independently
- [ ] All tests pass (unit + integration)
- [ ] Type checking passes

**User Experience:**
- [ ] Existing installations continue working
- [ ] New modular installations available
- [ ] Migration guide published

**Business:**
- [ ] Provider package reusable in external projects
- [ ] Engine embeddable in other applications
- [ ] Core types useful as standalone library

---

## Decision: Proceed or Not?

### ✅ PROCEED IF:
- You have 3-4 weeks for dedicated refactoring
- Modularity is valuable for your use cases
- You can accept some breaking changes in package structure
- You want to enable reusability of providers/engine

### ⚠️ DEFER IF:
- Development resources are limited
- Stability is higher priority than modularity
- Current structure meets all needs
- Risk of breaking changes is too high

### Recommendation: **PROCEED** ✅

**Rationale:**
1. Structure is fundamentally sound
2. Reasonable effort (3-4 weeks vs 8-12)
3. High value (enables reusability)
4. User understands codebase well
5. Natural package boundaries identified

---

## Next Steps

### Immediate Actions (Today)

1. ✅ Review analysis documents (start with QUICK_START_GUIDE.md)
2. ⏭️ Decide on proceeding
3. ⏭️ Create feature branch: `git checkout -b refactor/monorepo-split`
4. ⏭️ Start Week 1 Day 1: Extract tokenizers and daemon

### This Week

1. Complete Week 1 tasks from Quick Start Guide
2. Run validation after each step
3. Commit frequently with clear messages
4. Run full test suite daily

### This Month

1. Complete all 4 weeks of refactoring
2. Internal alpha testing
3. Update documentation
4. Create migration guide

### Next Month

1. Beta release to select users
2. Gather feedback
3. Iterate on issues
4. Stable release

---

## Support Resources

### Validation Commands
```bash
# Check current dependency status
python scripts/analyze_dependencies.py

# Validate proposed structure
python scripts/validate_proposed_structure.py

# Run tests
pytest tests/

# Type check
ty check src/
```

### Visualization
```bash
# View dependency graphs
# Copy .dot file contents to:
# https://dreampuf.github.io/GraphvizOnline/

# Or render locally with graphviz:
dot -Tpng proposed_structure.dot -o proposed_structure.png
```

### Documentation
- [User-Proposed Structure Diagram](proposed_structure.dot)
- [Implementation Guide](QUICK_START_GUIDE.md)
- [Detailed Analysis](REFINED_MONOREPO_ANALYSIS.md)

---

## Questions & Answers

### Q: Is this really viable?
**A:** Yes! User-proposed structure validated against actual imports. 164 violations detected but 62% are expected dependencies. Real work is ~63 violations across 5 refactoring tasks.

### Q: Why is this better than the initial analysis?
**A:** Initial analysis was conservative without domain knowledge. User identified natural boundaries and proper layering. Proposed structure aligns with actual usage patterns.

### Q: What's the biggest risk?
**A:** Breaking provider → engine dependency (20 imports). Mitigated by moving types to core.

### Q: Can we do this incrementally?
**A:** Yes! Start with tokenizers/daemon (immediate), then foundation layer (week 1), then build up through layers.

### Q: What if we encounter issues?
**A:** Validation scripts catch problems early. Each refactoring is independently testable. Can always rollback to previous commit.

### Q: Will this break existing users?
**A:** No! Main package `code-weaver` will still work exactly the same. New modular installations are additive.

---

## File Sizes & Contents

### Documentation (Total: ~100KB)
- QUICK_START_GUIDE.md (12KB) - Implementation guide
- REFINED_MONOREPO_ANALYSIS.md (18KB) - Main analysis
- monorepo_split_analysis.md (23KB) - Initial analysis
- EXECUTIVE_SUMMARY.md (7.6KB) - Original TL;DR

### Data Files (Total: ~85KB)
- proposed_structure_validation.json (48KB) - Validation results
- dependency_analysis.json (37KB) - Raw dependency data

### Visualizations (Total: ~12KB)
- dependency_graph.dot (6.1KB) - Full dependencies
- proposed_structure.dot (3.2KB) - Clean target structure
- simplified_graph.dot (2.5KB) - Major cycles only

---

## Analysis Timeline

**Phase 1: Initial Analysis (Without User Input)**
- Analyzed 15 packages, 200+ files
- Found 133 circular dependencies
- Conservative recommendation: 8-12 weeks, high complexity
- Status: ⚠️ Viable but challenging

**Phase 2: Refined Analysis (With User Input)**
- Validated user-proposed 9-package structure
- Found 164 violations (62% false positives)
- Identified 5 priority refactoring tasks
- Revised recommendation: 3-4 weeks, moderate complexity
- Status: ✅ Recommended for implementation

---

## Conclusion

**CodeWeaver can be successfully split into a modular monorepo structure.**

The user-proposed architecture is sound and aligns with the actual codebase usage patterns. While 164 import violations exist, most are expected dependencies and the remainder can be fixed through 5 targeted refactoring tasks over 3-4 weeks.

**The tooling (uv, mise) is ready. The architecture needs focused refactoring. The value proposition is strong.**

**Recommendation: Proceed with implementation starting with Week 1 of the Quick Start Guide.**

---

**Analysis Complete** ✅
**Ready for Implementation** 🚀

---

## Document History

- 2025-12-11: Initial conservative analysis completed
- 2025-12-11: User-proposed structure validated
- 2025-12-11: Refined analysis with implementation guide
- 2025-12-11: Index document created

**Version:** 2.0 (Refined with user domain knowledge)
**Status:** Complete and validated ✅
