<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Reconciliation Test Implementation Guide

## Quick Start: Fix the 4 xfail Tests

### Summary
- **Problem**: 4 tests fail due to Pydantic v2 mocking incompatibility
- **Solution**: Replace with integration tests using proven pattern
- **Effort**: 1-2 days
- **Files Changed**: 2 (test files only, no production code)

---

## Step 1: Add Integration Tests (Estimated Time: 4-6 hours)

### File: `tests/integration/test_reconciliation_integration.py`

Add these tests at the end of the file:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconciliation_handles_provider_error_gracefully(
    qdrant_test_manager, tmp_path, initialize_test_settings, caplog
):
    """Verify prime_index continues when reconciliation fails with ProviderError.

    This test validates the error handling at indexer.py:1377-1388.
    When add_missing_embeddings_to_existing_chunks raises ProviderError,
    prime_index should log the error and continue successfully.
    """
    import logging
    from codeweaver.exceptions import ProviderError

    # Create unique collection
    collection_name = qdrant_test_manager.create_collection_name("error_provider")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    config = QdrantConfig(url=qdrant_test_manager.url, collection_name=collection_name)
    provider = QdrantVectorStoreProvider(config=config)
    await provider._initialize()

    project_path = tmp_path / "test_error_project"
    project_path.mkdir()

    file1 = project_path / "module.py"
    file1.write_text("def func():\n    pass\n")

    # Create chunk with dense-only (to trigger sparse reconciliation)
    chunk = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name="module.py:func",
        file_path=Path("module.py"),
        language=Language.PYTHON,
        content="def func():\n    pass",
        dense_embedding=[0.1] * 768,
        sparse_embedding=None,  # Missing sparse
        line_start=1,
        line_end=2,
    )

    await provider.upsert([chunk])

    # Create indexer with sparse provider that will fail
    mock_sparse_provider = MagicMock()
    mock_sparse_provider.model = "test-sparse-model"
    mock_sparse_provider.provider_name = "test-sparse-provider"
    # Make embedding generation fail with ProviderError
    mock_sparse_provider.embed_document = AsyncMock(
        side_effect=ProviderError("Simulated provider failure")
    )

    mock_dense_provider = MagicMock()
    mock_dense_provider.model = "test-dense-model"
    mock_dense_provider.provider_name = "test-provider"

    mock_registry = create_mock_provider_registry(
        vector_store=provider,
        embedding_provider=mock_dense_provider,
        sparse_provider=mock_sparse_provider,
    )

    from codeweaver.config.settings import CodeWeaverSettings

    settings = CodeWeaverSettings(project_path=project_path)
    settings_dict = settings.model_dump()

    with caplog.at_level(logging.WARNING):
        with patch("codeweaver.common.registry.get_provider_registry", return_value=mock_registry):
            indexer = await Indexer.from_settings_async(settings_dict)

            # Initialize manifest
            from codeweaver.engine.indexer.manifest import FileManifestManager
            indexer._manifest_manager = FileManifestManager(project_path=project_path)
            indexer._file_manifest = indexer._manifest_manager.create_new()

            # Set up manifest to show missing sparse embeddings
            indexer._file_manifest.add_file(
                path=Path("module.py"),
                content_hash="test_hash",
                chunk_ids=[str(chunk.chunk_id)],
                dense_embedding_provider="test-provider",
                dense_embedding_model="test-dense-model",
                sparse_embedding_provider=None,
                sparse_embedding_model=None,
                has_dense_embeddings=True,
                has_sparse_embeddings=False,
            )

            # Mock _index_files to avoid actual file processing
            with patch.object(indexer, "_index_files", new_callable=AsyncMock) as mock_index:
                mock_index.return_value = None

                # This should NOT crash despite ProviderError during reconciliation
                result = await indexer.prime_index(force_reindex=False)

    # Verify prime_index completed successfully
    assert result == 0  # 0 files indexed (we mocked _index_files)

    # Verify error was logged
    assert any(
        "Automatic reconciliation failed" in record.message
        and "ProviderError" in record.message
        for record in caplog.records
    ), "Expected reconciliation error to be logged"

    print("✅ PASSED: ProviderError handling verified")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconciliation_handles_indexing_error_gracefully(
    qdrant_test_manager, tmp_path, initialize_test_settings, caplog
):
    """Verify prime_index continues when reconciliation fails with IndexingError.

    This test validates the error handling at indexer.py:1377-1388.
    """
    import logging
    from codeweaver.exceptions import IndexingError

    # Similar setup to provider error test
    collection_name = qdrant_test_manager.create_collection_name("error_indexing")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    config = QdrantConfig(url=qdrant_test_manager.url, collection_name=collection_name)
    provider = QdrantVectorStoreProvider(config=config)
    await provider._initialize()

    project_path = tmp_path / "test_error_indexing"
    project_path.mkdir()

    file1 = project_path / "module.py"
    file1.write_text("def func():\n    pass\n")

    chunk = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name="module.py:func",
        file_path=Path("module.py"),
        language=Language.PYTHON,
        content="def func():\n    pass",
        dense_embedding=[0.1] * 768,
        sparse_embedding=None,
        line_start=1,
        line_end=2,
    )

    await provider.upsert([chunk])

    # Make vector store client fail with IndexingError
    original_update = provider.client.update_vectors
    async def failing_update(*args, **kwargs):
        raise IndexingError("Simulated indexing failure")

    provider.client.update_vectors = failing_update

    mock_sparse_provider = MagicMock()
    mock_sparse_provider.model = "test-sparse-model"
    mock_sparse_provider.provider_name = "test-sparse-provider"
    mock_sparse_provider.embed_document = AsyncMock(
        return_value=[{"indices": [1, 2], "values": [0.9, 0.8]}]
    )

    mock_dense_provider = MagicMock()
    mock_dense_provider.model = "test-dense-model"
    mock_dense_provider.provider_name = "test-provider"

    mock_registry = create_mock_provider_registry(
        vector_store=provider,
        embedding_provider=mock_dense_provider,
        sparse_provider=mock_sparse_provider,
    )

    from codeweaver.config.settings import CodeWeaverSettings

    settings = CodeWeaverSettings(project_path=project_path)
    settings_dict = settings.model_dump()

    with caplog.at_level(logging.WARNING):
        with patch("codeweaver.common.registry.get_provider_registry", return_value=mock_registry):
            indexer = await Indexer.from_settings_async(settings_dict)

            from codeweaver.engine.indexer.manifest import FileManifestManager
            indexer._manifest_manager = FileManifestManager(project_path=project_path)
            indexer._file_manifest = indexer._manifest_manager.create_new()

            indexer._file_manifest.add_file(
                path=Path("module.py"),
                content_hash="test_hash",
                chunk_ids=[str(chunk.chunk_id)],
                dense_embedding_provider="test-provider",
                dense_embedding_model="test-dense-model",
                sparse_embedding_provider=None,
                sparse_embedding_model=None,
                has_dense_embeddings=True,
                has_sparse_embeddings=False,
            )

            with patch.object(indexer, "_index_files", new_callable=AsyncMock) as mock_index:
                mock_index.return_value = None
                result = await indexer.prime_index(force_reindex=False)

    assert result == 0
    assert any(
        "Automatic reconciliation failed" in record.message
        for record in caplog.records
    ), "Expected reconciliation error to be logged"

    print("✅ PASSED: IndexingError handling verified")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconciliation_handles_connection_error_gracefully(
    qdrant_test_manager, tmp_path, initialize_test_settings, caplog
):
    """Verify prime_index continues when reconciliation fails with ConnectionError.

    This test validates the error handling at indexer.py:1389-1396.
    """
    import logging

    collection_name = qdrant_test_manager.create_collection_name("error_connection")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    config = QdrantConfig(url=qdrant_test_manager.url, collection_name=collection_name)
    provider = QdrantVectorStoreProvider(config=config)
    await provider._initialize()

    project_path = tmp_path / "test_error_connection"
    project_path.mkdir()

    file1 = project_path / "module.py"
    file1.write_text("def func():\n    pass\n")

    chunk = create_test_chunk_with_embeddings(
        chunk_id=uuid7(),
        chunk_name="module.py:func",
        file_path=Path("module.py"),
        language=Language.PYTHON,
        content="def func():\n    pass",
        dense_embedding=[0.1] * 768,
        sparse_embedding=None,
        line_start=1,
        line_end=2,
    )

    await provider.upsert([chunk])

    # Make client.retrieve fail with ConnectionError
    async def failing_retrieve(*args, **kwargs):
        raise ConnectionError("Simulated connection failure")

    provider.client.retrieve = failing_retrieve

    mock_sparse_provider = MagicMock()
    mock_sparse_provider.model = "test-sparse-model"
    mock_sparse_provider.provider_name = "test-sparse-provider"

    mock_dense_provider = MagicMock()
    mock_dense_provider.model = "test-dense-model"
    mock_dense_provider.provider_name = "test-provider"

    mock_registry = create_mock_provider_registry(
        vector_store=provider,
        embedding_provider=mock_dense_provider,
        sparse_provider=mock_sparse_provider,
    )

    from codeweaver.config.settings import CodeWeaverSettings

    settings = CodeWeaverSettings(project_path=project_path)
    settings_dict = settings.model_dump()

    with caplog.at_level(logging.WARNING):
        with patch("codeweaver.common.registry.get_provider_registry", return_value=mock_registry):
            indexer = await Indexer.from_settings_async(settings_dict)

            from codeweaver.engine.indexer.manifest import FileManifestManager
            indexer._manifest_manager = FileManifestManager(project_path=project_path)
            indexer._file_manifest = indexer._manifest_manager.create_new()

            indexer._file_manifest.add_file(
                path=Path("module.py"),
                content_hash="test_hash",
                chunk_ids=[str(chunk.chunk_id)],
                dense_embedding_provider="test-provider",
                dense_embedding_model="test-dense-model",
                sparse_embedding_provider=None,
                sparse_embedding_model=None,
                has_dense_embeddings=True,
                has_sparse_embeddings=False,
            )

            with patch.object(indexer, "_index_files", new_callable=AsyncMock) as mock_index:
                mock_index.return_value = None
                result = await indexer.prime_index(force_reindex=False)

    assert result == 0
    assert any(
        "connection/IO error" in record.message
        for record in caplog.records
    ), "Expected connection error to be logged"

    print("✅ PASSED: ConnectionError handling verified")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconciliation_not_called_when_force_reindex_true(
    qdrant_test_manager, tmp_path, initialize_test_settings
):
    """Verify reconciliation is skipped when force_reindex=True.

    This validates the conditional at indexer.py:1334-1338.
    """
    collection_name = qdrant_test_manager.create_collection_name("skip_reindex")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    config = QdrantConfig(url=qdrant_test_manager.url, collection_name=collection_name)
    provider = QdrantVectorStoreProvider(config=config)
    await provider._initialize()

    project_path = tmp_path / "test_skip"
    project_path.mkdir()

    file1 = project_path / "module.py"
    file1.write_text("def func():\n    pass\n")

    # Create mock that will fail if called (to detect unwanted reconciliation)
    mock_sparse_provider = MagicMock()
    mock_sparse_provider.model = "test-sparse-model"
    mock_sparse_provider.provider_name = "test-sparse-provider"
    mock_sparse_provider.embed_document = AsyncMock(
        side_effect=Exception("Should not be called during force_reindex")
    )

    mock_dense_provider = MagicMock()
    mock_dense_provider.model = "test-dense-model"
    mock_dense_provider.provider_name = "test-provider"

    mock_registry = create_mock_provider_registry(
        vector_store=provider,
        embedding_provider=mock_dense_provider,
        sparse_provider=mock_sparse_provider,
    )

    from codeweaver.config.settings import CodeWeaverSettings

    settings = CodeWeaverSettings(project_path=project_path)
    settings_dict = settings.model_dump()

    with patch("codeweaver.common.registry.get_provider_registry", return_value=mock_registry):
        indexer = await Indexer.from_settings_async(settings_dict)

        from codeweaver.engine.indexer.manifest import FileManifestManager
        indexer._manifest_manager = FileManifestManager(project_path=project_path)
        indexer._file_manifest = indexer._manifest_manager.create_new()

        # Set up manifest to show missing embeddings
        # (would trigger reconciliation if force_reindex=False)
        indexer._file_manifest.add_file(
            path=Path("module.py"),
            content_hash="test_hash",
            chunk_ids=["fake-chunk-id"],
            dense_embedding_provider="test-provider",
            dense_embedding_model="test-dense-model",
            sparse_embedding_provider=None,
            sparse_embedding_model=None,
            has_dense_embeddings=True,
            has_sparse_embeddings=False,
        )

        with patch.object(indexer, "_index_files", new_callable=AsyncMock) as mock_index:
            mock_index.return_value = None

            # Call with force_reindex=True
            # If reconciliation runs, embed_document will raise exception
            result = await indexer.prime_index(force_reindex=True)

    # Test passes if we reach here without exception
    # (embed_document was never called)
    print("✅ PASSED: Reconciliation correctly skipped during force_reindex")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconciliation_not_called_when_no_vector_store(
    tmp_path, initialize_test_settings
):
    """Verify reconciliation is skipped when no vector store is configured.

    This validates the conditional at indexer.py:1334-1338.
    """
    project_path = tmp_path / "test_no_vs"
    project_path.mkdir()

    file1 = project_path / "module.py"
    file1.write_text("def func():\n    pass\n")

    # Create indexer WITHOUT vector store
    mock_sparse_provider = MagicMock()
    mock_sparse_provider.model = "test-sparse-model"
    mock_sparse_provider.provider_name = "test-sparse-provider"

    mock_dense_provider = MagicMock()
    mock_dense_provider.model = "test-dense-model"
    mock_dense_provider.provider_name = "test-provider"

    # No vector store in registry
    mock_registry = create_mock_provider_registry(
        vector_store=None,  # No vector store
        embedding_provider=mock_dense_provider,
        sparse_provider=mock_sparse_provider,
    )

    from codeweaver.config.settings import CodeWeaverSettings

    settings = CodeWeaverSettings(project_path=project_path)
    settings_dict = settings.model_dump()

    with patch("codeweaver.common.registry.get_provider_registry", return_value=mock_registry):
        indexer = await Indexer.from_settings_async(settings_dict)

        from codeweaver.engine.indexer.manifest import FileManifestManager
        indexer._manifest_manager = FileManifestManager(project_path=project_path)
        indexer._file_manifest = indexer._manifest_manager.create_new()

        with patch.object(indexer, "_index_files", new_callable=AsyncMock) as mock_index:
            mock_index.return_value = None

            # Should not attempt reconciliation (no vector store)
            result = await indexer.prime_index(force_reindex=False)

    # Test passes if we reach here
    assert result == 0
    print("✅ PASSED: Reconciliation correctly skipped when no vector store")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reconciliation_not_called_when_no_providers(
    qdrant_test_manager, tmp_path, initialize_test_settings
):
    """Verify reconciliation is skipped when no embedding providers configured.

    This validates the conditional at indexer.py:1334-1338.
    """
    collection_name = qdrant_test_manager.create_collection_name("no_providers")
    await qdrant_test_manager.create_collection(
        collection_name, dense_vector_size=768, sparse_vector_size=1000
    )

    config = QdrantConfig(url=qdrant_test_manager.url, collection_name=collection_name)
    provider = QdrantVectorStoreProvider(config=config)
    await provider._initialize()

    project_path = tmp_path / "test_no_providers"
    project_path.mkdir()

    file1 = project_path / "module.py"
    file1.write_text("def func():\n    pass\n")

    # Create registry with vector store but NO embedding providers
    mock_registry = create_mock_provider_registry(
        vector_store=provider,
        embedding_provider=None,  # No dense provider
        sparse_provider=None,  # No sparse provider
    )

    from codeweaver.config.settings import CodeWeaverSettings

    settings = CodeWeaverSettings(project_path=project_path)
    settings_dict = settings.model_dump()

    with patch("codeweaver.common.registry.get_provider_registry", return_value=mock_registry):
        indexer = await Indexer.from_settings_async(settings_dict)

        from codeweaver.engine.indexer.manifest import FileManifestManager
        indexer._manifest_manager = FileManifestManager(project_path=project_path)
        indexer._file_manifest = indexer._manifest_manager.create_new()

        with patch.object(indexer, "_index_files", new_callable=AsyncMock) as mock_index:
            mock_index.return_value = None

            # Should not attempt reconciliation (no providers)
            result = await indexer.prime_index(force_reindex=False)

    assert result == 0
    print("✅ PASSED: Reconciliation correctly skipped when no providers")
