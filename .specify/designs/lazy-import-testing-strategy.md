# Lazy Import System - Testing Strategy

## Overview

This document defines the comprehensive testing approach for the lazy import system redesign, including unit tests, integration tests, performance benchmarks, and property-based tests.

---

## Testing Pyramid

```
                    ┌─────────────────┐
                    │  E2E Tests (5)  │  Full workflow validation
                    └─────────────────┘
                  ┌──────────────────────┐
                  │ Integration Tests    │  Component interaction
                  │      (15-20)         │
                  └──────────────────────┘
              ┌────────────────────────────────┐
              │     Unit Tests (100+)          │  Individual components
              └────────────────────────────────┘
          ┌──────────────────────────────────────────┐
          │  Property-Based Tests (10-15)            │  Invariants & edge cases
          └──────────────────────────────────────────┘
```

---

## Unit Testing Strategy

### Coverage Targets

| Component | Coverage Target | Priority |
|-----------|----------------|----------|
| Rule Engine | >90% | Critical |
| Propagation Graph | >85% | Critical |
| Code Generator | >80% | High |
| Validator | >85% | High |
| Cache System | >80% | High |
| CLI Commands | >70% | Medium |
| Overall | >80% | Critical |

### Test Organization

```
tests/
├── unit/
│   ├── export_manager/
│   │   ├── test_rules.py           # Rule engine tests
│   │   ├── test_graph.py           # Propagation graph tests
│   │   ├── test_generator.py       # Code generator tests
│   │   └── test_cache.py           # Cache system tests
│   │
│   ├── validator/
│   │   ├── test_resolver.py        # Import resolver tests
│   │   ├── test_consistency.py     # Consistency checker tests
│   │   └── test_scanner.py         # Call validator tests
│   │
│   └── common/
│       ├── test_ast_utils.py
│       ├── test_config.py
│       └── test_types.py
│
├── integration/
│   ├── test_full_pipeline.py       # End-to-end pipeline
│   ├── test_migration.py           # Migration scenarios
│   ├── test_incremental.py         # Incremental updates
│   └── test_error_handling.py      # Error scenarios
│
├── performance/
│   ├── test_benchmarks.py          # Performance benchmarks
│   ├── test_cache_performance.py   # Cache effectiveness
│   └── test_memory_usage.py        # Memory profiling
│
├── property/
│   ├── test_determinism.py         # Deterministic behavior
│   ├── test_idempotence.py         # Idempotent operations
│   └── test_invariants.py          # System invariants
│
└── fixtures/
    ├── simple/                     # Simple test cases
    ├── complex/                    # Complex scenarios
    └── edge_cases/                 # Edge cases
```

---

## Unit Test Examples

### Rule Engine Tests

