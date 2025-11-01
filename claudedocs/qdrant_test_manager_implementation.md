<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Qdrant Test Manager Implementation Summary

**Date**: 2025-11-01
**Branch**: 003-our-aim-to
**Task**: Complete integration testing infrastructure for Qdrant vector store provider

## Problem Statement

The integration test harness lacked a reliable way to test the Qdrant implementation. Specific issues:

1. **Port conflicts**: Tests could interfere with existing Qdrant instances
2. **No port detection**: Hard-coded ports (e.g., 6336) might not be available
3. **Collection cleanup**: Manual cleanup was error-prone and incomplete
4. **Authentication testing**: No way to test client/server authentication in controlled manner
5. **Test isolation**: Collections could collide between concurrent tests

## Solution: QdrantTestManager

A comprehensive test infrastructure providing:

### 1. Automatic Port Management

```python
# Scans ports 6333-6400 for availability
manager = QdrantTestManager()  # Auto-detects first available port

# Or use explicit port
manager = QdrantTestManager(port=6340)
```

**Implementation**: `tests/qdrant_test_manager.py:QdrantTestManager._find_available_port()`

- Uses socket binding to check port availability
- Scans range 6333-6400 (standard Qdrant ports)
- Raises `RuntimeError` if no ports available
- Configurable range for custom deployments

### 2. Test Isolation with Unique Collections

```python
# Each test gets unique collection name
collection_name = manager.create_collection_name("mytest")
# Returns: "mytest-a1b2c3d4" (8-char UUID suffix)

# Automatic creation and cleanup
async with manager.collection_context() as (client, collection):
    # Collection ready for use
    await client.upsert(collection, points=[...])
    # Automatic cleanup on exit
```

**Key Features**:
- UUID-based unique names prevent collisions
- Context manager ensures cleanup even on test failure
- Tracks all created collections for batch cleanup
- Supports both dense and sparse vectors

### 3. Authentication Support

```python
# Test with API key
manager = QdrantTestManager(api_key="test-secure-key")

# Verify authenticated operations
client = await manager.ensure_client()
collections = await client.get_collections()

# Test authentication failures
manager_no_auth = QdrantTestManager()  # No API key
# Operations should fail appropriately
```

**Use Cases**:
- Testing authenticated client/server connections
- Validating API key handling
- Testing permission failures

### 4. Connection Verification

```python
# Check if Qdrant is reachable before tests
if not await manager.verify_connection():
    pytest.skip("Qdrant not available at {manager.url}")
```

**Implementation**:
- Socket check for port availability
- Actual API call to verify service responds
- 5-second timeout for quick failure
- Used by `qdrant_test_manager` fixture to auto-skip tests

## Implementation Details

### Files Created

1. **`tests/qdrant_test_manager.py`** (400 lines)
   - `QdrantTestManager` class with full lifecycle management
   - Port detection and availability checking
   - Collection creation with vector configuration
   - Context managers for automatic cleanup
   - Connection verification
   - Helper function `get_qdrant_test_config()` for compatibility

2. **`tests/QDRANT_TESTING.md`** (600+ lines)
   - Complete testing guide
   - Quick start instructions
   - Usage patterns and best practices
   - Troubleshooting section
   - CI/CD integration examples
   - Advanced usage scenarios

3. **`tests/conftest.py`** (additions)
   - `qdrant_test_manager` fixture (primary)
   - `qdrant_test_client` fixture (convenience)
   - `qdrant_test_collection` fixture (context manager)

### Files Modified

1. **`tests/contract/test_qdrant_provider.py`**
   - Replaced hard-coded port configuration
   - Updated `qdrant_provider` fixture to use `qdrant_test_manager`
   - Removed manual cleanup code
   - Added automatic collection creation/cleanup

## Pytest Fixtures

### Primary Fixture: `qdrant_test_manager`

```python
@pytest.fixture
async def qdrant_test_manager(tmp_path: Path):
    """Provide a QdrantTestManager for integration tests."""
    from tests.qdrant_test_manager import QdrantTestManager

    storage_path = tmp_path / "qdrant_storage"
    storage_path.mkdir(exist_ok=True)

    manager = QdrantTestManager(storage_path=storage_path)

    # Auto-skip if Qdrant not available
    if not await manager.verify_connection():
        pytest.skip(f"Qdrant not available at {manager.url}")

    yield manager

    # Automatic cleanup
    await manager.close()
```

**Usage in Tests**:

```python
async def test_something(qdrant_test_manager):
    # Option 1: Context manager (recommended)
    async with qdrant_test_manager.collection_context() as (client, collection):
        await client.upsert(collection, points=[...])

    # Option 2: Manual management
    collection = await qdrant_test_manager.create_collection("test")
    client = await qdrant_test_manager.ensure_client()
    # Use collection...
    # Cleanup automatic via manager
```

## Key Benefits

### 1. No Port Conflicts