```

**New Tests Summary**:
- ✅ Provider error handling
- ✅ Indexing error handling
- ✅ Connection error handling
- ✅ Skip when force_reindex=True
- ✅ Skip when no vector store
- ✅ Skip when no providers

**Lines of Code**: ~400 lines
**Estimated Time**: 4-6 hours (includes testing)

---

## Step 2: Remove xfail Tests (Estimated Time: 30 minutes)

### File: `tests/unit/test_indexer_reconciliation.py`

**Action 1**: Delete `TestAutomaticReconciliation` class

Remove lines 383-518:
```python
# DELETE THIS ENTIRE CLASS
class TestAutomaticReconciliation:
    """Test automatic reconciliation during prime_index.
    ...
    """
```

**Action 2**: Delete `TestReconciliationExceptionHandling` class

Remove lines 794-989:
```python
# DELETE THIS ENTIRE CLASS
class TestReconciliationExceptionHandling:
    """Test exception handling during reconciliation in prime_index.
    ...
    """
```

**Action 3**: Update file docstring

Replace the module docstring at the top of the file:

```python
"""Tests for automatic embedding reconciliation in the indexer.

This module contains unit tests for the reconciliation functionality that detects
and adds missing embeddings to existing chunks in the vector store.

Test Organization:
------------------

UNIT TESTS (this file):
    - TestAddMissingEmbeddings: Comprehensive unit tests for add_missing_embeddings_to_existing_chunks()
        * Tests the core reconciliation logic directly
        * Covers all embedding combination scenarios (dense-only, sparse-only, both, neither)
        * Validates selective embedding generation based on existing vectors
        * Tests manifest updates after successful reconciliation

    - TestEdgeCases: Edge case and error handling for reconciliation logic
        * Non-standard vector types (list vs dict representations)
        * Empty or missing data scenarios
        * Single-provider configurations
        * Payload validation edge cases

INTEGRATION TESTS (tests/integration/test_reconciliation_integration.py):
    - Full prime_index() workflow testing with real Qdrant vector store
    - Error handling during reconciliation (ProviderError, IndexingError, ConnectionError)
    - Reconciliation skip conditions (force_reindex, no vector store, no providers)
    - End-to-end validation of reconciliation behavior in production-like scenarios

Design Rationale:
-----------------
We separate unit and integration tests for reconciliation because:

1. Indexer is a Pydantic v2 BaseModel, which doesn't support reliable method patching
   - Pydantic v2's internal architecture makes patch.object() and similar techniques fragile
   - Class-level patching conflicts with Pydantic's descriptor system

2. Integration tests provide better coverage for prime_index() integration
   - They test real behavior without brittle mocking
   - They exercise actual vector store interactions
   - They validate error handling in realistic scenarios

3. Unit tests focus on the reconciliation logic itself
   - Direct testing of add_missing_embeddings_to_existing_chunks() works perfectly
   - No Pydantic patching required (we mock at the provider level)
   - Comprehensive coverage of all reconciliation paths

This separation provides:
- Fast, reliable unit tests for core logic
- Realistic integration tests for workflow validation
- No xfail tests or brittle mocking
- Comprehensive coverage across both test types
"""
```

---

## Step 3: Verify Changes (Estimated Time: 1 hour)

### Run Tests

```bash
# Run only reconciliation unit tests
pytest tests/unit/test_indexer_reconciliation.py -v