```python
# tests/unit/export_manager/test_rules.py

import pytest
from codeweaver.tools.lazy_imports.export_manager.rules import (
    RuleEngine, Rule, RuleAction, PropagationLevel
)


class TestRuleEngine:
    """Test suite for rule engine."""

    def test_exact_name_match(self):
        """Rule with exact name match should include export."""
        rule = Rule(
            name="include-version",
            priority=900,
            match={"name_exact": "__version__"},
            action=RuleAction.INCLUDE
        )
        engine = RuleEngine([rule])

        result = engine.evaluate("__version__", "codeweaver.core", "variable")

        assert result.action == RuleAction.INCLUDE
        assert result.matched_rule.name == "include-version"
        assert result.propagation == PropagationLevel.PARENT

    def test_pattern_match(self):
        """Rule with regex pattern should match correctly."""
        rule = Rule(
            name="include-get-functions",
            priority=800,
            match={"name_pattern": r"^get_"},
            action=RuleAction.INCLUDE
        )
        engine = RuleEngine([rule])

        result = engine.evaluate("get_config", "codeweaver.core", "function")

        assert result.action == RuleAction.INCLUDE
        assert result.matched_rule.name == "include-get-functions"

    def test_priority_ordering(self):
        """Higher priority rule should win over lower priority."""
        rules = [
            Rule("exclude-all", priority=100,
                 match={"name_pattern": ".*"}, action=RuleAction.EXCLUDE),
            Rule("include-version", priority=900,
                 match={"name_exact": "__version__"}, action=RuleAction.INCLUDE),
        ]
        engine = RuleEngine(rules)

        result = engine.evaluate("__version__", "any.module", "variable")

        assert result.action == RuleAction.INCLUDE
        assert result.matched_rule.name == "include-version"

    def test_lexicographic_tiebreak(self):
        """Same priority: alphabetically first rule name wins."""
        rules = [
            Rule("zzz-exclude", priority=500,
                 match={"name_pattern": "test"}, action=RuleAction.EXCLUDE),
            Rule("aaa-include", priority=500,
                 match={"name_pattern": "test"}, action=RuleAction.INCLUDE),
        ]
        engine = RuleEngine(rules)

        result = engine.evaluate("test", "module", "class")

        assert result.action == RuleAction.INCLUDE
        assert result.matched_rule.name == "aaa-include"

    def test_no_matching_rule(self):
        """When no rule matches, should return NO_DECISION."""
        engine = RuleEngine([])

        result = engine.evaluate("something", "module", "class")

        assert result.action == RuleAction.NO_DECISION
        assert result.matched_rule is None

    def test_module_pattern_match(self):
        """Rule should match on module pattern."""
        rule = Rule(
            name="types-propagate",
            priority=700,
            match={
                "name_pattern": r"^[A-Z][a-zA-Z0-9]*$",
                "module_pattern": r".*\.types(\..*)?"
            },
            action=RuleAction.INCLUDE,
            propagate=PropagationLevel.PARENT
        )
        engine = RuleEngine([rule])

        result = engine.evaluate("MyType", "codeweaver.core.types", "class")

        assert result.action == RuleAction.INCLUDE
        assert result.propagation == PropagationLevel.PARENT

    def test_member_type_filter(self):
        """Rule should filter by member type."""
        rule = Rule(
            name="classes-only",
            priority=600,
            match={
                "name_pattern": ".*",
                "member_type": "class"
            },
            action=RuleAction.INCLUDE
        )
        engine = RuleEngine([rule])

        # Class should match
        result_class = engine.evaluate("MyClass", "module", "class")
        assert result_class.action == RuleAction.INCLUDE

        # Function should not match
        result_func = engine.evaluate("my_function", "module", "function")
        assert result_func.action == RuleAction.NO_DECISION


class TestRuleLoading:
    """Test suite for rule loading and validation."""

    def test_load_yaml_rules(self):
        """Should load rules from YAML file."""
        yaml_content = """
schema_version: "1.0"
rules:
  - name: "test-rule"
    priority: 500
    match:
      name_pattern: "^test_"
    action: include
"""
        path = write_temp_file("rules.yaml", yaml_content)

        rules = load_rules(path)

        assert len(rules) == 1
        assert rules[0].name == "test-rule"
        assert rules[0].priority == 500

    def test_invalid_yaml_syntax(self):
        """Should reject invalid YAML with clear error."""
        yaml_content = 'name: "unclosed'
        path = write_temp_file("bad.yaml", yaml_content)

        with pytest.raises(YAMLSyntaxError) as exc:
            load_rules(path)

        assert "Invalid YAML syntax" in str(exc.value)
        assert path.name in str(exc.value)

    def test_schema_validation(self):
        """Should validate rules against schema."""
        yaml_content = """
rules:
  - name: "invalid"
    priority: 1500  # Exceeds maximum
    action: include
"""
        path = write_temp_file("invalid.yaml", yaml_content)

        with pytest.raises(SchemaValidationError) as exc:
            load_rules(path)

        assert "priority" in str(exc.value)
        assert "maximum: 1000" in str(exc.value)

    def test_unsupported_schema_version(self):
        """Should reject unsupported schema versions."""
        yaml_content = """
schema_version: "99.0"
rules: []
"""
        path = write_temp_file("future.yaml", yaml_content)

        with pytest.raises(UnsupportedSchemaVersion) as exc:
            load_rules(path)

        assert "99.0" in str(exc.value)
        assert "Supported versions:" in str(exc.value)
```

