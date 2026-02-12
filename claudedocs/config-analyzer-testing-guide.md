# ConfigChangeAnalyzer Testing Guide

## Quick Start

### Run All Tests
```bash
pytest tests/unit/engine/services/test_config_analyzer.py \
        tests/integration/test_config_validation_flow.py -v
```

### Expected Output
```
tests/unit/engine/services/test_config_analyzer.py::TestAnalyzeCurrentConfig::test_no_checkpoint_returns_none PASSED
tests/unit/engine/services/test_config_analyzer.py::TestAnalyzeCurrentConfig::test_loads_checkpoint_metadata PASSED
tests/unit/engine/services/test_config_analyzer.py::TestAnalyzeCurrentConfig::test_calls_analyze_with_current_config PASSED
...
tests/integration/test_config_validation_flow.py::TestFullValidationWorkflow::test_analyze_current_config_with_checkpoint PASSED
...

============ 56 passed in 2.34s ============
```

---

## Test File Locations

| Test Suite | File | Tests | Purpose |
|-----------|------|-------|---------|
| **Unit** | `tests/unit/engine/services/test_config_analyzer.py` | 37 | Direct instantiation, mocked dependencies |
| **Integration** | `tests/integration/test_config_validation_flow.py` | 19 | Full DI container, real services |

---

## Running Specific Tests

### Run Single Test Class
```bash
# Test model compatibility
pytest tests/unit/engine/services/test_config_analyzer.py::TestModelCompatibility -v

# Test dimension reduction
pytest tests/unit/engine/services/test_config_analyzer.py::TestAnalyzeConfigChangeDimensionReduction -v

# Test empirical data
pytest tests/unit/engine/services/test_config_analyzer.py::TestMatryoshkaImpactEstimation -v
```

### Run Single Test Method
```bash
pytest tests/unit/engine/services/test_config_analyzer.py::TestMatryoshkaImpactEstimation::test_voyage_code_3_empirical_2048_to_512 -v
```

### Run Integration Tests Only
```bash
pytest tests/integration/test_config_validation_flow.py -v
```

### Run Unit Tests Only
```bash
pytest tests/unit/engine/services/test_config_analyzer.py -v
```

---

## Test Coverage Analysis

### Generate Coverage Report
```bash
pytest tests/unit/engine/services/test_config_analyzer.py \
        tests/integration/test_config_validation_flow.py \
        --cov=codeweaver.engine.services.config_analyzer \
        --cov-report=html \
        --cov-report=term-missing
```

### View HTML Report
```bash
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
```

### Expected Coverage
- Line Coverage: >95%
- Branch Coverage: >90%
- Covered Methods:
  - ✅ `analyze_current_config()`
  - ✅ `analyze_config_change()`
  - ✅ `validate_config_change()`
  - ✅ `_models_compatible()`
  - ✅ `_estimate_matryoshka_impact()`
  - ✅ `_simulate_config_change()`
  - ✅ `_is_valid_quantization()`
  - ✅ All helper methods

---

## Common Test Scenarios

### Scenario 1: Test No Configuration Change
```bash
pytest tests/unit/engine/services/test_config_analyzer.py::TestAnalyzeConfigChangeNoChange::test_identical_config_returns_none_impact -v
```
**Expects**: NONE impact, no transformations

### Scenario 2: Test Dimension Reduction
```bash
pytest tests/unit/engine/services/test_config_analyzer.py::TestAnalyzeConfigChangeDimensionReduction -v
```
**Expects**: TRANSFORMABLE impact, accurate empirical data

### Scenario 3: Test Breaking Changes
```bash
pytest tests/unit/engine/services/test_config_analyzer.py::TestAnalyzeConfigChangeBreaking -v
```
**Expects**: BREAKING impact, helpful recommendations

### Scenario 4: Test Full Workflow
```bash
pytest tests/integration/test_config_validation_flow.py::TestFullValidationWorkflow -v
```
**Expects**: Complete workflows without errors

---

## Debugging Failed Tests

### Increase Verbosity
```bash
pytest tests/unit/engine/services/test_config_analyzer.py::TestMatryoshkaImpactEstimation -vv
```

### Show Print Statements
```bash
pytest tests/unit/engine/services/test_config_analyzer.py::TestMatryoshkaImpactEstimation -s
```