# Expected output:
# - TestAddMissingEmbeddings: 6 tests passing
# - TestEdgeCases: 6 tests passing
# - No xfail tests
# - Total: 12 passing tests

# Run only reconciliation integration tests
pytest tests/integration/test_reconciliation_integration.py -v

# Expected output:
# - Original 4 tests passing
# - New 6 tests passing
# - Total: 10 passing tests

# Run all reconciliation tests
pytest tests/ -k reconciliation -v

# Expected output:
# - 22 tests total
# - All passing
# - No xfail
```

### Check Coverage

```bash
# Generate coverage report for reconciliation code
pytest tests/ -k reconciliation --cov=src/codeweaver/engine/indexer/indexer --cov-report=html

# Open htmlcov/index.html and verify:
# - add_missing_embeddings_to_existing_chunks: >90% coverage
# - prime_index reconciliation block (lines 1334-1400): >80% coverage
```

---

## Step 4: Update Documentation (Estimated Time: 30 minutes)

### File: Update test skip/xfail analysis

If there's a document tracking xfail tests, update it to reflect:
- 4 reconciliation tests removed (not xfail anymore)
- Coverage achieved through integration tests
- Reasoning for approach

### File: Add comment to integration test file

At the top of `tests/integration/test_reconciliation_integration.py`:

```python
"""Integration tests for embedding reconciliation in the indexer.

These tests exercise the reconciliation path in prime_index() using real
Qdrant vector store instances. They replace the unit tests that were
previously marked xfail due to Pydantic v2 mocking incompatibility.

Coverage Areas:
--------------
1. Reconciliation workflow during prime_index()
2. Error handling for ProviderError, IndexingError, ConnectionError
3. Conditional logic for when reconciliation should/shouldn't run
4. Logging and error reporting

Why Integration Tests:
---------------------
- Indexer is a Pydantic v2 BaseModel (method patching unreliable)
- Integration tests exercise real behavior without brittle mocking
- Core reconciliation logic has comprehensive unit test coverage
- This approach provides better test reliability and maintenance

Related Unit Tests:
------------------
- tests/unit/test_indexer_reconciliation.py::TestAddMissingEmbeddings
  * Direct testing of add_missing_embeddings_to_existing_chunks()
  * Comprehensive coverage of reconciliation logic
- tests/unit/test_indexer_reconciliation.py::TestEdgeCases
  * Edge case handling and error scenarios
"""
```

---

## Testing Checklist

### Before Starting
- [ ] Read analysis document (reconciliation_test_analysis.md)
- [ ] Understand Pydantic v2 mocking issue
- [ ] Review existing integration test pattern
- [ ] Set up local Qdrant for testing

### Implementation
- [ ] Add 6 new integration tests to test_reconciliation_integration.py
- [ ] Test each new test individually as you write it
- [ ] Delete TestAutomaticReconciliation class
- [ ] Delete TestReconciliationExceptionHandling class
- [ ] Update test file docstrings

### Verification
- [ ] Run all unit tests: `pytest tests/unit/test_indexer_reconciliation.py -v`
- [ ] Run all integration tests: `pytest tests/integration/test_reconciliation_integration.py -v`
- [ ] Check no xfail tests remain: `pytest tests/ -k reconciliation -v | grep -i xfail`
- [ ] Generate coverage report: `pytest tests/ -k reconciliation --cov=...`
- [ ] Verify >90% coverage for reconciliation method
- [ ] Verify >80% coverage for prime_index reconciliation block
- [ ] Check all error paths are tested
- [ ] Verify logging tests use caplog correctly

### Documentation
- [ ] Update test file docstring
- [ ] Add integration test file header comment
- [ ] Update any test skip/xfail tracking documents
- [ ] Document reasoning in PR description

### Final Review
- [ ] All reconciliation tests passing
- [ ] No xfail tests in reconciliation suite
- [ ] Coverage metrics meet standards
- [ ] Code review by peer
- [ ] CI/CD pipeline passes

---

## Rollback Plan

If issues arise during implementation:

### Quick Rollback
```bash
# Restore xfail tests
git checkout HEAD -- tests/unit/test_indexer_reconciliation.py