### Propagation Graph Tests

```python
# tests/unit/export_manager/test_graph.py

import pytest
from codeweaver.tools.lazy_imports.export_manager.graph import (
    PropagationGraph, ExportNode, PropagationLevel
)


class TestPropagationGraph:
    """Test suite for propagation graph."""

    def test_simple_propagation_to_parent(self):
        """Exports with PARENT propagation should appear in parent __all__."""
        graph = PropagationGraph()

        # Add export from child module
        graph.add_export(ExportNode(
            name="MyClass",
            module="codeweaver.core.types",
            propagation=PropagationLevel.PARENT
        ))

        # Build graph
        manifests = graph.build_manifests()

        # Check parent includes child export
        parent_manifest = manifests["codeweaver.core"]
        assert "MyClass" in parent_manifest.propagated_exports

    def test_propagation_to_root(self):
        """Exports with ROOT propagation should reach top-level package."""
        graph = PropagationGraph()

        # Add export deep in hierarchy
        graph.add_export(ExportNode(
            name="TopLevelType",
            module="codeweaver.core.deep.nested.types",
            propagation=PropagationLevel.ROOT
        ))

        manifests = graph.build_manifests()

        # Check all levels up to root
        assert "TopLevelType" in manifests["codeweaver.core.deep.nested"].own_exports
        assert "TopLevelType" in manifests["codeweaver.core.deep"].propagated_exports
        assert "TopLevelType" in manifests["codeweaver.core"].propagated_exports
        assert "TopLevelType" in manifests["codeweaver"].propagated_exports

    def test_duplicate_detection(self):
        """Same export from different submodules should be deduplicated."""
        graph = PropagationGraph()

        # Two modules export "Config"
        graph.add_export(ExportNode(
            name="Config",
            module="codeweaver.core.config",
            propagation=PropagationLevel.PARENT
        ))
        graph.add_export(ExportNode(
            name="Config",
            module="codeweaver.utils.config",
            propagation=PropagationLevel.PARENT
        ))

        manifests = graph.build_manifests()

        # Parent should list "Config" only once
        parent = manifests["codeweaver"]
        config_count = parent.all_exports.count("Config")
        assert config_count == 1

    def test_circular_propagation_detection(self):
        """Should detect and reject circular propagation."""
        # This would require malformed rules creating cycles
        graph = PropagationGraph()

        # Simulate circular dependency (would need special setup)
        # In practice, this is prevented by module hierarchy

        with pytest.raises(PropagationCycleError) as exc:
            # Create circular scenario
            create_circular_propagation(graph)
            graph.build_manifests()

        assert "Circular propagation detected" in str(exc.value)

    def test_no_propagation(self):
        """Exports with NONE propagation should not propagate."""
        graph = PropagationGraph()

        graph.add_export(ExportNode(
            name="InternalClass",
            module="codeweaver.core.internal",
            propagation=PropagationLevel.NONE
        ))

        manifests = graph.build_manifests()

        # Should exist in own module
        assert "InternalClass" in manifests["codeweaver.core.internal"].own_exports

        # Should NOT propagate to parent
        assert "InternalClass" not in manifests["codeweaver.core"].propagated_exports
```

### Cache Tests

