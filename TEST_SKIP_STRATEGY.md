# Test Skip Strategy for Python 3.14+ and Free-Threaded Compatibility

## Problem

CodeWeaver's test suite fails on Python 3.14+ and free-threaded Python builds due to:

1. **FastEmbed** package not available on Python 3.14+ (dependency constraint)
2. **VoyageAI** package has pydantic v1 incompatibility on Python 3.14+ (`min_items` validation error)
3. **Free-threaded Python** (3.13t, 3.14t) has package build failures:
   - `cffi` not supported on free-threaded 3.13
   - `primp` build fails on free-threaded 3.14

## Solution

Implemented automatic test skipping based on environment detection using pytest hooks.

### New Pytest Markers

Added to `pyproject.toml`:

- `requires_fastembed`: Tests requiring fastembed package (not available on Python 3.14+)
- `requires_voyageai`: Tests requiring voyageai package (has pydantic v1 issues on Python 3.14+)
- `skip_on_python_314`: Tests that should be skipped on Python 3.14+ due to dependency incompatibilities
- `skip_on_free_threaded`: Tests that should be skipped on free-threaded Python builds
- `requires_free_threaded_support`: Tests requiring packages compatible with free-threaded Python

### Implementation

**File: `tests/conftest.py`**

Added `pytest_collection_modifyitems` hook that:

1. Detects Python version (`sys.version_info >= (3, 14)`)
2. Detects free-threaded Python (`hasattr(sys, "_is_gil_enabled") and not sys._is_gil_enabled()`)
3. Checks package availability (try importing `fastembed`, `voyageai`)
4. Automatically applies skip markers to tests based on conditions

### Test File Changes

1. **`tests/unit/providers/embedding/test_voyage.py`**:
   - Added `pytest.mark.requires_voyageai` to `pytestmark`

2. **`tests/unit/providers/reranking/test_voyage.py`**:
   - Added `pytest.mark.requires_voyageai` to `pytestmark`

3. **`tests/integration/conftest.py`**:
   - Moved `FastEmbedEmbeddingProvider` import to `TYPE_CHECKING` block
   - Prevents import-time failures when fastembed isn't available

### CI Behavior

- **Python 3.12/3.13**: Voyageai tests will skip (package not in CI environment)
- **Python 3.14**: Integration tests requiring fastembed/voyageai will skip
- **Free-threaded Python**: Tests requiring incompatible packages will skip

### Manual Testing

To verify the skip logic works:

```bash
# Check which tests would be skipped
mise run test -- --collect-only -m "requires_voyageai or requires_fastembed"

# Run tests on Python 3.13 (should skip voyage tests)
mise run test -- tests/unit/providers/embedding/test_voyage.py -v
```

### Future Work

- Consider adding similar markers for other optional dependencies
- Update CI to explicitly mark which Python versions install which packages
- Add documentation about testing with different dependency sets

## Related Issues

- Issue #240: Resolve test failures
- CI runs showing fastembed/voyageai import errors on Python 3.14