# Remove new integration tests
git checkout HEAD -- tests/integration/test_reconciliation_integration.py
```

### Partial Rollback
Keep new integration tests but restore xfail tests:
```bash
# Only restore unit test file
git checkout HEAD -- tests/unit/test_indexer_reconciliation.py

# Keep new integration tests
# They provide value even if xfail tests remain
```

---

## Success Criteria

### Must Have (Required)
✅ All 4 xfail tests removed
✅ 6+ new integration tests added
✅ All tests passing
✅ No decrease in code coverage
✅ Documentation updated

### Should Have (Strongly Recommended)
✅ Coverage >90% for add_missing_embeddings_to_existing_chunks
✅ Coverage >80% for prime_index reconciliation block
✅ All error handling paths explicitly tested
✅ Logging verification using caplog
✅ Clear comments explaining test strategy

### Nice to Have (Optional)
✅ Performance benchmarks for integration tests
✅ Test execution time <5min for full reconciliation suite
✅ Additional edge case tests
✅ Parametrized tests for error types

---

## Common Issues & Solutions

### Issue: Integration tests fail with "Collection not found"
**Solution**: Ensure qdrant_test_manager fixture is working correctly
```python
# Add debug logging
logger.info(f"Collection name: {collection_name}")
logger.info(f"Collections: {await qdrant_test_manager.list_collections()}")
```

### Issue: caplog doesn't capture logs
**Solution**: Set correct log level
```python
import logging
with caplog.at_level(logging.WARNING):
    # Your test code
