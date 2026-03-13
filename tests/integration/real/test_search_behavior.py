# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Real search behavior validation tests.

These tests use ACTUAL providers (not mocks) to validate that search
quality works end-to-end. They catch issues that mock-based tests cannot:

- Embedding generation produces wrong dimensions
- Vector store can't find relevant results
- Search returns irrelevant files
- Semantic understanding breaks down

Test Philosophy:
- Tier 1 (mocks): "Does my code call the right methods?"
- Tier 2 (real): "Does search actually work?"

Performance: ~2-10s per test due to real embedding generation.
"""

from __future__ import annotations

import pytest

from codeweaver.core.config.loader import CodeWeaverSettingsType


# =============================================================================
# Search Quality Validation Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_finds_authentication_code(indexed_test_project):
    """Validate that searching for 'authentication' finds auth.py in top results.

    This test validates the ENTIRE search pipeline:
    1. Real embeddings capture semantic meaning of "authentication"
    2. Vector store performs real similarity search
    3. Ranking prioritizes relevant results
    4. auth.py appears in top 3 results

    **What could break in production that this test catches:**
    - Embeddings don't capture authentication semantics
    - Vector similarity doesn't find auth-related code
    - Ranking algorithm prioritizes irrelevant files
    - Chunking doesn't extract meaningful auth functions

    **Why mocks can't catch this:**
    Mocks return hardcoded results - they'll pass even if the embedding
    model returns random noise or the vector store can't do similarity search.
    """
    from codeweaver.server.agent_api import IntentType, find_code

    # Search for authentication functionality
    response = await find_code(
        query="authentication login session management", intent=IntentType.UNDERSTAND
    )

    # Extract file paths from results
    result_files = [r.file.path.name for r in response.matches[:3]]

    # Validate auth.py is in top 3 results
    assert "auth.py" in result_files, (
        f"Expected auth.py in top 3 results for authentication query, "
        f"got: {result_files}. This indicates search quality is broken - "
        f"embeddings may not capture authentication semantics."
    )


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_finds_database_code(indexed_test_project):
    """Validate that searching for 'database connection' finds database.py.

    **What this validates:**
    - Embeddings understand database/connection concepts
    - Search finds SQL and connection management code
    - database.py ranks higher than unrelated files

    **Production failure modes this catches:**
    - Model doesn't understand database terminology
    - Vector search favors unrelated code
    - Chunking misses database connection functions
    """
    from codeweaver.server.agent_api import IntentType, find_code

    response = await find_code(
        query="database connection query execution SQL", intent=IntentType.UNDERSTAND
    )

    result_files = [r.file.path.name for r in response.matches[:3]]

    assert "database.py" in result_files, (
        f"Expected database.py in top 3 results for database query, "
        f"got: {result_files}. Search is not finding database-related code."
    )


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_finds_api_endpoints(indexed_test_project):
    """Validate that searching for 'REST API endpoints' finds api.py.

    **What this validates:**
    - Embeddings understand REST API concepts
    - Search finds HTTP endpoint handlers
    - Routing code ranks highly for API queries

    **Production failure modes this catches:**
    - Model doesn't understand API/endpoint terminology
    - Search confuses API code with other interfaces
    - Ranking doesn't prioritize endpoint handlers
    """
    from codeweaver.server.agent_api import IntentType, find_code

    response = await find_code(
        query="REST API endpoints HTTP routing handlers", intent=IntentType.UNDERSTAND
    )

    result_files = [r.file.path.name for r in response.matches[:3]]

    assert "api.py" in result_files, (
        f"Expected api.py in top 3 results for API query, "
        f"got: {result_files}. Search is not finding API endpoint code."
    )


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_distinguishes_different_concepts(indexed_test_project):
    """Validate that search distinguishes between different semantic concepts.

    This test ensures search doesn't just return random files - it should
    find DIFFERENT files for DIFFERENT queries based on semantic understanding.

    **What this validates:**
    - Embeddings capture distinct semantic concepts
    - Vector search differentiates between topics
    - Results vary appropriately by query intent

    **Production failure modes this catches:**
    - Embeddings produce similar vectors for different concepts
    - Vector store returns same results regardless of query
    - Ranking algorithm ignores semantic differences
    """
    from codeweaver.server.agent_api import IntentType, find_code

    # Query 1: Authentication
    auth_response = await find_code(query="user authentication login", intent=IntentType.UNDERSTAND)
    auth_files = {r.file.path.name for r in auth_response.matches[:3]}

    # Query 2: Configuration
    config_response = await find_code(
        query="configuration settings environment variables", intent=IntentType.UNDERSTAND
    )
    config_files = {r.file.path.name for r in config_response.matches[:3]}

    # Results should be different for different concepts
    assert auth_files != config_files, (
        f"Auth query and config query returned identical results: {auth_files}. "
        f"Search is not distinguishing between different semantic concepts."
    )

    # Validate expected files appear
    assert "auth.py" in auth_files, "Auth query should find auth.py"
    assert "config.py" in config_files, "Config query should find config.py"


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_returns_relevant_code_chunks(indexed_test_project):
    """Validate that search returns actual code content, not empty results.

    **What this validates:**
    - Chunking extracts meaningful code segments
    - Indexing stores chunk content correctly
    - Search returns actual code, not just metadata

    **Production failure modes this catches:**
    - Chunking produces empty segments
    - Content not stored in vector store
    - Search returns metadata without code
    """
    from codeweaver.server.agent_api import IntentType, find_code

    response = await find_code(query="password hashing", intent=IntentType.UNDERSTAND)

    # Validate we got results
    assert len(response.matches) > 0, "Search should return results"

    # Validate results contain actual code content
    top_results = response.matches[:3]
    for result in top_results:
        assert result.content, "Search result should contain code content"
        assert len(result.content.content) > 10, (
            f"Search result content too short: {len(result.content.content)} chars. "
            f"Chunking may be broken or content not indexed properly."
        )

    # Validate at least one result has code structure (functions, classes, etc).
    # Individual chunks may be module docstrings or comments, but the pipeline
    # should return at least one chunk containing actual code constructs.
    contents = [r.content.content for r in top_results if r.content]
    assert any(
        any(keyword in content for keyword in ["def ", "class ", "import "])
        for content in contents
    ), (
        f"No search results contain Python code constructs (def/class/import). "
        f"Top result content: {contents[0][:200] if contents else 'none'}. "
        f"Chunking may not be extracting code correctly."
    )


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_respects_file_types(indexed_test_project):
    """Validate that search finds Python files for Python queries.

    **What this validates:**
    - File filtering works correctly
    - Language detection identifies Python
    - Search doesn't return non-code files

    **Production failure modes this catches:**
    - Language detection misclassifies files
    - Search returns documentation instead of code
    - File filtering is broken
    """
    from codeweaver.server.agent_api import IntentType, find_code

    response = await find_code(query="function definition", intent=IntentType.UNDERSTAND)

    # All results should be Python files
    for result in response.matches:
        assert result.file.path.suffix == ".py", (
            f"Expected Python file, got: {result.file.path}. "
            f"File filtering or language detection is broken."
        )


# =============================================================================
# Search Edge Cases
# =============================================================================


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_handles_no_matches_gracefully(indexed_test_project):
    """Validate that search handles queries with no good matches gracefully.

    **What this validates:**
    - Search doesn't crash on poor matches
    - Returns empty or low-confidence results appropriately
    - Doesn't return random irrelevant code

    **Production failure modes this catches:**
    - Search crashes on uncommon queries
    - Returns high-confidence scores for poor matches
    - Ranking algorithm misbehaves with no clear winner
    """
    from codeweaver.server.agent_api import IntentType, find_code

    # Query for something not in the codebase
    response = await find_code(
        query="machine learning neural network training", intent=IntentType.UNDERSTAND
    )

    # Should either return nothing or low-confidence results
    if response.matches:
        # If results exist, confidence should be lower for poor matches
        # This is subjective, but helps catch ranking issues
        top_score = response.matches[0].relevance_score
        assert top_score < 0.95, (
            f"Unexpectedly high confidence ({top_score}) for unrelated query. "
            f"Ranking algorithm may not be calibrated correctly."
        )


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_handles_empty_codebase(tmp_path, clean_container):
    """Validate that search handles empty codebase without crashing.

    **What this validates:**
    - Indexing handles empty directories
    - Search doesn't crash with no indexed content
    - Error messages are clear
    """
    from unittest.mock import AsyncMock

    import codeweaver.core.dependencies
    import codeweaver.engine.dependencies
    import codeweaver.providers.dependencies
    import codeweaver.server.dependencies  # noqa: F401 - ensures @dependency_provider decorators run

    from codeweaver.core.config.loader import get_settings
    from codeweaver.engine import IndexingService
    from codeweaver.providers import EmbeddingProvider, SparseEmbeddingProvider, VectorStoreProvider
    from codeweaver.providers.config.profiles import ProviderProfile
    from codeweaver.providers.config.providers import ProviderSettings
    from codeweaver.providers.dependencies.providers import (
        EmbeddingProvidersDep,
        SparseEmbeddingProvidersDep,
        VectorStoreProvidersDep,
    )
    from codeweaver.providers.types.search import SearchPackage
    from codeweaver.server.agent_api import IntentType, find_code

    empty_dir = tmp_path / "empty_codebase"
    empty_dir.mkdir()
    (empty_dir / ".git").mkdir()  # Git marker

    # Define a factory that returns settings with the empty project path
    async def get_test_settings() -> CodeWeaverSettingsType:
        settings = get_settings()
        settings.project_path = empty_dir
        settings.project_name = f"test_empty_{empty_dir.name}"
        # get_settings() never calls _initialize(), leaving provider=UNSET.
        settings.provider = ProviderSettings.model_construct(
            **ProviderProfile.TESTING.as_provider_settings()
        )
        return settings

    # Mock providers to avoid requiring real API keys/services
    mock_embed = AsyncMock(spec=EmbeddingProvider)
    mock_embed.model_name = "mock-dense-model"
    mock_embed.embed_documents = AsyncMock(return_value=[[0.1] * 256])
    mock_embed.embed_query = AsyncMock(return_value=[[0.1] * 256])
    mock_sparse = AsyncMock(spec=SparseEmbeddingProvider)
    mock_sparse.model_name = "mock-sparse-model"
    mock_sparse.embed_documents = AsyncMock(return_value=[{"indices": [0], "values": [0.1]}])
    mock_sparse.embed_query = AsyncMock(return_value={"indices": [0], "values": [0.1]})
    mock_store = AsyncMock(spec=VectorStoreProvider)
    mock_store.collection_name = "test_collection"
    mock_store.upsert = AsyncMock()
    mock_store.delete_by_file = AsyncMock()
    mock_store.search = AsyncMock(return_value=[])

    # Mock the full search package to bypass agent/data/reranking provider resolution
    mock_search_package = AsyncMock(spec=SearchPackage)
    mock_search_package.embedding = mock_embed
    mock_search_package.sparse_embedding = mock_sparse
    mock_search_package.vector_store = mock_store
    mock_search_package.reranking = ()
    mock_search_package.agent = None

    overrides = {
        CodeWeaverSettingsType: get_test_settings,
        EmbeddingProvidersDep: (mock_embed,),
        SparseEmbeddingProvidersDep: (mock_sparse,),
        VectorStoreProvidersDep: (mock_store,),
        SearchPackage: lambda: mock_search_package,
    }

    with clean_container.use_overrides(overrides):
        # Resolve settings and store in _singletons for sync access via _global_settings()
        test_settings = await clean_container.resolve(CodeWeaverSettingsType)
        clean_container._singletons[CodeWeaverSettingsType] = test_settings

        # Resolve indexer from container
        indexer = await clean_container.resolve(IndexingService)
        await indexer.index_project()

        response = await find_code(query="any query", intent=IntentType.UNDERSTAND)

    # Should return no results, not crash
    assert len(response.matches) == 0, "Empty codebase should return no results"


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_with_very_long_query(indexed_test_project):
    """Validate that search handles long queries without crashing.

    **What this validates:**
    - Embedding model handles long input
    - Query processing doesn't exceed token limits
    - Search quality doesn't degrade with longer queries

    **Production failure modes this catches:**
    - Crash on long queries
    - Silent truncation losing query intent
    - Performance degradation with query length
    """
    from codeweaver.server.agent_api import IntentType, find_code

    # Create a long but meaningful query
    long_query = "I'm looking for code that handles user authentication including login functionality, password validation, session management, and logout procedures. The code should validate credentials against a database and create session tokens for authenticated users."

    # Should handle long query without crashing
    response = await find_code(query=long_query, intent=IntentType.UNDERSTAND)

    # Should return results without crashing
    assert response is not None, "Search should return a response object"

    # Should still find auth-related code in top results.
    # Check top 5 to allow for ranking variance with small/fast embedding models.
    result_files = [r.file.path.name for r in response.matches[:5]]
    assert "auth.py" in result_files, (
        f"Long query should still find authentication code in top 5, got: {result_files}"
    )