### Show Local Variables on Failure
```bash
pytest tests/unit/engine/services/test_config_analyzer.py::TestMatryoshkaImpactEstimation -l
```

### Run with Detailed Traceback
```bash
pytest tests/unit/engine/services/test_config_analyzer.py::TestMatryoshkaImpactEstimation --tb=long
```

### Run Single Test with Full Debug
```bash
pytest tests/unit/engine/services/test_config_analyzer.py::TestMatryoshkaImpactEstimation::test_voyage_code_3_empirical_2048_to_512 -vvs -l --tb=long
```

---

## CI/CD Integration

### GitHub Actions Example
```yaml
name: ConfigChangeAnalyzer Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: "3.13"

      - name: Install dependencies
        run: |
          python -m pip install -e ".[dev]"
          mise run sync

      - name: Run unit tests
        run: |
          pytest tests/unit/engine/services/test_config_analyzer.py \
                  --cov=codeweaver.engine.services.config_analyzer \
                  --cov-report=xml

      - name: Run integration tests
        run: |
          pytest tests/integration/test_config_validation_flow.py -v

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

### Local Pre-commit Hook
```bash
#!/bin/bash
# .git/hooks/pre-commit

pytest tests/unit/engine/services/test_config_analyzer.py \
        tests/integration/test_config_validation_flow.py \
        --tb=short -q

if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
```

---

## Test Execution Performance

### Time Breakdown

| Test Suite | Count | Typical Time | Per Test |
|-----------|-------|-------------|----------|
| Unit Tests | 37 | ~1.2 seconds | 32ms |
| Integration Tests | 19 | ~0.8 seconds | 42ms |
| **Total** | **56** | **~2.0 seconds** | **36ms** |

### Optimize Test Execution
```bash
# Run in parallel (if pytest-xdist installed)
pip install pytest-xdist
pytest tests/unit/engine/services/test_config_analyzer.py \
        tests/integration/test_config_validation_flow.py \
        -n auto  # Use all CPU cores
```

### Profile Test Execution
```bash
pytest tests/unit/engine/services/test_config_analyzer.py \
        tests/integration/test_config_validation_flow.py \
        --durations=10  # Show 10 slowest tests
```

---

## Troubleshooting

### Issue: Import Errors
```
ImportError: No module named 'codeweaver'
```
**Solution**: Install package in development mode:
```bash
cd /home/knitli/codeweaver
pip install -e .
```

### Issue: Tests Timeout
```
TimeoutError: test took longer than X seconds
```
**Solution**: Increase timeout or investigate mock configuration:
```bash
pytest tests/unit/engine/services/test_config_analyzer.py \
        --timeout=30 \
        -vv -s
```

### Issue: Mock Assertion Failures
```
AssertionError: expected call but not called
```
**Solution**: Verify mock setup in fixture:
```python
# Check mock is being passed correctly
async def test_example(config_analyzer):
    print(config_analyzer._models_compatible)  # Should not be None
    assert callable(config_analyzer._models_compatible)
