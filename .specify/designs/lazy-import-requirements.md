# Lazy Import System - Formal Requirements Specification

## Overview

This document defines the formal requirements for the lazy import system redesign with measurable acceptance criteria and test approaches.

---

## Performance Requirements

### REQ-PERF-001: Processing Speed
**Requirement**: Full pipeline SHALL complete in <5 seconds for 500 modules
**Priority**: MUST
**Acceptance Criteria**:
- Benchmark script reports total time <5 seconds on reference hardware
- Reference: 4-core CPU, 16GB RAM, SSD storage
- Measured from process start to completion including all file I/O

**Test Approach**:
```bash
mise run benchmark-lazy-imports --modules 500
# Expected output: Total time: 4.2s ✓
```

**Validation**: Performance test suite runs on every PR

---

### REQ-PERF-002: Cache Hit Rate
**Requirement**: Cache hit rate SHALL be >90% on second run
**Priority**: MUST
**Acceptance Criteria**:
- Metrics show cache_hits / (cache_hits + cache_misses) > 0.90
- Applies when no files have been modified between runs
- Cache must be persistent across process restarts

**Test Approach**:
```python
def test_cache_effectiveness():
    processor.process_all()  # First run (warm cache)
    metrics = processor.process_all()  # Second run

    assert metrics.cache_hit_rate > 0.90
    assert metrics.processing_time < 5.0
```

**Validation**: Performance test validates cache metrics

---

### REQ-PERF-003: Incremental Processing
**Requirement**: Processing single modified file SHALL take <500ms
**Priority**: SHOULD
**Acceptance Criteria**:
- When only one file changes, reprocessing completes in <500ms
- Unchanged files use cached analysis
- Graph rebuild is incremental, not full

**Test Approach**:
```python
def test_incremental_update():
    processor.process_all()  # Initial state

    modify_file("src/codeweaver/test.py")

    start = time.time()
    processor.process_all()
    duration = time.time() - start

    assert duration < 0.5  # 500ms
    assert processor.metrics.files_reprocessed == 1
```

---

### REQ-PERF-004: Memory Usage
**Requirement**: Peak memory usage SHALL be <500MB for large codebase
**Priority**: SHOULD
**Acceptance Criteria**:
- Processing 1000+ files uses <500MB peak RSS
- No memory leaks on repeated runs
- Cache eviction prevents unbounded growth

**Test Approach**:
```python
@pytest.mark.benchmark
def test_memory_usage():
    import tracemalloc

    tracemalloc.start()
    processor.process_all()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert peak < 500 * 1024 * 1024  # 500MB in bytes
```

---

## Compatibility Requirements

### REQ-COMPAT-001: Output Equivalence
**Requirement**: New system SHALL produce identical output to old system
**Priority**: MUST
**Acceptance Criteria**:
- Migration validation shows 0% delta OR all differences approved
- All 347 modules in current codebase produce identical __all__ declarations
- All _dynamic_imports entries match old system
- Any differences documented in migration exceptions list

**Test Approach**:
```bash
mise run lazy-imports --validate-migration
# Must report: 100% match OR documented exceptions only
```

**Validation**: CI pipeline runs migration validation

---

### REQ-COMPAT-002: Backward Compatibility Timeline
**Requirement**: Old system SHALL remain functional for 2 release cycles
**Priority**: MUST
**Acceptance Criteria**:
- v0.9.0: New system default, old system available with --legacy flag
- v0.10.0: Old system deprecated with warning, still functional
- v0.11.0: Old system removed, migration required

**Test Approach**:
- v0.9.0: Both systems tested in CI
- v0.10.0: Old system tests with deprecation warnings
- v0.11.0: Old system code removed

---

### REQ-COMPAT-003: Configuration Migration
**Requirement**: System SHALL automatically migrate old configuration
**Priority**: MUST
**Acceptance Criteria**:
- First run with new system auto-migrates exports_config.json
- Backup created as exports_config.json.pre-v0.9.0
- Migration tool validates converted rules match old behavior
- User can rollback by deleting new config and restarting

**Test Approach**:
```python
def test_config_migration():
    # Given: Old config exists
    create_old_config("exports_config.json")

    # When: New system starts
    processor = LazyImportProcessor()

    # Then: Config migrated
    assert Path(".codeweaver/lazy_imports.toml").exists()
    assert Path("exports_config.json.pre-v0.9.0").exists()

    # And: Validation passes
    validation = validate_migration(old, new)
    assert validation.match_rate == 1.0
```

