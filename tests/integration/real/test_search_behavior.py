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


# =============================================================================
# Search Quality Validation Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_finds_authentication_code(real_providers, known_test_codebase):
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
    from codeweaver.agent_api.find_code import find_code

    # Index the test codebase with real embeddings
    response = await find_code(
        query="authentication login session management",
        cwd=str(known_test_codebase),
        index_if_needed=True,
    )

    # Extract file paths from results
    result_files = [r.file_path.name for r in response.results[:3]]

    # Validate auth.py is in top 3 results
    assert "auth.py" in result_files, (
        f"Expected auth.py in top 3 results for authentication query, "
        f"got: {result_files}. This indicates search quality is broken - "
        f"embeddings may not capture authentication semantics."
    )


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_finds_database_code(real_providers, known_test_codebase):
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
    from codeweaver.agent_api.find_code import find_code

    response = await find_code(
        query="database connection query execution SQL",
        cwd=str(known_test_codebase),
        index_if_needed=True,
    )

    result_files = [r.file_path.name for r in response.results[:3]]

    assert "database.py" in result_files, (
        f"Expected database.py in top 3 results for database query, "
        f"got: {result_files}. Search is not finding database-related code."
    )


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_finds_api_endpoints(real_providers, known_test_codebase):
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
    from codeweaver.agent_api.find_code import find_code

    response = await find_code(
        query="REST API endpoints HTTP routing handlers",
        cwd=str(known_test_codebase),
        index_if_needed=True,
    )

    result_files = [r.file_path.name for r in response.results[:3]]

    assert "api.py" in result_files, (
        f"Expected api.py in top 3 results for API query, "
        f"got: {result_files}. Search is not finding API endpoint code."
    )


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_distinguishes_different_concepts(real_providers, known_test_codebase):
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
    from codeweaver.agent_api.find_code import find_code

    # Query 1: Authentication
    auth_response = await find_code(
        query="user authentication login",
        cwd=str(known_test_codebase),
        index_if_needed=True,
    )
    auth_files = {r.file_path.name for r in auth_response.results[:3]}

    # Query 2: Configuration
    config_response = await find_code(
        query="configuration settings environment variables",
        cwd=str(known_test_codebase),
        index_if_needed=True,
    )
    config_files = {r.file_path.name for r in config_response.results[:3]}

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
async def test_search_returns_relevant_code_chunks(real_providers, known_test_codebase):
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
    from codeweaver.agent_api.find_code import find_code

    response = await find_code(
        query="password hashing",
        cwd=str(known_test_codebase),
        index_if_needed=True,
    )

    # Validate we got results
    assert len(response.results) > 0, "Search should return results"

    # Validate results contain actual code content
    for result in response.results[:3]:
        assert result.content, "Search result should contain code content"
        assert len(result.content.content) > 50, (
            f"Search result content too short: {len(result.content.content)} chars. "
            f"Chunking may be broken or content not indexed properly."
        )

        # Validate chunk has code structure (functions, classes, etc)
        content = result.content.content
        assert any(keyword in content for keyword in ["def ", "class ", "import "]), (
            f"Search result doesn't look like Python code: {content[:100]}. "
            f"Chunking may not be extracting code correctly."
        )


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_respects_file_types(real_providers, known_test_codebase):
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
    from codeweaver.agent_api.find_code import find_code

    response = await find_code(
        query="function definition",
        cwd=str(known_test_codebase),
        index_if_needed=True,
    )

    # All results should be Python files
    for result in response.results:
        assert result.file_path.suffix == ".py", (
            f"Expected Python file, got: {result.file_path}. "
            f"File filtering or language detection is broken."
        )


# =============================================================================
# Search Edge Cases
# =============================================================================


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_handles_no_matches_gracefully(real_providers, known_test_codebase):
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
    from codeweaver.agent_api.find_code import find_code

    # Query for something not in the codebase
    response = await find_code(
        query="machine learning neural network training",
        cwd=str(known_test_codebase),
        index_if_needed=True,
    )

    # Should either return nothing or low-confidence results
    if response.results:
        # If results exist, confidence should be lower for poor matches
        # This is subjective, but helps catch ranking issues
        top_score = response.results[0].score
        assert top_score < 0.95, (
            f"Unexpectedly high confidence ({top_score}) for unrelated query. "
            f"Ranking algorithm may not be calibrated correctly."
        )


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_handles_empty_codebase(real_providers, tmp_path):
    """Validate that search handles empty codebase without crashing.

    **What this validates:**
    - Indexing handles empty directories
    - Search doesn't crash with no indexed content
    - Error messages are clear

    **Production failure modes this catches:**
    - Crash on empty repository
    - Unclear error messages for users
    - Indexing assumes content exists
    """
    from codeweaver.agent_api.find_code import find_code

    empty_dir = tmp_path / "empty_codebase"
    empty_dir.mkdir()

    # Should handle empty codebase gracefully
    response = await find_code(
        query="any query",
        cwd=str(empty_dir),
        index_if_needed=True,
    )

    # Should return no results, not crash
    assert len(response.results) == 0, "Empty codebase should return no results"


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_with_very_long_query(real_providers, known_test_codebase):
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
    from codeweaver.agent_api.find_code import find_code

    # Create a long but meaningful query
    long_query = " ".join([
        "I'm looking for code that handles user authentication",
        "including login functionality, password validation,",
        "session management, and logout procedures.",
        "The code should validate credentials against a database",
        "and create session tokens for authenticated users.",
    ])

    # Should handle long query without crashing
    response = await find_code(
        query=long_query,
        cwd=str(known_test_codebase),
        index_if_needed=True,
    )

    # Should still find auth-related code
    result_files = [r.file_path.name for r in response.results[:3]]
    assert "auth.py" in result_files, (
        f"Long query should still find authentication code, got: {result_files}"
    )
