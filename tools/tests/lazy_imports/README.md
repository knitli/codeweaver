<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Lazy Import System Tests

Comprehensive test suite for the lazy import system redesign.

## Overview

This test suite provides comprehensive coverage for all components of the lazy import system, including:

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions and workflows
- **Performance Benchmarks**: Verify performance requirements
- **Property-Based Tests**: Test invariants and edge cases (via hypothesis)

## Test Structure

```
tests/tools/lazy_imports/
├── __init__.py
├── README.md               # This file
├── conftest.py             # Shared fixtures and test utilities
├── test_types.py           # Common types and data structures
├── test_rules.py           # Rule Engine tests
├── test_graph.py           # Propagation Graph tests
├── test_cache.py           # Analysis Cache tests
├── test_generator.py       # Code Generator tests (already exists)
├── test_validator.py       # Import Validator tests
├── test_integration.py     # End-to-end workflows
└── test_benchmarks.py      # Performance benchmarks
```

## Running Tests

### All Tests
```bash
mise run test tests/tools/lazy_imports/
```

### By Category
```bash
# Unit tests only
mise run test tests/tools/lazy_imports/test_types.py
mise run test tests/tools/lazy_imports/test_rules.py
mise run test tests/tools/lazy_imports/test_graph.py
mise run test tests/tools/lazy_imports/test_cache.py
mise run test tests/tools/lazy_imports/test_validator.py

# Integration tests
mise run test tests/tools/lazy_imports/test_integration.py -m integration

# Performance benchmarks
mise run test tests/tools/lazy_imports/test_benchmarks.py -m benchmark
```

### With Coverage
```bash
mise run test --cov=src/codeweaver/tools/lazy_imports tests/tools/lazy_imports/
```

### Fast Tests Only
```bash
mise run test --profile fast tests/tools/lazy_imports/
```

## Test Coverage Targets

Per component targets from `.specify/designs/lazy-import-testing-strategy.md`:

| Component | Coverage Target | Test File |
|-----------|----------------|-----------|
| Rule Engine | >90% | `test_rules.py` |
| Propagation Graph | >85% | `test_graph.py` |
| Analysis Cache | >85% | `test_cache.py` |
| Code Generator | >80% | `test_generator.py` |
| Validator | >80% | `test_validator.py` |
| Common Types | >80% | `test_types.py` |
| **Overall** | **>80%** | All files |

## Test Categories

### Unit Tests

Test individual components in isolation:

- **test_types.py**: Data structures, enums, and basic types
- **test_rules.py**: Rule engine logic, pattern matching, priority ordering
- **test_graph.py**: Graph construction, propagation, topological sorting
- **test_cache.py**: Cache operations, persistence, invalidation
- **test_generator.py**: Code generation, sentinel preservation, validation
- **test_validator.py**: Import resolution, consistency checking

### Integration Tests

Test component interactions:

- **test_integration.py**:
  - Full pipeline workflows (analyze → generate → validate)
  - Cache integration and effectiveness
  - Rule changes invalidate cache
  - Incremental updates
  - Error handling and recovery

### Performance Tests

Test performance requirements:

- **test_benchmarks.py**:
  - **REQ-PERF-001**: Processing <5s for 500 modules
  - **REQ-PERF-002**: Cache hit rate >90%
  - **REQ-PERF-003**: Incremental processing <500ms
  - **REQ-PERF-004**: Memory usage <500MB
  - Scalability tests
  - Concurrent access tests

## Shared Fixtures

`conftest.py` provides shared fixtures used across tests:

### Directory Fixtures
- `temp_cache_dir`: Temporary cache directory
- `temp_project`: Temporary project structure
- `nested_module_structure`: Nested package structure for propagation tests

### Configuration Fixtures
- `sample_rules`: Sample rule configuration (dict format)
- `sample_yaml_rules`: Sample rules in YAML format
- `rule_engine`: Configured RuleEngine instance
- `analysis_cache`: Fresh AnalysisCache instance

### Module Content Fixtures
- `simple_python_module`: Simple module with public/private members
- `complex_python_module`: Complex module with multiple types
- Utility functions: `create_test_module`, `create_test_modules`

## Key Test Scenarios

### Rule Engine

```python
def test_priority_ordering():
    """Higher priority rule wins over lower priority."""

def test_lexicographic_tiebreak():
    """Same priority: alphabetically first rule name wins."""

def test_pattern_matching():
    """Regex patterns match correctly."""

def test_module_path_matching():
    """Module pattern matching works."""
```

### Propagation Graph