```python
# tests/unit/export_manager/test_cache.py

import pytest
from codeweaver.tools.lazy_imports.common.cache import (
    JSONAnalysisCache, AnalysisResult
)


class TestJSONAnalysisCache:
    """Test suite for JSON-based analysis cache."""

    def test_cache_hit(self):
        """Should return cached analysis for unchanged file."""
        cache = JSONAnalysisCache()
        analysis = AnalysisResult(exports=["Foo", "Bar"])

        # Store in cache
        cache.put("module.py", "hash123", analysis)

        # Retrieve from cache
        cached = cache.get("module.py", "hash123")

        assert cached == analysis

    def test_cache_miss_different_hash(self):
        """Should return None when file hash changes."""
        cache = JSONAnalysisCache()
        analysis = AnalysisResult(exports=["Foo"])

        cache.put("module.py", "hash123", analysis)

        # Different hash = cache miss
        cached = cache.get("module.py", "hash456")

        assert cached is None

    def test_cache_invalidation(self):
        """Should invalidate cache entry."""
        cache = JSONAnalysisCache()
        cache.put("module.py", "hash123", AnalysisResult(exports=["Foo"]))

        cache.invalidate("module.py")

        cached = cache.get("module.py", "hash123")
        assert cached is None

    def test_corrupt_cache_recovery(self):
        """Should recover from corrupt cache file."""
        cache = JSONAnalysisCache()

        # Corrupt the cache file
        cache_path = cache._get_cache_path("module.py")
        cache_path.write_text("{invalid json")

        # Should handle gracefully
        cached = cache.get("module.py", "hash123")
        assert cached is None

    def test_cache_persistence(self):
        """Should persist across cache instances."""
        cache1 = JSONAnalysisCache()
        analysis = AnalysisResult(exports=["Persistent"])

        cache1.put("module.py", "hash123", analysis)

        # New cache instance
        cache2 = JSONAnalysisCache()
        cached = cache2.get("module.py", "hash123")

        assert cached == analysis
```

---

## Integration Testing Strategy

### Test Scenarios

#### Scenario 1: Full Pipeline
```python
# tests/integration/test_full_pipeline.py

def test_generate_and_validate_workflow():
    """Complete workflow: generate exports then validate."""
    # Setup: Create test modules
    create_test_module("codeweaver/test_module.py", """
class TestClass:
    pass

def test_function():
    pass
""")

    # Execute: Generate exports
    export_manager = ExportManager()
    result = export_manager.generate_all()

    assert result.generated_count > 0
    assert "TestClass" in result.exports

    # Validate: Check consistency
    validator = LazyImportValidator()
    validation = validator.validate_all()

    assert len(validation.errors) == 0
    assert validation.success
```

#### Scenario 2: Incremental Updates
```python
def test_incremental_file_update():
    """Modifying single file should trigger incremental update."""
    # Initial state
    processor = LazyImportProcessor()
    initial_result = processor.process_all()

    # Modify one file
    modify_file("codeweaver/core/types.py", add_class="NewType")

    # Incremental update
    update_result = processor.process_all()

    # Only modified file should be reprocessed
    assert update_result.files_reprocessed == 1
    assert update_result.cache_hits > 0
    assert "NewType" in update_result.exports
```

#### Scenario 3: Migration Validation
```python
def test_old_vs_new_system_equivalence():
    """New system should produce identical output to old system."""
    # Run old system
    old_results = run_old_system()

    # Run new system
    new_results = run_new_system()

    # Compare
    comparison = compare_results(old_results, new_results)

    assert comparison.match_rate == 1.0
    assert len(comparison.differences) == 0
```

---

## Performance Testing Strategy

### Benchmarks

```python
# tests/performance/test_benchmarks.py

import pytest
import time


@pytest.mark.benchmark
class TestPerformanceBenchmarks:
    """Performance benchmark suite."""

    def test_processing_speed_target(self):
        """Full pipeline should complete in <5s for 500 modules."""
        processor = LazyImportProcessor()

        # Create 500 test modules
        create_test_modules(count=500)

        # Measure processing time
        start = time.time()
        result = processor.process_all()
        duration = time.time() - start

        # Verify target met
        assert duration < 5.0, f"Processing took {duration}s, expected <5s"
        assert result.success

    def test_cache_effectiveness(self):
        """Cache hit rate should be >90% on second run."""
        processor = LazyImportProcessor()

        # First run (warm cache)
        processor.process_all()

        # Second run (should use cache)
        result = processor.process_all()

        # Verify cache effectiveness
        assert result.cache_hit_rate > 0.90, \
            f"Cache hit rate {result.cache_hit_rate}, expected >0.90"

    def test_incremental_update_speed(self):
        """Single file update should complete in <500ms."""
        processor = LazyImportProcessor()

        # Initial state
        processor.process_all()

        # Modify one file
        modify_file("test_module.py")

        # Measure incremental update
        start = time.time()
        processor.process_all()
        duration = time.time() - start

        assert duration < 0.5, f"Incremental update took {duration}s, expected <0.5s"

    def test_memory_usage(self):
        """Memory usage should stay under 500MB for large codebase."""
        import tracemalloc

        processor = LazyImportProcessor()
        create_test_modules(count=1000)

        tracemalloc.start()
        processor.process_all()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / (1024 * 1024)
        assert peak_mb < 500, f"Peak memory {peak_mb}MB, expected <500MB"
```

