<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Qdrant Integration Testing Guide

This guide explains how to run integration tests for the Qdrant vector store provider, including setup, configuration, and troubleshooting.

## Overview

CodeWeaver's Qdrant integration testing uses `QdrantTestManager`, a custom fixture system that provides:

- **Port auto-detection**: Finds available ports (6333-6400) to avoid conflicts with existing instances (note: this won't work on wsl)
- **Test isolation**: Each test gets a unique collection with automatic cleanup
- **Flexible deployment**: Supports local containers, remote instances, and authentication
- **Graceful skipping**: Tests are automatically skipped if Qdrant is unavailable

## Quick Start

### 1. Start Qdrant Instance

**Option A: Docker (Recommended for CI/CD)**

```bash
# Standard port (6333)
docker run -d --name qdrant-test -p 6333:6333 qdrant/qdrant:latest

# Custom port (if 6333 is in use)
docker run -d --name qdrant-test -p 6340:6333 qdrant/qdrant:latest
```

**Option B: Local Installation**

```bash
# macOS with Homebrew
brew install qdrant

# Start service
qdrant --port 6333
```

**Option C: Docker Compose (Multi-service testing)**

```yaml
# docker-compose.test.yml
services:
  qdrant-test:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    environment:
      QDRANT__SERVICE__GRPC_PORT: 6334
```

```bash
docker-compose -f docker-compose.test.yml up -d
```

### 2. Run Tests

```bash
# Run all Qdrant tests
pytest tests/contract/test_qdrant_provider.py -v

# Run specific test
pytest tests/contract/test_qdrant_provider.py::TestQdrantProviderContract::test_hybrid_search -v

# Run with more detailed output
pytest tests/contract/test_qdrant_provider.py -vv -s
```

## Test Architecture

### QdrantTestManager

The `QdrantTestManager` class (defined in `tests/qdrant_test_manager.py`) handles all test instance lifecycle management.

**Key Features:**

```python
from tests.qdrant_test_manager import QdrantTestManager

# Auto-detect available port
manager = QdrantTestManager()  # Scans 6333-6400

# Specific port
manager = QdrantTestManager(port=6340)

# With authentication
manager = QdrantTestManager(api_key="your-api-key")

# Custom host (remote instance)
manager = QdrantTestManager(host="qdrant.example.com", port=6333)
```

### Pytest Fixtures

Three fixtures are available in `tests/conftest.py`:

**1. `qdrant_test_manager` (Primary)**

Provides full test manager with cleanup capabilities.

```python
async def test_something(qdrant_test_manager):
    # Create isolated collection
    collection = await qdrant_test_manager.create_collection(
        "my-test",
        dense_vector_size=768,
        sparse_vector_size=1000
    )

    client = await qdrant_test_manager.ensure_client()
    # Use client and collection
    # Cleanup automatic
```

**2. `qdrant_test_client`**

Convenience fixture that returns just the client.

```python
async def test_something(qdrant_test_client):
    # Client already connected
    collections = await qdrant_test_client.get_collections()
```

**3. `qdrant_test_collection`**

Context manager that provides both client and collection.

```python
async def test_something(qdrant_test_collection):
    client, collection = qdrant_test_collection
    await client.upsert(collection, points=[...])
```

## Usage Patterns

### Pattern 1: Manual Collection Management

```python
async def test_custom_setup(qdrant_test_manager):
    # Create multiple collections
    coll1 = await qdrant_test_manager.create_collection(
        "test-dense-only",
        dense_vector_size=512,
        sparse_vector_size=None  # No sparse vectors
    )

    coll2 = await qdrant_test_manager.create_collection(
        "test-hybrid",
        dense_vector_size=768,
        sparse_vector_size=1000
    )

    client = await qdrant_test_manager.ensure_client()

    # Use collections
    # ...

    # Cleanup automatic via manager
```

### Pattern 2: Context Manager (Recommended)

```python
async def test_with_context(qdrant_test_manager):
    async with qdrant_test_manager.collection_context(
        prefix="mytest",
        dense_vector_size=768
    ) as (client, collection):
        # Collection created and ready
        await client.upsert(collection, points=[...])
        # Automatic cleanup on exit
```

### Pattern 3: Provider Integration

```python
async def test_provider(qdrant_test_manager):
    from codeweaver.providers.vector_stores.qdrant import QdrantVectorStoreProvider

    # Create collection
    collection = qdrant_test_manager.create_collection_name("provider-test")
    await qdrant_test_manager.create_collection(collection)

    # Configure provider
    config = {
        "url": qdrant_test_manager.url,
        "collection_name": collection,
        "batch_size": 64,
    }

    provider = QdrantVectorStoreProvider(config=config)
    await provider._initialize()

    # Test provider
    # ...
```

## Configuration

### Port Detection

The manager scans ports 6333-6400 to find an available one:

```python
# Default: auto-detect
manager = QdrantTestManager()  # Will use first available port

# Explicit port
manager = QdrantTestManager(port=6340)

# Custom range (modify in qdrant_test_manager.py)
port = QdrantTestManager._find_available_port(start=7000, end=7100)
```

### Authentication

For testing authenticated Qdrant instances:

```python
# Environment variable
export QDRANT_API_KEY="your-api-key"

# Fixture usage
manager = QdrantTestManager(api_key="your-api-key")
```

### Remote Instances

Test against remote Qdrant deployments:

```python
manager = QdrantTestManager(
    host="qdrant.example.com",
    port=6333,
    api_key="production-key"  # For staging/prod testing
)
```

## Troubleshooting

### Issue: Tests Skipped - "Qdrant not available"

**Cause**: No Qdrant instance running on detected port.

**Solutions**:

```bash
# 1. Check if Qdrant is running
docker ps | grep qdrant

# 2. Check if port is accessible
curl http://localhost:6333/health

# 3. Start Qdrant
docker run -d --name qdrant-test -p 6333:6333 qdrant/qdrant:latest

# 4. Verify connection
docker logs qdrant-test
```

### Issue: Port Already in Use

**Cause**: Another Qdrant instance or service using the port.

**Solutions**:

```bash
# Option 1: Stop existing instance
docker stop qdrant-test
docker rm qdrant-test

# Option 2: Use different port (auto-detected)
# Manager will automatically scan 6333-6400 and use first available

# Option 3: Explicitly specify port
# Modify test to use: QdrantTestManager(port=6340)
```

### Issue: Collection Already Exists

**Cause**: Previous test didn't clean up (rare with fixtures).

**Solutions**:

```bash
# Manual cleanup via Docker
docker exec qdrant-test sh -c "rm -rf /qdrant/storage/collections/*"
docker restart qdrant-test

# Or restart container
docker restart qdrant-test

# Or use API
curl -X DELETE http://localhost:6333/collections/problematic-collection
```

### Issue: Authentication Failures

**Cause**: API key mismatch or missing.

**Solutions**:

```bash
# 1. Check API key configuration
echo $QDRANT_API_KEY

# 2. Start Qdrant with auth
docker run -d --name qdrant-test \
  -p 6333:6333 \
  -e QDRANT__SERVICE__API_KEY=test-key \
  qdrant/qdrant:latest

# 3. Pass to manager
manager = QdrantTestManager(api_key="test-key")
```

### Issue: Slow Tests

**Cause**: Network latency or large vector operations.

**Solutions**:

```python
# 1. Reduce vector sizes in tests
await manager.create_collection(
    "test",
    dense_vector_size=128,  # Instead of 768
    sparse_vector_size=100   # Instead of 1000
)

# 2. Reduce batch sizes
config = {"batch_size": 10}  # Instead of 64

# 3. Use local container (not remote)
manager = QdrantTestManager(host="localhost")  # Not remote host
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      qdrant:
        image: qdrant/qdrant:latest
        ports:
          - 6333:6333
        options: >-
          --health-cmd "curl -f http://localhost:6333/health || exit 1"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync --all-groups

      - name: Wait for Qdrant
        run: |
          timeout 30 bash -c 'until curl -f http://localhost:6333/health; do sleep 1; done'

      - name: Run Qdrant tests
        run: |
          pytest tests/contract/test_qdrant_provider.py -v
```

### GitLab CI

```yaml
test:qdrant:
  image: python:3.12

  services:
    - name: qdrant/qdrant:latest
      alias: qdrant

  variables:
    QDRANT_HOST: qdrant
    QDRANT_PORT: "6333"

  before_script:
    - pip install uv
    - uv sync --all-groups

  script:
    - pytest tests/contract/test_qdrant_provider.py -v
```

## Best Practices

### 1. Use Context Managers

```python
# ✅ Good: Automatic cleanup
async with manager.collection_context() as (client, collection):
    await client.upsert(collection, points=[...])

# ❌ Avoid: Manual cleanup required
collection = await manager.create_collection("test")
# ... use collection ...
await manager.delete_collection("test")  # Easy to forget
```

### 2. Unique Collection Names

```python
# ✅ Good: Automatic uniqueness
name = manager.create_collection_name("mytest")  # "mytest-a1b2c3d4"

# ❌ Avoid: Hard-coded names (can conflict)
collection = "test-collection"  # Collision risk
```

### 3. Verify Connections

```python
# ✅ Good: Check before tests
if not await manager.verify_connection():
    pytest.skip("Qdrant unavailable")

# ❌ Avoid: Assume connection works
client = await manager.ensure_client()  # May fail
```

### 4. Clean Separation

```python
# ✅ Good: One manager per test
async def test_a(qdrant_test_manager):
    # Isolated manager
    pass

async def test_b(qdrant_test_manager):
    # Different manager, no interference
    pass

# ❌ Avoid: Shared state between tests
global_manager = QdrantTestManager()  # Dangerous
```

## Advanced Usage

### Custom Vector Configurations

```python
from qdrant_client.http import models as qmodels

async def test_custom_distance(qdrant_test_manager):
    collection = await qdrant_test_manager.create_collection(
        "test-euclidean",
        dense_vector_size=768,
        distance=qmodels.Distance.EUCLIDEAN  # Not COSINE
    )
```

### Multiple Simultaneous Collections

```python
async def test_multi_collection(qdrant_test_manager):
    # Separate dense and sparse collections
    dense_coll = await qdrant_test_manager.create_collection(
        "dense-only",
        dense_vector_size=768,
        sparse_vector_size=None
    )

    sparse_coll = await qdrant_test_manager.create_collection(
        "sparse-only",
        dense_vector_size=128,  # Minimal
        sparse_vector_size=5000
    )

    client = await qdrant_test_manager.ensure_client()
    # Test cross-collection operations
```

### Authentication Testing

```python
async def test_authenticated_operations(tmp_path):
    # Test with API key
    manager = QdrantTestManager(
        storage_path=tmp_path,
        api_key="test-secure-key"
    )

    # Verify auth works
    client = await manager.ensure_client()
    collections = await client.get_collections()

    # Verify auth required
    manager_no_auth = QdrantTestManager(storage_path=tmp_path)
    with pytest.raises(Exception):  # Should fail without key
        await manager_no_auth.ensure_client()
```

## Reference

### QdrantTestManager API

**Constructor Parameters:**
- `host: str` - Qdrant host (default: "localhost")
- `port: int | None` - Port number (default: auto-detect)
- `prefer_grpc: bool` - Use gRPC vs HTTP (default: False)
- `api_key: str | None` - API key for authentication
- `storage_path: Path | None` - Local storage path
- `timeout: float` - Connection timeout (default: 30.0s)

**Methods:**
- `create_collection_name(prefix)` - Generate unique collection name
- `create_collection(...)` - Create collection with vectors
- `delete_collection(name)` - Delete specific collection
- `cleanup_all_collections()` - Delete all created collections
- `ensure_client()` - Get or create connected client
- `verify_connection()` - Check if Qdrant is reachable
- `collection_context(...)` - Context manager for collection lifecycle
- `close()` - Close client and cleanup all collections

### Pytest Fixtures

- `qdrant_test_manager` - Full manager with cleanup
- `qdrant_test_client` - Just the connected client
- `qdrant_test_collection` - Client + collection tuple

## Support

For issues with Qdrant testing:

1. Check [Qdrant documentation](https://qdrant.tech/documentation/)
2. Review test logs: `pytest tests/contract/test_qdrant_provider.py -vv -s`
3. Verify Qdrant health: `curl http://localhost:6333/health`
4. Check this guide's troubleshooting section
5. Open issue at https://github.com/knitli/codeweaver-mcp/issues