---

## Correctness Requirements

### REQ-CORRECT-001: Deterministic Evaluation
**Requirement**: Rule evaluation SHALL be deterministic
**Priority**: MUST
**Acceptance Criteria**:
- Same input always produces same output
- Rule evaluation order is consistent
- No randomness in tie-breaking

**Test Approach**:
```python
from hypothesis import given, strategies as st

@given(
    rules=st.lists(rule_strategy(), min_size=2, max_size=20),
    export=export_strategy()
)
def test_determinism(rules, export):
    engine1 = RuleEngine(rules)
    engine2 = RuleEngine(rules)

    result1 = engine1.evaluate(export.name, export.module, export.type)
    result2 = engine2.evaluate(export.name, export.module, export.type)

    assert result1 == result2
```

**Validation**: Property-based tests using hypothesis

---

### REQ-CORRECT-002: Conflict Resolution
**Requirement**: Rule conflicts SHALL be resolved using priority + lexicographic ordering
**Priority**: MUST
**Acceptance Criteria**:
- Higher priority rule always wins
- Same priority: alphabetically first rule name wins
- Tie-breaking is consistent and documented

**Algorithm**:
```python
def resolve_conflict(matches: list[RuleMatch]) -> RuleMatch:
    """Resolve conflicts between matching rules."""
    if not matches:
        return NO_MATCH

    # Sort by priority (descending), then name (ascending)
    sorted_matches = sorted(
        matches,
        key=lambda m: (-m.rule.priority, m.rule.name)
    )

    return sorted_matches[0]
```

**Test Approach**:
```python
def test_priority_ordering():
    rules = [
        Rule("aaa-exclude", priority=500, action="exclude"),
        Rule("zzz-include", priority=900, action="include"),
    ]
    result = engine.evaluate("test", "module", "class")
    assert result.matched_rule.name == "zzz-include"

def test_lexicographic_tiebreak():
    rules = [
        Rule("zzz-exclude", priority=500, action="exclude"),
        Rule("aaa-include", priority=500, action="include"),
    ]
    result = engine.evaluate("test", "module", "class")
    assert result.matched_rule.name == "aaa-include"
```

---

### REQ-CORRECT-003: No Circular Propagation
**Requirement**: System SHALL detect and reject circular propagation
**Priority**: MUST
**Acceptance Criteria**:
- Circular propagation detected during graph build
- Clear error message showing cycle path
- Build fails (exit code 1)

**Test Approach**:
```python
def test_circular_propagation_detection():
    # Create circular propagation scenario
    rules = create_circular_rules()

    with pytest.raises(PropagationCycleError) as exc:
        graph = PropagationGraph(rules)
        graph.build()

    assert "Circular propagation detected" in str(exc.value)
    assert "Module A → Module B → Module A" in str(exc.value)
```

---

## Error Handling Requirements

### REQ-ERROR-001: Invalid Rule Rejection
**Requirement**: Invalid rules SHALL be rejected with actionable error messages
**Priority**: MUST
**Acceptance Criteria**:
- YAML syntax errors show file, line number, and issue
- Schema validation errors explain what's wrong and how to fix
- Error includes suggestions for correction
- Exit code 1 (fail fast)

**Example Error**:
```
❌ Error loading rules from .codeweaver/rules/custom.yaml

Line 15: Invalid YAML syntax
  13 | - name: "my-rule"
  14 |   match:
  15 |     name_pattern: "^Foo  # <-- Missing closing quote
  16 |   action: include

Suggestions:
- Check for missing quotes, colons, or indentation
- Validate YAML at: https://www.yamllint.com/
- Restore from backup: .codeweaver/rules/custom.yaml.bak

Exit code: 1
```

**Test Approach**:
```python
def test_invalid_yaml_error():
    write_file("rules.yaml", 'name: "unclosed')

    result = subprocess.run(
        ["mise", "run", "lazy-imports", "export", "generate"],
        capture_output=True
    )

    assert result.returncode == 1
    assert "Invalid YAML syntax" in result.stderr
    assert "Missing closing quote" in result.stderr
```

---

### REQ-ERROR-002: Corrupt Cache Recovery
**Requirement**: System SHALL recover from corrupt cache gracefully
**Priority**: MUST
**Acceptance Criteria**:
- JSON parse errors detected
- Corrupt entries deleted automatically
- Warning logged but build continues
- Performance impact minimized (only corrupt entries reprocessed)