---

## Property-Based Testing Strategy

### Invariants to Test

```python
# tests/property/test_determinism.py

from hypothesis import given, strategies as st


# Custom strategies
def rule_strategy():
    """Generate random but valid rules."""
    return st.builds(
        Rule,
        name=st.text(min_size=1, max_size=50),
        priority=st.integers(min_value=0, max_value=1000),
        match=st.dictionaries(
            st.sampled_from(["name_pattern", "module_pattern"]),
            st.text(min_size=1)
        ),
        action=st.sampled_from([RuleAction.INCLUDE, RuleAction.EXCLUDE])
    )


def export_strategy():
    """Generate random exports."""
    return st.builds(
        Export,
        name=st.text(min_size=1, max_size=50),
        module=st.text(min_size=1, max_size=100),
        member_type=st.sampled_from(["class", "function", "variable"])
    )


@given(
    rules=st.lists(rule_strategy(), min_size=2, max_size=20),
    export=export_strategy()
)
def test_evaluation_is_deterministic(rules, export):
    """Same input should always produce same output."""
    engine1 = RuleEngine(rules)
    engine2 = RuleEngine(rules)

    result1 = engine1.evaluate(export.name, export.module, export.member_type)
    result2 = engine2.evaluate(export.name, export.module, export.member_type)

    assert result1.action == result2.action
    assert result1.matched_rule == result2.matched_rule


@given(exports=st.lists(export_strategy(), min_size=1, max_size=100))
def test_processing_is_idempotent(exports):
    """Processing same exports multiple times should produce same result."""
    processor = LazyImportProcessor()

    result1 = processor.process(exports)
    result2 = processor.process(exports)
    result3 = processor.process(exports)

    assert result1 == result2 == result3


@given(
    rules=st.lists(rule_strategy(), min_size=1),
    exports=st.lists(export_strategy(), min_size=1)
)
def test_no_export_lost(rules, exports):
    """All exports should be accounted for (included or excluded)."""
    engine = RuleEngine(rules)

    processed = []
    for export in exports:
        result = engine.evaluate(export.name, export.module, export.member_type)
        processed.append((export, result))

    # Every export gets a decision
    assert len(processed) == len(exports)
    assert all(result.action != None for _, result in processed)
```

---

## Test Data Strategy

### Fixture Organization

```
tests/fixtures/
├── simple/
│   ├── types.py              # Simple types module
│   ├── functions.py          # Simple functions
│   └── expected_init.py      # Expected __init__.py output
│
├── complex/
│   ├── nested/
│   │   └── deep/
│   │       └── types.py      # Deep nesting scenario
│   ├── multi_exports.py      # Multiple exports
│   └── mixed.py              # Mix of types
│
├── edge_cases/
│   ├── circular.py           # Circular import attempts
│   ├── duplicates.py         # Duplicate exports
│   ├── empty.py              # Empty module
│   └── special_names.py      # __special__ names
│
└── real_world/
    └── snapshot/             # Snapshot of real codebase
        ├── core/
        ├── providers/
        └── utils/
```

### Fixture Helpers

```python
# tests/conftest.py

import pytest
from pathlib import Path


@pytest.fixture
def temp_project(tmp_path):
    """Create temporary project structure."""
    project = tmp_path / "test_project"
    project.mkdir()

    (project / "src").mkdir()
    (project / "src" / "package").mkdir()

    return project


@pytest.fixture
def rule_engine():
    """Standard rule engine with default rules."""
    return RuleEngine(load_default_rules())


@pytest.fixture
def analysis_cache(tmp_path):
    """Temporary analysis cache."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return JSONAnalysisCache(cache_dir)


def create_test_module(path: str, content: str):
    """Helper to create test module files."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content)


def create_test_modules(count: int, base_path: str = "test_modules"):
    """Create multiple test modules for benchmarking."""
    for i in range(count):
        create_test_module(
            f"{base_path}/module_{i}.py",
            f"class TestClass{i}: pass"
        )
```