```python
def test_simple_propagation_to_parent():
    """PARENT propagation to direct parent."""

def test_propagation_to_root():
    """ROOT propagation to package root."""

def test_no_propagation():
    """NONE propagation stays in module."""

def test_deduplication():
    """Duplicate exports handled correctly."""
```

### Analysis Cache

```python
def test_cache_hit():
    """Cached analysis returned for unchanged file."""

def test_cache_miss_different_hash():
    """File changes invalidate cache."""

def test_corrupt_cache_recovery():
    """Recover from corrupt cache gracefully."""

def test_cache_persistence():
    """Cache persists across instances."""
```

### Code Generator

```python
def test_preserve_manual_code():
    """Manual code above sentinel preserved."""

def test_type_checking_blocks():
    """TYPE_CHECKING imports separated."""

def test_all_list_sorted():
    """__all__ list sorted alphabetically."""

def test_atomic_write():
    """Writes are atomic with backup."""
```

### Validator

```python
def test_valid_lazy_import_call():
    """Valid lazy_import passes validation."""

def test_broken_lazy_import_module():
    """Broken module path detected."""

def test_consistency_checking():
    """__all__ and _dynamic_imports match."""
```

### Integration

```python
def test_full_pipeline():
    """Complete workflow: analyze → generate → validate."""

def test_cache_speeds_up_second_run():
    """Cache improves second run performance."""

def test_rule_changes_invalidate():
    """Rule changes trigger reprocessing."""
```

### Benchmarks

```python
@pytest.mark.benchmark
def test_processing_speed_target():
    """Full pipeline <5s for 500 modules."""

@pytest.mark.benchmark
def test_cache_effectiveness():
    """Cache hit rate >90% on second run."""

@pytest.mark.benchmark
def test_memory_usage():
    """Memory usage <500MB for 1000 modules."""
```

## Property-Based Testing

For rule engine invariants, use hypothesis:

```python
from hypothesis import given, strategies as st

@given(
    rules=st.lists(rule_strategy(), min_size=2, max_size=20),
    export=export_strategy()
)
def test_determinism(rules, export):
    """Same input always produces same output."""
    engine1 = RuleEngine(rules)
    engine2 = RuleEngine(rules)

    result1 = engine1.evaluate(...)
    result2 = engine2.evaluate(...)

    assert result1 == result2
```

## Test Markers

Use pytest markers to filter tests:

```bash
# Run only integration tests
pytest -m integration

# Run only benchmarks
pytest -m benchmark

# Skip slow tests
pytest -m "not slow"

# Run external API tests
pytest -m external_api
```

## CI Integration

Tests run in CI pipeline:

```yaml
test:
  - Unit tests with coverage
  - Integration tests
  - Property-based tests (100 examples)
  - Coverage report (fail if <80%)

performance:
  - Run benchmarks
  - Check performance targets
  - Track performance over time
```

## Writing New Tests

### Guidelines

1. **Use fixtures**: Leverage shared fixtures from `conftest.py`
2. **Test one thing**: Each test should verify one specific behavior
3. **Descriptive names**: Test names should describe what they verify
4. **Clear assertions**: Use specific assertions with helpful messages
5. **Document edge cases**: Comment on why edge cases matter

### Example Test

```python
def test_rule_priority_ordering(rule_engine):
    """Higher priority rule should win over lower priority."""
    # Arrange
    rules = [
        Rule("low-priority", priority=100, ...),
        Rule("high-priority", priority=900, ...),
    ]
    engine = RuleEngine(rules)

    # Act
    result = engine.evaluate("test", "module", MemberType.CLASS)

    # Assert
    assert result.action == RuleAction.INCLUDE
    assert result.matched_rule.name == "high-priority"
```

## Troubleshooting

### Import Errors

If tests fail with import errors:
1. Check that the main codebase builds: `mise run check`
2. Verify test environment: `mise run test --collect-only`
3. Check fixture imports in `conftest.py`

### Fixture Not Found

If fixture not found:
1. Check fixture is defined in `conftest.py`
2. Verify fixture name matches usage
3. Ensure `conftest.py` is in correct directory

### Performance Test Failures

If benchmarks fail:
1. Check system resources (CPU, memory)
2. Run benchmarks multiple times (variance)
3. Adjust timeouts if on slower hardware
4. Use `--benchmark` flag explicitly

## Coverage Reports

Generate detailed coverage report:

```bash
# Run tests with coverage
mise run test --cov=src/codeweaver/tools/lazy_imports \
              --cov-report=html \
              tests/tools/lazy_imports/

# View HTML report
open htmlcov/index.html
```

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
- No known edge case failures
- Clear test documentation

✅ **Quality**:
- No flaky tests
- Fast test execution (<2 minutes for full suite)
- Clear failure messages