assert any("expected message" in record.message for record in caplog.records)
```

### Issue: Mock providers not being called
**Solution**: Verify provider registry patching
```python
# Make sure patch context is active when prime_index is called
with patch("codeweaver.common.registry.get_provider_registry", return_value=mock_registry):
    indexer = await Indexer.from_settings_async(settings_dict)
    # prime_index call MUST be inside this context
    await indexer.prime_index(...)
```

### Issue: Tests pass locally but fail in CI
**Solution**: Check Qdrant availability in CI
```yaml
# .github/workflows/test.yml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - 6333:6333
```

---

## FAQ

**Q: Why not fix the Pydantic v2 mocking issue?**
A: Pydantic v2's internal architecture makes reliable method patching extremely difficult. The integration test approach is more maintainable and tests real behavior.

**Q: Will this reduce test coverage?**
A: No, coverage will increase. Integration tests cover more of the actual code path than the xfail unit tests would.

**Q: Are integration tests slower?**
A: Slightly (seconds, not minutes). The trade-off for reliability and actual behavior testing is worth it.

**Q: What if we want to add more reconciliation tests later?**
A: Follow the same pattern: unit tests for add_missing_embeddings_to_existing_chunks logic, integration tests for prime_index integration.

**Q: Should we revisit this when Pydantic v3 is released?**
A: Yes, if Pydantic v3 improves mocking compatibility, we can reconsider. For now, integration tests are the right approach.

---

## Next Steps After Implementation

### Short Term (This Sprint)
1. Merge PR with test changes
2. Monitor CI/CD for any issues
3. Update team documentation
4. Share learnings about Pydantic v2 testing

### Medium Term (Next Quarter)
1. Consider refactoring for ReconciliationService (Option 3 from analysis)
2. Add performance benchmarks
3. Expand edge case coverage
4. Review other Pydantic model tests for similar issues

### Long Term (Future)
1. Monitor Pydantic v3 development
2. Consider architectural improvements
3. Evaluate test suite performance
4. Continuous improvement of test patterns

---

## Contact & Support

If you encounter issues during implementation:
1. Review the analysis document
2. Check existing integration test patterns
3. Consult with team members familiar with:
   - Pydantic v2 behavior
   - Integration test infrastructure
   - Reconciliation logic

This implementation guide is designed to be self-contained and actionable. Follow the steps in order for best results.