**Recovery Behavior**:
```python
def analyze_file(self, path: Path) -> Analysis:
    try:
        cached = self.cache.get(path, hash_file(path))
        if cached:
            return cached
    except (JSONDecodeError, CacheCorruptionError) as e:
        logger.warning(
            f"Cache corruption detected for {path}: {e}\n"
            f"Deleting corrupt entry and re-analyzing"
        )
        self.cache.invalidate(path)
        # Fall through to re-analysis

    return self._analyze_directly(path)
```

**Test Approach**:
```python
def test_corrupt_cache_recovery():
    # Corrupt the cache
    cache_file = ".codeweaver/cache/test.json"
    write_file(cache_file, "{truncated")

    # Should recover gracefully
    result = processor.process_all()

    assert result.success
    assert "Cache corruption detected" in caplog.text
    assert not Path(cache_file).exists()  # Corrupt entry deleted
```

---

### REQ-ERROR-003: Cache Circuit Breaker
**Requirement**: System SHALL open circuit breaker after 3 consecutive cache failures
**Priority**: SHOULD
**Acceptance Criteria**:
- After 3 consecutive cache errors, circuit opens
- Circuit open: bypass cache for remaining operations
- Warning logged: "Cache circuit opened, using fallback"
- Next run: circuit resets

**Test Approach**:
```python
def test_cache_circuit_breaker():
    cache = FakeCacheWithFailures(fail_count=5)
    processor = LazyImportProcessor(cache=cache)

    result = processor.process_all()

    assert result.success
    assert "Cache circuit opened" in caplog.text
    assert processor.cache_failures >= 3
    assert processor.cache_circuit_open
```

---

## Validation Requirements

### REQ-VALID-001: Lazy Import Call Validation
**Requirement**: System SHALL detect broken lazy_import() calls
**Priority**: MUST
**Acceptance Criteria**:
- All lazy_import(module, obj) calls validated
- Validation confirms module exists and obj is importable
- Errors show file, line, module, object, and issue
- Validation runs in CI and locally

**Test Approach**:
```python
def test_broken_lazy_import_detection():
    write_file("test.py", '''
lazy_import("nonexistent.module", "Class")
''')

    validator = LazyImportValidator()
    issues = validator.validate_calls([Path("test.py")])

    assert len(issues) == 1
    assert "nonexistent.module" in issues[0].message
    assert issues[0].severity == "error"
```

---

### REQ-VALID-002: Package Consistency
**Requirement**: System SHALL validate package __init__.py consistency
**Priority**: MUST
**Acceptance Criteria**:
- __all__ matches _dynamic_imports
- _dynamic_imports entries can be imported
- TYPE_CHECKING imports exist
- No duplicates between own and propagated exports

**Test Approach**:
```python
def test_package_consistency():
    validator = LazyImportValidator()
    issues = validator.check_package(Path("codeweaver/__init__.py"))

    # No errors expected for valid package
    errors = [i for i in issues if i.severity == "error"]
    assert len(errors) == 0
```

---

## Configuration Requirements

### REQ-CONFIG-001: Schema Validation
**Requirement**: Configuration SHALL be validated against JSON schema
**Priority**: MUST
**Acceptance Criteria**:
- Rules validated against schema before loading
- Settings validated against schema before use
- Validation errors clear and actionable
- Command to validate config: `mise run lazy-imports validate-config`

**Test Approach**:
```python
def test_schema_validation():
    write_file("rules.yaml", '''
rules:
  - name: "test"
    priority: 1500  # Invalid: >1000
    action: "include"
''')

    with pytest.raises(SchemaValidationError) as exc:
        load_rules("rules.yaml")

    assert "priority" in str(exc.value)
    assert "maximum: 1000" in str(exc.value)
```

---

### REQ-CONFIG-002: Schema Versioning
**Requirement**: Configuration files SHALL include schema version
**Priority**: MUST
**Acceptance Criteria**:
- All rule files include schema_version field
- Unsupported versions rejected with clear error
- Migration tools provided for version upgrades
- Minimum 2 release notice before version deprecation

**Format**:
```yaml
schema_version: "1.0"

rules:
  - name: "example"
    # ...
```

**Test Approach**:
```python
def test_unsupported_schema_version():
    write_file("rules.yaml", '''
schema_version: "99.0"
rules: []
''')

    with pytest.raises(UnsupportedSchemaVersion) as exc:
        load_rules("rules.yaml")

    assert "99.0" in str(exc.value)
    assert "Supported versions: 1.0, 1.1" in str(exc.value)
```

