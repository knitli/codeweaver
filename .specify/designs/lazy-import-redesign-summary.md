# Lazy Import System Redesign - Executive Summary

> **Expert Panel Review Complete**: Specification quality **7.4/10**
> **Status**: Strong architecture, requires additional specification before implementation
> **Action Required**: Complete requirements, testing strategy, and failure mode analysis (see [Recommendations](#expert-panel-recommendations))

## Related Documents

- **[Requirements Specification](./lazy-import-requirements.md)** - Formal requirements with acceptance criteria
- **[Testing Strategy](./lazy-import-testing-strategy.md)** - Comprehensive test plan and coverage targets
- **[Failure Modes](./lazy-import-failure-modes.md)** - Failure scenarios and recovery strategies
- **[User Workflows](./lazy-import-workflows.md)** - Step-by-step workflows for all personas
- **[Interface Contracts](./lazy-import-interfaces.md)** - Component interfaces and data contracts
- **[Separation of Concerns](./lazy-import-separation-of-concerns.md)** - System boundary definitions

---

## The Problem

The current `validate-lazy-imports.py` has grown to 1845 lines with deeply nested if/else logic that is:
- **Hard to understand**: Which rule wins when they conflict?
- **Hard to extend**: Need to modify code for every new rule
- **Inefficient**: Multiple passes, O(N²) duplicate detection
- **Fragile**: Rules overlap and can block each other

## The Solution

Replace hardcoded logic with a **declarative rule system** featuring:

1. **Rule Engine**: Priority-based rules with pattern matching
2. **Propagation Graph**: Explicit model of how exports flow up the hierarchy
3. **Caching**: JSON-based analysis cache for 10x speedup
4. **Single-Pass Processing**: Build graph once, apply rules consistently

---

## Architecture Comparison

### Current System
```
File 1 ──┐
File 2 ──┼──→ [ should_auto_exclude() ]
File 3 ──┘         ↓
                102 lines of if/else
                   ↓
            [ get_package_exports() ]
                   ↓
            150 lines of filtering
                   ↓
            Duplicate detection (O(N²))
                   ↓
            Generate __init__.py
```

### New System
```
File 1 ──┐         ┌─────────────────┐
File 2 ──┼──→ [ Analysis Cache (JSON) ]
File 3 ──┘         └─────────────────┘
                          ↓
                  ┌──────────────────┐
                  │ Propagation Graph │
                  │  (bottom-up)      │
                  └──────────────────┘
                          ↓
                  ┌──────────────────┐
                  │   Rule Engine    │
                  │ Priority: 1000→0 │
                  └──────────────────┘
                          ↓
                  Generate __init__.py
```

---

## Key Improvements

### 1. Rule System

**Before:**
```python
# Hardcoded in function
def should_auto_exclude(name, module_path, member_type):
    if len(name) == 1 and name.isupper():
        return True  # Exclude single-letter types

    if name == "__version__":
        return False  # Never exclude __version__

    if name.startswith("get_"):
        return False  # Never exclude get_ functions

    # ... 99 more lines of if/else ...
```

**After:**
```yaml
# Declarative rules in YAML
rules:
  - name: "exclude-single-letter-types"
    priority: 1000
    match:
      name_pattern: "^[A-Z]$"
    action: exclude

  - name: "include-version"
    priority: 900
    match:
      name_exact: "__version__"
    action: include

  - name: "include-get-functions"
    priority: 800
    match:
      name_pattern: "^get_"
    action: include
```

**Benefits:**
- ✅ Clear priority ordering (higher number = evaluated first)
- ✅ Self-documenting (name and description fields)
- ✅ Easy to add new rules (no code changes)
- ✅ Testable in isolation

---

### 2. Propagation Model

**Before:**
```python
# Scattered checks at multiple levels
def get_package_exports(package_dir):
    # Check is_types at THIS level
    is_types = "types" in mod_path

    # Apply different rules HERE
    if is_types and name[0].isupper():
        filtered.append(name)

    # Then check again at PARENT level
    # Then dedupe across ALL levels
    # No clear model of "how far should this propagate?"
```

**After:**
```python
# Explicit propagation levels
export = ExportNode(
    name="MyType",
    propagation_level=PropagationLevel.PARENT  # or ROOT or NONE
)

# Graph computes propagation targets
graph.add_export(export)
graph.build_propagated_exports()  # Bottom-up traversal

# Clear model: each export knows exactly where it propagates
```

**Benefits:**
- ✅ Explicit propagation: NONE, PARENT, ROOT, or CUSTOM
- ✅ Conflict resolution: Higher priority rule wins
- ✅ O(N) complexity: Process each export once
- ✅ Predictable: Same export always propagates the same way

---

### 3. Performance Optimization

| Aspect | Current | New | Improvement |
|--------|---------|-----|-------------|
| **File Parsing** | Parse every run | JSON cache + hash check | 10-100x |
| **Duplicate Detection** | O(N²) comparisons | O(N) graph traversal | 10x |
| **Rule Evaluation** | O(N × R) linear scan | O(log R) priority queue | 2-5x |
| **Full Pipeline** | ~30 seconds | ~3 seconds | 10x |

**Key Optimizations:**
1. **JSON Caching**: Parse each file once, cache analysis results
2. **Graph-Based Dedup**: Build propagation graph, conflicts resolved during construction
3. **Priority Rules**: Binary search for matching rule (sorted by priority)
4. **Incremental Updates**: Only reprocess changed files

---

### 4. Extensibility

**Adding a New Rule**

**Before** (requires code change):
```python
# Edit should_auto_exclude() function
def should_auto_exclude(...):
    # ... existing checks ...

    # Add new special case at correct position
    if module_path == "codeweaver.new.module" and name.startswith("internal_"):
        return True  # But does this conflict with other rules?

    # ... rest of function ...
```

**After** (just add config):
```yaml
# .codeweaver/rules/custom.yaml
- name: "exclude-internal-from-new-module"
  priority: 350  # Explicit priority
  description: "Don't export internal_* from new module"
  match:
    name_pattern: "^internal_"
    module_exact: "codeweaver.new.module"
  action: exclude
```

**Benefits:**
- ✅ No code changes needed
- ✅ Priority is explicit (350 = between which other rules?)
- ✅ Can be tested independently
- ✅ Self-documenting

---

## Migration Path

### Phase 1: Dual Mode Support (Week 1)
```python
# Support both old and new systems
if Path(".codeweaver/lazy_imports.toml").exists():
    processor = LazyImportProcessor(...)  # New system
else:
    legacy_auto_fix()  # Old system (fallback)
```

### Phase 2: Auto-Migration Tool (Week 2)
```bash
$ python mise-tasks/migrate-lazy-import-config.py

✓ Analyzed 102 lines of hardcoded rules
✓ Generated 15 YAML rules from code logic
✓ Migrated 67 manual exclusions to overrides
✓ Created .codeweaver/lazy_imports.toml
✓ Backed up old config to exports_config.json.bak
```

### Phase 3: Testing & Validation (Week 3-4)
- Run both systems in parallel
- Compare outputs and fix discrepancies
- Performance benchmarking
- Edge case testing

### Phase 4: Cutover (Week 5)
- Switch to new system by default
- Keep old system for 1-2 releases
- Remove old code after migration period

---

## Example: Rule Debugging

**Problem**: "Why isn't `MyClass` being exported from `codeweaver.providers.capabilities.types`?"

**Current System**: Read 102 lines of if/else, trace execution path mentally

**New System**:
```bash
$ python mise-tasks/validate-lazy-imports.py --debug-rules "MyClass"

Evaluating export: MyClass (codeweaver.providers.capabilities.types)

Rule evaluation order:
  ✓ MATCH [P1000] exclude-single-letter-types → SKIP (name doesn't match)
  ✓ MATCH [P900]  include-version → SKIP (name doesn't match)
  ✓ MATCH [P800]  include-get-functions → SKIP (name doesn't match)
  ✓ MATCH [P700]  types-propagate-pascalcase → INCLUDE ✅
       Reason: Name matches ^[A-Z][a-zA-Z0-9]*$
               Module matches .*\.types(\..*)?
       Propagate: parent
  ✓ SKIP [P600]  capabilities-exclude-constants (already decided)

Final decision: INCLUDE with propagation to parent
Will propagate to: codeweaver.providers.capabilities
```

---

## Configuration Structure

```
.codeweaver/
├── lazy_imports.toml          # Main config
├── rules/                     # Rule definitions
│   ├── core.yaml             # Core codebase rules
│   ├── providers.yaml        # Provider-specific rules
│   └── custom.yaml           # Project-specific rules
└── cache/                     # JSON cache files
    ├── src_codeweaver_core_types_aliases.json
    ├── src_codeweaver_providers_embedding_base.json
    └── ...
```

**Main Config** (`lazy_imports.toml`):
```toml
[settings]
enabled = true
strict_mode = false
cache_enabled = true

[rules]
rule_files = [
    ".codeweaver/rules/core.yaml",
    ".codeweaver/rules/providers.yaml",
]

[overrides.include]
"codeweaver.core.di.utils" = ["dependency_provider"]

[overrides.exclude]
"codeweaver.main" = ["UvicornAccessLogFilter"]

[cache]
enabled = true
format = "json"  # Safe serialization
max_age_days = 7
```

---

## Success Metrics

### Quantitative
- **Performance**: 10x faster (30s → 3s)
- **Code Size**: 1845 lines → 500 lines + config
- **Maintainability**: Add rule without code change
- **Cache Hit Rate**: >90% on second run

### Qualitative
- **Understandability**: Junior dev can add rule
- **Debuggability**: Clear trace of rule evaluation
- **Extensibility**: Rules composable with AND/OR
- **Reliability**: Conflicts resolved predictably

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Migration bugs | Medium | High | Dual-mode support, extensive testing |
| Performance regression | Low | Medium | Benchmarking, profiling, optimization |
| Rule conflicts | Medium | Low | Priority system, conflict detection |
| Config complexity | Low | Low | Good defaults, documentation, examples |

---

## Next Steps

1. **Review Design** (You are here!)
   - Validate approach
   - Identify gaps
   - Refine architecture

2. **Prototype Core Components** (Week 1)
   - Implement `RuleRegistry` and `RuleMatch`
   - Write tests for rule evaluation
   - Validate YAML schema

3. **Build Propagation Graph** (Week 2)
   - Implement `PropagationGraph`
   - Test with small examples
   - Verify conflict resolution

4. **Integrate Caching** (Week 3)
   - Add JSON-based `AnalysisCache`
   - Benchmark performance gains
   - Test invalidation logic

5. **Full Pipeline** (Week 4-5)
   - Integrate all components
   - Run on real codebase
   - Compare with old system

---

## Expert Panel Recommendations

### Summary Assessment

**Overall Specification Quality**: 7.4/10

**Strengths** ✅:
- Excellent architecture design (9.0/10)
- Strong separation of concerns
- Clear problem analysis with quantitative metrics
- Well-thought-out migration strategy

**Critical Gaps** ❌:
- Missing formal testing strategy (5.5/10)
- Missing formal requirements with acceptance criteria (6.5/10)
- Missing failure mode analysis (6.0/10)
- Missing detailed user workflows (7.0/10)

### Required Actions Before Implementation

#### CRITICAL (Must Address)

1. **[REQ] Formal Requirements Specification** - See [lazy-import-requirements.md](./lazy-import-requirements.md)
   - Add REQ-* identifiers with measurable acceptance criteria
   - Define all performance, compatibility, and correctness requirements
   - Priority: CRITICAL

2. **[TEST] Comprehensive Testing Strategy** - See [lazy-import-testing-strategy.md](./lazy-import-testing-strategy.md)
   - Define unit test requirements (>80% coverage)
   - Create integration test scenarios (>10 workflows)
   - Establish performance benchmarks and validation
   - Priority: CRITICAL

3. **[ERROR] Failure Mode Analysis** - See [lazy-import-failure-modes.md](./lazy-import-failure-modes.md)
   - Document all failure scenarios with detection/recovery
   - Implement circuit breaker for cache failures
   - Define error handling philosophy (fail-fast vs permissive)
   - Priority: CRITICAL

#### HIGH (Should Address)

4. **[API] Interface Contracts** - See [lazy-import-interfaces.md](./lazy-import-interfaces.md)
   - Define formal contracts between Export Manager and Validator
   - Create Protocol-based abstractions for testability
   - Add schema versioning for configuration
   - Priority: HIGH

5. **[UX] User Workflows** - See [lazy-import-workflows.md](./lazy-import-workflows.md)
   - Document step-by-step workflows for all personas
   - Include error recovery procedures
   - Define CI/CD integration modes
   - Priority: HIGH

6. **[CONFIG] Configuration Validation**
   - Create JSON schemas for rule and settings validation
   - Implement validation command: `mise run lazy-imports validate-config`
   - Priority: HIGH

### Decision Points Requiring User Input

1. **Migration Tolerance**: Must new system match old system exactly (0% delta) or is <1% acceptable?
2. **Error Philosophy**: Fail fast (strict) or continue with warnings (permissive)?
3. **Performance vs Correctness**: If validation takes 5s instead of 3s target, which wins?
4. **Compatibility Timeline**: Is v0.9-v0.11 timeline acceptable?
5. **CI Integration**: Automatic (pre-commit), manual, or CI-enforced export generation?

### Timeline Estimate

- **Specification Completion**: 2-3 weeks (addressing critical and high priority gaps)
- **Risk Reduction**: HIGH → LOW
- **Quality Improvement**: 7.4/10 → 9.0/10
- **Implementation Readiness**: MEDIUM → HIGH

### Next Immediate Steps

1. Review and approve user decisions (see Decision Points above)
2. Create formal requirements document with acceptance criteria
3. Define comprehensive testing strategy with coverage targets
4. Document all failure modes with recovery strategies
5. Finalize user workflows and integration modes

**Recommendation**: Complete specification documents before beginning implementation. The architecture is sound, but operational details must be defined to ensure production readiness.

---

## Questions for Discussion

### Architectural Questions

1. **Rule Priority Ranges**: Should we define priority ranges for different categories?
   - 900-1000: Absolute overrides
   - 700-899: Type-based rules
   - 500-699: Module-based rules
   - 100-499: Default rules

2. **Custom Propagation**: Do we need custom propagation levels beyond NONE/PARENT/ROOT?
   - Example: "Propagate 2 levels up" or "Propagate to specific module"

3. **Rule Composition**: Should we support more complex logic?
   - Example: `(types OR dependencies) AND (PascalCase OR get_*)`

4. **Configuration Format**: TOML vs YAML for rules?
   - TOML for settings, YAML for rules?
   - Or all TOML?

5. **Performance Target**: Is 3 seconds acceptable or should we aim for <1s?
   - Parallel processing?
   - More aggressive caching?

### Implementation Questions

6. **Testability Abstractions**: Should we add Protocol-based abstractions?
   - `AnalysisCache(Protocol)` for testing without file I/O
   - `FileSystem(Protocol)` for testing without disk access
   - Trade-off: Improved testability vs increased complexity

7. **Event-Driven Architecture**: Should we add event bus for extensibility?
   - Allows plugins (linter, formatter) without modifying coordinator
   - Trade-off: More flexible vs more complex for MVP

8. **Migration Validation Mode**: How strict should equivalence checking be?
   - Require 100% match or allow approved exceptions?
   - Automatic approval or manual review for differences?

---

## Appendix: Code Reduction

### Before
```python
# should_auto_exclude(): 102 lines
# get_package_exports(): 150 lines
# Various helper functions: 100+ lines
# Total hardcoded logic: ~400 lines
```

### After
```python
# Rule engine: 80 lines
# Propagation graph: 120 lines
# Cache system: 60 lines
# Processor: 80 lines
# Total code: ~340 lines

# Plus declarative config: ~100 lines YAML
# Net reduction: 400 lines → 100 lines (75% less code)
```

**But more importantly**:
- Old: All logic in one file, hard to understand
- New: Clear separation of concerns, self-documenting
- Old: Add rule = modify code + hope for no conflicts
- New: Add rule = add YAML entry with explicit priority