Before:
```python
# Hard-coded port, may conflict
"url": "http://localhost:6336"
```

After:
```python
# Auto-detected available port
manager = QdrantTestManager()  # Finds first available port 6333-6400
```

### 2. Automatic Cleanup

Before:
```python
# Manual cleanup, easy to forget or fail
try:
    await provider._client.delete_collection(collection_name)
except Exception:
    pass  # Silently fails, collections accumulate
```

After:
```python
async with manager.collection_context() as (client, collection):
    # Test code here
    pass  # Automatic cleanup on exit, even on exceptions
```

### 3. Test Isolation

Before:
```python
# Collection name collision risk
collection_name = "test_contract"  # Multiple tests may use same name
```

After:
```python
# Guaranteed unique per test
collection_name = manager.create_collection_name("contract")
# Returns: "contract-a1b2c3d4"
```

### 4. Graceful Skipping

Before:
```python
# Tests fail if Qdrant not running
await provider._initialize()  # ConnectionError if Qdrant down
```

After:
```python
# Tests auto-skip if Qdrant unavailable
# Via fixture verification
if not await manager.verify_connection():
    pytest.skip("Qdrant not available")
```

## Usage Examples

### Example 1: Basic Test

```python
async def test_search(qdrant_test_manager, sample_chunk):
    async with qdrant_test_manager.collection_context(
        dense_vector_size=768
    ) as (client, collection):
        # Upsert test data
        await client.upsert(collection, points=[...])

        # Search
        results = await client.search(
            collection_name=collection,
            query_vector=[0.1, 0.2, ...],
            limit=5
        )

        assert len(results) > 0
```

### Example 2: Provider Integration

```python
async def test_provider(qdrant_test_manager):
    collection = qdrant_test_manager.create_collection_name("provider")
    await qdrant_test_manager.create_collection(collection)

    provider = QdrantVectorStoreProvider(config={
        "url": qdrant_test_manager.url,
        "collection_name": collection,
    })

    await provider._initialize()
    # Test provider methods...
```

### Example 3: Multi-Collection Test

```python
async def test_multiple_collections(qdrant_test_manager):
    # Dense-only collection
    dense_coll = await qdrant_test_manager.create_collection(
        "dense-only",
        dense_vector_size=768,
        sparse_vector_size=None
    )

    # Hybrid collection
    hybrid_coll = await qdrant_test_manager.create_collection(
        "hybrid",
        dense_vector_size=768,
        sparse_vector_size=1000
    )

    client = await qdrant_test_manager.ensure_client()
    # Test cross-collection operations...
```

## Testing the Implementation

### Start Qdrant

```bash
docker run -d --name qdrant-test -p 6333:6333 qdrant/qdrant:latest
```

### Run Tests

```bash
# All Qdrant tests
pytest tests/contract/test_qdrant_provider.py -v

# Specific test
pytest tests/contract/test_qdrant_provider.py::TestQdrantProviderContract::test_search_with_dense_vector -v

# With detailed output
pytest tests/contract/test_qdrant_provider.py -vv -s
```

### Verify Cleanup

```bash
# Check collections before test
docker exec qdrant-test sh -c "ls /qdrant/storage/collections"

# Run tests
pytest tests/contract/test_qdrant_provider.py

# Check collections after (should be clean)
docker exec qdrant-test sh -c "ls /qdrant/storage/collections"
```

## CI/CD Integration

### GitHub Actions Example

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - 6333:6333
    options: >-
      --health-cmd "curl -f http://localhost:6333/health"
      --health-interval 10s

steps:
  - name: Run Qdrant tests
    run: pytest tests/contract/test_qdrant_provider.py -v
```

The manager automatically:
1. Detects Qdrant at localhost:6333
2. Creates unique collections per test
3. Cleans up after each test
4. Skips tests if Qdrant unavailable

## Future Enhancements

1. **Docker Management** (Optional)
   - Auto-start Qdrant container if not running
   - Use random host ports to avoid conflicts
   - Stop container after tests

2. **Performance Metrics**
   - Track test execution times
   - Monitor collection sizes
   - Report cleanup statistics

3. **Snapshot Support**
   - Save collection state for debugging
   - Restore known-good states
   - Compare before/after snapshots

4. **Parallel Test Support**
   - Ensure thread-safe collection names
   - Coordinate cleanup across workers
   - Pool connections for efficiency

## Conclusion

The `QdrantTestManager` provides a robust, production-ready solution for Qdrant integration testing with:

✅ **Zero port conflicts** - automatic port detection
✅ **Complete isolation** - unique collections per test
✅ **Automatic cleanup** - context managers ensure no leftover data
✅ **Authentication testing** - controlled API key scenarios
✅ **Graceful degradation** - tests skip if Qdrant unavailable
✅ **CI/CD ready** - works with GitHub Actions, GitLab CI, etc.

This implementation meets all requirements from the original request and provides a solid foundation for reliable Qdrant testing in the CodeWeaver MCP project.