---

## User Experience Requirements

### REQ-UX-001: Clear Debug Output
**Requirement**: Debug mode SHALL show rule evaluation trace
**Priority**: MUST
**Acceptance Criteria**:
- Shows all rules evaluated in priority order
- Shows match/skip decision for each rule
- Shows final decision and propagation
- Shows where export will appear

**Example Output**:
```
Evaluating export: MyClass (codeweaver.providers.types)

Rule evaluation order:
  ✓ MATCH [P1000] exclude-single-letter-types → SKIP (name doesn't match)
  ✓ MATCH [P900]  include-version → SKIP (name doesn't match)
  ✓ MATCH [P700]  types-propagate-pascalcase → INCLUDE ✅
       Reason: Name matches ^[A-Z][a-zA-Z0-9]*$
               Module matches .*\.types(\..*)?
       Propagate: parent
  ✓ SKIP [P600]  (already decided)

Final decision: INCLUDE with propagation to parent
Will propagate to: codeweaver.providers
```

**Test Approach**:
```python
def test_debug_output(capsys):
    processor.debug_export("MyClass", "codeweaver.providers.types")

    output = capsys.readouterr().out
    assert "Rule evaluation order:" in output
    assert "Final decision:" in output
    assert "Will propagate to:" in output
```

---

### REQ-UX-002: Progress Indication
**Requirement**: Long operations SHALL show progress
**Priority**: SHOULD
**Acceptance Criteria**:
- Processing >50 files shows progress bar
- Shows files/second and estimated time remaining
- Updates at reasonable frequency (not every file)

**Test Approach**:
```python
def test_progress_indication(capsys):
    # Create many files to trigger progress bar
    files = [create_test_file(f"module_{i}.py") for i in range(100)]

    processor.process_all()

    output = capsys.readouterr().out
    assert "Processing:" in output
    assert "files/s" in output
```

---

## Testing Requirements

### REQ-TEST-001: Code Coverage
**Requirement**: New code SHALL have >80% test coverage
**Priority**: MUST
**Acceptance Criteria**:
- Rule engine: >90% coverage
- Propagation graph: >85% coverage
- Code generator: >80% coverage
- Validator: >85% coverage
- Overall: >80% coverage

**Validation**: Coverage report in CI

---

### REQ-TEST-002: Performance Benchmarks
**Requirement**: Performance benchmarks SHALL pass on every PR
**Priority**: MUST
**Acceptance Criteria**:
- Processing time <5s for 500 modules
- Cache hit rate >90% on second run
- Benchmarks run in CI
- Regressions fail the build

**Validation**:
```yaml
# .github/workflows/ci.yml
- name: Run Performance Benchmarks
  run: |
    mise run benchmark-lazy-imports
    # Fails if targets not met
```

---

## Requirements Summary

### Critical Path Requirements (MUST)
- REQ-PERF-001: Processing speed <5s
- REQ-PERF-002: Cache hit rate >90%
- REQ-COMPAT-001: Output equivalence with old system
- REQ-COMPAT-002: 2 release backward compatibility
- REQ-COMPAT-003: Automatic config migration
- REQ-CORRECT-001: Deterministic evaluation
- REQ-CORRECT-002: Conflict resolution algorithm
- REQ-CORRECT-003: Circular propagation detection
- REQ-ERROR-001: Invalid rule rejection
- REQ-ERROR-002: Corrupt cache recovery
- REQ-VALID-001: Lazy import call validation
- REQ-VALID-002: Package consistency validation
- REQ-CONFIG-001: Schema validation
- REQ-CONFIG-002: Schema versioning
- REQ-UX-001: Clear debug output
- REQ-TEST-001: Code coverage >80%
- REQ-TEST-002: Performance benchmarks pass

### Important Requirements (SHOULD)
- REQ-PERF-003: Incremental processing <500ms
- REQ-PERF-004: Memory usage <500MB
- REQ-ERROR-003: Cache circuit breaker
- REQ-UX-002: Progress indication

### Definition of Done

Implementation is complete when:
- ✅ All MUST requirements have passing tests
- ✅ All SHOULD requirements implemented or explicitly deferred
- ✅ Code coverage >80%
- ✅ Performance benchmarks pass
- ✅ Migration validation shows 100% match (or approved exceptions)
- ✅ Documentation complete
- ✅ User workflows validated