```

### Issue: Async Test Failures
```
RuntimeError: Event loop is closed
```
**Solution**: Ensure pytest-asyncio is installed:
```bash
pip install pytest-asyncio
```

---

## Test Maintenance

### When ConfigChangeAnalyzer Changes

1. **Run full test suite**:
   ```bash
   pytest tests/unit/engine/services/test_config_analyzer.py \
           tests/integration/test_config_validation_flow.py -v
   ```

2. **Check coverage**:
   ```bash
   pytest tests/unit/engine/services/test_config_analyzer.py \
           --cov=codeweaver.engine.services.config_analyzer \
           --cov-report=term-missing
   ```

3. **Update tests if needed**:
   - Edit test fixture if interface changes
   - Add new test methods for new features
   - Update empirical data tests if algorithms change

4. **Verify integration**:
   ```bash
   pytest tests/integration/test_config_validation_flow.py -v
   ```

### When Empirical Data Updates

1. **Update `_estimate_matryoshka_impact()` method**
2. **Update all corresponding tests**:
   - `TestMatryoshkaImpactEstimation::test_voyage_code_3_empirical_*`
3. **Add new tests for new data points**
4. **Verify all tests pass**

### Adding New Tests

1. **Choose test file**:
   - Unit test → `test_config_analyzer.py`
   - Integration test → `test_config_validation_flow.py`

2. **Pick test class** (or create new one):
   ```python
   class TestNewFeature:
       """Tests for new feature description."""

       async def test_scenario_name(self, config_analyzer):
           """Test description."""
           # Arrange
           # Act
           result = await config_analyzer.method(...)
           # Assert
           assert result is not None
   ```

3. **Run test**:
   ```bash
   pytest tests/unit/engine/services/test_config_analyzer.py::TestNewFeature -v
   ```

---

## Example Test Walkthrough

### Test: Dimension Reduction to Empirical Data
```python
async def test_dimension_reduction_returns_transformable(
    config_analyzer,
    collection_metadata,
    embedding_config,
):
    """Test that dimension reduction returns TRANSFORMABLE impact."""
    from codeweaver.engine.managers.checkpoint_manager import ChangeImpact

    # ARRANGE: Set up test data
    collection_metadata.dimension = 2048  # Original
    embedding_config.dimension = 1024    # Reduced
    config_analyzer._models_compatible = Mock(return_value=True)
    config_analyzer._estimate_matryoshka_impact = Mock(
        return_value="~0.5% (empirical)"
    )

    # ACT: Call the method
    analysis = await config_analyzer.analyze_config_change(
        old_meta=collection_metadata,
        new_config=embedding_config,
        vector_count=1000,
    )

    # ASSERT: Verify results
    assert analysis.impact == ChangeImpact.TRANSFORMABLE
    assert len(analysis.transformations) == 1
    assert analysis.transformations[0].type == "dimension_reduction"
```

**How to run**:
```bash
pytest tests/unit/engine/services/test_config_analyzer.py::TestAnalyzeConfigChangeDimensionReduction::test_dimension_reduction_returns_transformable -v
```

**Expected output**:
```
tests/unit/engine/services/test_config_analyzer.py::TestAnalyzeConfigChangeDimensionReduction::test_dimension_reduction_returns_transformable PASSED
```

---

## Advanced: Custom Markers

### Mark slow tests
```python
@pytest.mark.slow
async def test_large_collection_performance(config_analyzer):
    # Test with 10M vectors
    pass
```

**Run only fast tests**:
```bash
pytest tests/unit/engine/services/test_config_analyzer.py -m "not slow"
```

### Mark empirical data tests
```python
@pytest.mark.empirical
def test_voyage_code_3_empirical_2048_to_512(config_analyzer):
    # Uses empirical benchmark data
    pass
```

**Run only empirical data tests**:
```bash
pytest tests/unit/engine/services/test_config_analyzer.py -m "empirical"
```

---

## Validation Checklist

Before merging to main:

- [ ] All 56 tests pass: `pytest tests/unit/engine/services/test_config_analyzer.py tests/integration/test_config_validation_flow.py`
- [ ] Coverage >90%: `--cov-report=term-missing`
- [ ] No warnings: No deprecation or lint warnings
- [ ] Unit tests fast: <2 seconds total
- [ ] Integration tests work: `pytest tests/integration/test_config_validation_flow.py -v`
- [ ] Empirical data verified: All 5 Voyage-3 data points correct
- [ ] Documentation updated: This guide reflects current tests

---

## Getting Help

### Test-Specific Questions
```bash
# See what tests are available
pytest tests/unit/engine/services/test_config_analyzer.py --collect-only

# See test names matching pattern
pytest tests/unit/engine/services/test_config_analyzer.py::TestMatryoshka --collect-only
```

### Run Pytest Help
```bash
pytest --help
```

### Debug Mode
```bash
# Drop into pdb on failure
pytest tests/unit/engine/services/test_config_analyzer.py --pdb

# Drop into pdb on first failure
pytest tests/unit/engine/services/test_config_analyzer.py -x --pdb
```

---

## Related Documentation

- **Test Suite Overview**: `/home/knitli/codeweaver/claudedocs/test-suites-config-analyzer.md`
- **Implementation Plan**: `/home/knitli/codeweaver/claudedocs/unified-implementation-plan.md`
- **ConfigChangeAnalyzer Source**: `src/codeweaver/engine/services/config_analyzer.py`
- **Unit Tests**: `tests/unit/engine/services/test_config_analyzer.py`
- **Integration Tests**: `tests/integration/test_config_validation_flow.py`
