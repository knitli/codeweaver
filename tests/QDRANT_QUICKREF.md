<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Qdrant Testing Quick Reference

Quick reference for writing tests with QdrantTestManager.

## Setup

```bash
# Start Qdrant
docker run -d --name qdrant-test -p 6333:6333 qdrant/qdrant:latest

# Run tests
pytest tests/contract/test_qdrant_provider.py -v
```

## Pattern 1: Context Manager (Recommended)

```python
async def test_something(qdrant_test_manager):
    async with qdrant_test_manager.collection_context(
        prefix="mytest",
        dense_vector_size=768,
        sparse_vector_size=1000  # Optional
    ) as (client, collection):
        # Collection created and ready
        await client.upsert(collection, points=[...])
        # Automatic cleanup on exit
```

## Pattern 2: Manual Management

```python
async def test_something(qdrant_test_manager):
    # Create collection
    collection = await qdrant_test_manager.create_collection(
        "my-test",
        dense_vector_size=768
    )

    # Get client
    client = await qdrant_test_manager.ensure_client()

    # Use collection
    await client.upsert(collection, points=[...])

    # Cleanup automatic via manager
```

## Pattern 3: Provider Testing

```python
async def test_provider(qdrant_test_manager):
    # Create unique collection
    collection = qdrant_test_manager.create_collection_name("provider")
    await qdrant_test_manager.create_collection(collection)

    # Configure provider
    provider = QdrantVectorStoreProvider(config={
        "url": qdrant_test_manager.url,
        "collection_name": collection,
    })

    await provider._initialize()
    # Test provider...
```

## Available Fixtures

```python
# Primary fixture
async def test_a(qdrant_test_manager):
    # Full manager with all capabilities
    pass

# Convenience: just the client
async def test_b(qdrant_test_client):
    collections = await qdrant_test_client.get_collections()

# Convenience: client + collection
async def test_c(qdrant_test_collection):
    client, collection = qdrant_test_collection
    await client.upsert(collection, points=[...])
```

## Common Operations

### Create Unique Collection

```python
name = manager.create_collection_name("prefix")  # "prefix-a1b2c3d4"
```

### Create Collection with Vectors

```python
await manager.create_collection(
    "my-collection",
    dense_vector_size=768,
    sparse_vector_size=1000,  # Optional
    distance=qmodels.Distance.COSINE  # Optional
)
```

### Get Connected Client

```python
client = await manager.ensure_client()
```

### Verify Connection

```python
if not await manager.verify_connection():
    pytest.skip("Qdrant not available")
```

### Delete Collection

```python
await manager.delete_collection("collection-name")
```

### Cleanup All Collections

```python
await manager.cleanup_all_collections()
```

## Troubleshooting

### Qdrant Not Available

```bash
# Check if running
docker ps | grep qdrant

# Start if needed
docker run -d --name qdrant-test -p 6333:6333 qdrant/qdrant:latest

# Check health
curl http://localhost:6333/health
```

### Port Already in Use

```bash
# Manager auto-detects available port (6333-6400)
# Or use custom port:
manager = QdrantTestManager(port=6340)
```

### Collection Not Cleaned Up

```bash
# Restart Qdrant
docker restart qdrant-test

# Or delete manually
docker exec qdrant-test sh -c "rm -rf /qdrant/storage/collections/*"
```

## Full Documentation

See `tests/QDRANT_TESTING.md` for complete guide including:
- Advanced usage patterns
- CI/CD integration
- Authentication testing
- Performance tuning
- Detailed troubleshooting