---

## Testing Workflow

### Local Development

```bash
# Run all tests
mise run test

# Run specific test suite
mise run test tests/unit/
mise run test tests/integration/
mise run test tests/performance/

# Run with coverage
mise run test --cov

# Run property-based tests with more examples
mise run test tests/property/ --hypothesis-examples=1000

# Run performance benchmarks
mise run benchmark-lazy-imports
```

### CI Pipeline

```yaml
# .github/workflows/ci.yml

name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup
        run: mise run setup

      - name: Unit Tests
        run: mise run test tests/unit/ --cov

      - name: Integration Tests
        run: mise run test tests/integration/

      - name: Property Tests
        run: mise run test tests/property/ --hypothesis-examples=100

      - name: Coverage Check
        run: |
          coverage report --fail-under=80

  performance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup
        run: mise run setup

      - name: Performance Benchmarks
        run: mise run benchmark-lazy-imports

      - name: Check Performance Targets
        run: |
          # Fails if benchmarks don't meet targets
          python scripts/check-performance.py

  migration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup
        run: mise run setup

      - name: Migration Validation
        run: mise run lazy-imports --validate-migration

      - name: Check Equivalence
        run: |
          # Fails if new system doesn't match old
          python scripts/check-migration.py
```

---

## Test Metrics & Reporting

### Coverage Reporting

```bash
# Generate coverage report
coverage run -m pytest tests/
coverage report
coverage html

# View in browser
open htmlcov/index.html
```

### Performance Tracking

```python
# scripts/track-performance.py

import json
from pathlib import Path
from datetime import datetime


def track_benchmark_results(results):
    """Track performance over time."""
    history_file = Path(".codeweaver/performance-history.json")

    if history_file.exists():
        history = json.loads(history_file.read_text())
    else:
        history = []

    history.append({
        "timestamp": datetime.now().isoformat(),
        "processing_time": results.processing_time,
        "cache_hit_rate": results.cache_hit_rate,
        "memory_peak_mb": results.memory_peak_mb,
    })

    history_file.write_text(json.dumps(history, indent=2))

    # Check for regressions
    if len(history) > 1:
        current = history[-1]
        previous = history[-2]

        if current["processing_time"] > previous["processing_time"] * 1.1:
            print(f"⚠️  Performance regression detected!")
            print(f"   Previous: {previous['processing_time']}s")
            print(f"   Current: {current['processing_time']}s")
            return False

    return True
```

---

## Testing Checklist

### Before Implementation
- [x] Review testing strategy
- [x] Set up test infrastructure
- [x] Create fixture structure
- [x] Configure coverage tools
- [x] Set up CI pipeline

### During Implementation
- [ ] Write unit tests before implementation (TDD)
- [ ] Achieve >80% coverage for each component
- [ ] Add integration tests for workflows
- [ ] Create property-based tests for invariants
- [ ] Run benchmarks regularly

### Before Merge
- [ ] All tests passing
- [ ] Coverage >80%
- [ ] Performance benchmarks meet targets
- [ ] No regressions detected
- [ ] Migration validation passes

### Before Release
- [ ] Full test suite passing
- [ ] Performance targets met
- [ ] Migration thoroughly validated
- [ ] Edge cases covered
- [ ] Documentation updated

---

## Success Criteria

Testing is complete when:

✅ **Coverage**:
- Overall coverage >80%
- Critical components >85%
- All public APIs tested

✅ **Performance**:
- All benchmarks passing
- No performance regressions
- Memory usage within limits

✅ **Correctness**:
- All property-based tests passing
- Migration validation shows 100% match
- No known edge case failures

✅ **Quality**:
- No flaky tests
- Fast test execution (<2 minutes for full suite)
- Clear test documentation
