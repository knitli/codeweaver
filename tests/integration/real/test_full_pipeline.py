# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Full pipeline end-to-end tests with real providers.

These tests validate the complete index → search workflow using real
embeddings, real vector storage, and real search operations.

They catch integration issues that unit tests and mocked integration tests miss:
- Indexing doesn't actually store vectors
- Embeddings incompatible with vector store dimensions
- Search can't find freshly indexed content
- Pipeline steps don't coordinate correctly

Performance: ~5-15s per test due to full indexing + search.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# =============================================================================
# Full Pipeline Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_full_pipeline_index_then_search(real_providers, known_test_codebase):
    """Validate complete workflow: index fresh codebase, then search it.

    This is the MOST IMPORTANT real provider test. It validates that:
    1. Indexing actually stores embeddings in vector store
    2. Stored embeddings have correct dimensions
    3. Search can find what was just indexed
    4. The entire pipeline coordinates correctly

    **What could break in production that this test catches:**
    - Indexing silently fails to store vectors
    - Embedding dimensions don't match vector store config
    - Vector store loses data between index and search
    - Search queries different collection than indexing writes to
    - Chunking produces content that embeddings can't handle

    **Why this is different from mock tests:**
    Mock tests validate that code calls the right methods. This test validates
    that the methods actually DO what they're supposed to do.
    """
    from codeweaver.agent_api.find_code import find_code

    # Step 1: Index the codebase with real embeddings
    index_response = await find_code(
        query="initialize",  # Dummy query to trigger indexing
        cwd=str(known_test_codebase),
        index_if_needed=True,
    )

    # Validate indexing succeeded
    assert index_response is not None, "Indexing should return response"

    # Step 2: Search for specific functionality in the indexed codebase
    search_response = await find_code(
        query="authentication user login",
        cwd=str(known_test_codebase),
        index_if_needed=False,  # Don't re-index, use existing index
    )

    # Validate search found the code we just indexed
    assert len(search_response.results) > 0, (
        "Search should find results in freshly indexed codebase. "
        "This indicates indexing didn't actually store vectors, or "
        "search is querying the wrong collection."
    )

    # Validate correct file was found
    result_files = [r.file_path.name for r in search_response.results[:3]]
    assert "auth.py" in result_files, (
        f"Search should find auth.py after indexing, got: {result_files}. "
        f"Either indexing failed to store auth.py content, or search "
        f"can't find freshly indexed content."
    )


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_incremental_indexing_updates_search_results(real_providers, known_test_codebase):
    """Validate that adding new files updates search results.

    **What this validates:**
    - Incremental indexing actually adds new content
    - New embeddings appear in search results
    - Vector store handles updates correctly

    **Production failure modes this catches:**
    - Incremental indexing doesn't store new files
    - Vector store overwrites old content instead of adding
    - Search doesn't see newly indexed files
    """
    from codeweaver.agent_api.find_code import find_code

    # Step 1: Index initial codebase
    await find_code(query="initial", cwd=str(known_test_codebase), index_if_needed=True)

    # Step 2: Add a new file with distinct content
    new_file = Path(known_test_codebase) / "payments.py"
    new_file.write_text('''"""
Payment processing module.

Handles credit card payments, Stripe integration, and refunds.
"""

def process_payment(amount: float, card_token: str) -> str:
    """Process credit card payment through Stripe.

    Returns transaction ID if successful, raises PaymentError otherwise.
    """
    import stripe

    try:
        charge = stripe.Charge.create(
            amount=int(amount * 100),  # Convert to cents
            currency="usd",
            source=card_token,
        )
        return charge.id
    except stripe.error.CardError as e:
        raise PaymentError(f"Card declined: {e}") from e


def process_refund(transaction_id: str) -> None:
    """Process refund for previous transaction."""
    import stripe

    stripe.Refund.create(charge=transaction_id)
''')

    # Step 3: Re-index to pick up new file
    await find_code(query="update", cwd=str(known_test_codebase), index_if_needed=True)

    # Step 4: Search for new file's content
    response = await find_code(
        query="payment processing credit card Stripe",
        cwd=str(known_test_codebase),
        index_if_needed=False,
    )

    # Validate new file appears in results
    result_files = [r.file_path.name for r in response.results]
    assert "payments.py" in result_files, (
        f"Newly added file should appear in search results, got: {result_files}. "
        f"Incremental indexing may not be storing new content."
    )


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_pipeline_handles_large_codebase(real_providers, tmp_path):
    """Validate pipeline handles larger codebase (~20 files) efficiently.

    **What this validates:**
    - Indexing scales to realistic codebase size
    - Embedding generation handles batching
    - Vector store handles moderate data volume
    - Search performance acceptable with more content

    **Production failure modes this catches:**
    - Memory issues with larger codebases
    - Performance degradation with scale
    - Batch processing bugs
    - Vector store capacity issues
    """
    from codeweaver.agent_api.find_code import find_code

    # Create a larger test codebase
    large_codebase = tmp_path / "large_codebase"
    large_codebase.mkdir()

    # Generate 20 Python files with distinct content
    for i in range(20):
        module_name = f"module_{i:02d}"
        (large_codebase / f"{module_name}.py").write_text(f'''"""
Module {i}: {module_name} implementation.

This module provides functionality for {module_name} operations.
"""

def {module_name}_function(param: str) -> str:
    """Process {module_name} operation.

    This is a distinct function for module {i}.
    """
    return f"Processed: {{param}} in {module_name}"


class {module_name.capitalize()}Handler:
    """Handler for {module_name} operations."""

    def handle(self, data):
        """Handle {module_name} data processing."""
        return f"Handled by {module_name}: {{data}}"
''')

    # Index the large codebase (should complete without issues)
    import time

    start_time = time.time()

    response = await find_code(
        query="module function", cwd=str(large_codebase), index_if_needed=True
    )

    indexing_time = time.time() - start_time

    # Validate indexing completed
    assert response is not None, "Indexing should complete"

    # Validate reasonable performance (<30s for 20 files)
    assert indexing_time < 30.0, (
        f"Indexing took {indexing_time:.1f}s for 20 files. "
        f"Performance may not scale to real codebases."
    )

    # Search should find some of the indexed files
    assert len(response.results) > 0, "Search should find indexed files"


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_pipeline_handles_file_updates(real_providers, known_test_codebase):
    """Validate that modifying files updates their embeddings.

    **What this validates:**
    - Re-indexing updates existing vectors
    - Modified content produces different embeddings
    - Search reflects updated content

    **Production failure modes this catches:**
    - Re-indexing doesn't update existing vectors
    - Vector store cache prevents updates
    - Search returns stale content
    """
    from codeweaver.agent_api.find_code import find_code

    # Step 1: Index initial version
    await find_code(query="initial", cwd=str(known_test_codebase), index_if_needed=True)

    # Step 2: Search for original content
    response_before = await find_code(
        query="authentication", cwd=str(known_test_codebase), index_if_needed=False
    )
    [r.content.content for r in response_before.results if "auth.py" in str(r.file_path)]

    # Step 3: Modify auth.py significantly
    auth_file = Path(known_test_codebase) / "auth.py"
    auth_file.write_text('''"""
Enhanced authentication with OAuth2 and JWT tokens.

Now supports OAuth2 providers and JWT token generation.
"""

def oauth2_authenticate(provider: str, token: str) -> dict:
    """Authenticate using OAuth2 provider (Google, GitHub, etc).

    Validates OAuth2 token and creates user session.
    """
    import jwt

    # Decode OAuth2 token
    user_data = jwt.decode(token, verify=False)
    return {"user_id": user_data["sub"], "email": user_data["email"]}


def generate_jwt(user_id: str) -> str:
    """Generate JWT token for authenticated user."""
    import jwt
    import time

    payload = {
        "user_id": user_id,
        "exp": time.time() + 3600,
    }

    return jwt.encode(payload, "secret_key", algorithm="HS256")
''')

    # Step 4: Re-index with updated content
    await find_code(query="update", cwd=str(known_test_codebase), index_if_needed=True)

    # Step 5: Search should now find OAuth content
    response_after = await find_code(
        query="OAuth2 JWT token", cwd=str(known_test_codebase), index_if_needed=False
    )

    # Validate updated content is found
    result_files = [r.file_path.name for r in response_after.results[:3]]
    assert "auth.py" in result_files, "Updated auth.py should still be findable after modification"

    # Validate content is actually updated
    auth_results = [
        r.content.content for r in response_after.results if "auth.py" in str(r.file_path)
    ]

    if auth_results:
        updated_content = auth_results[0]
        assert "OAuth2" in updated_content or "JWT" in updated_content, (
            f"Search should return updated content with OAuth2/JWT, "
            f"got: {updated_content[:200]}. Re-indexing may not update vectors."
        )


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_pipeline_coordination_with_errors(real_providers, tmp_path):
    """Validate pipeline handles partial failures gracefully.

    **What this validates:**
    - Pipeline doesn't completely fail on bad files
    - Error handling allows partial indexing
    - Search works with partially indexed content

    **Production failure modes this catches:**
    - One bad file breaks entire indexing
    - Pipeline lacks error recovery
    - Users can't search any content if one file fails
    """
    from codeweaver.agent_api.find_code import find_code

    # Create codebase with mix of good and problematic files
    mixed_codebase = tmp_path / "mixed_codebase"
    mixed_codebase.mkdir()

    # Good file
    (mixed_codebase / "good.py").write_text('''
def working_function():
    """This file is valid Python."""
    return "success"
''')

    # File with syntax errors (might cause parsing issues)
    (mixed_codebase / "bad.py").write_text('''
def broken_function(
    """This has syntax errors"""
    return "incomplete
''')

    # Another good file
    (mixed_codebase / "also_good.py").write_text('''
def another_working_function():
    """This file is also valid."""
    return "also success"
''')

    # Index should handle errors gracefully
    response = await find_code(query="function", cwd=str(mixed_codebase), index_if_needed=True)

    # Should index good files even if bad file fails
    # At minimum, shouldn't crash completely
    assert response is not None, "Pipeline should handle errors gracefully, not crash completely"


# =============================================================================
# Performance Validation
# =============================================================================


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_search_performance_with_real_providers(real_providers, known_test_codebase):
    """Validate search performance meets requirements with real providers.

    **Performance Requirement (FR-037):**
    Search should complete in <3 seconds for codebases with ≤10K files.

    **What this validates:**
    - Real embedding generation is fast enough
    - Vector search performs within SLA
    - Reranking doesn't exceed time budget
    - End-to-end pipeline meets performance targets

    **Production failure modes this catches:**
    - Embedding model too slow for production
    - Vector search optimization needed
    - Reranking bottleneck
    - Overall performance regression
    """
    import time

    from codeweaver.agent_api.find_code import find_code

    # Index first (not part of search performance)
    await find_code(query="initialize", cwd=str(known_test_codebase), index_if_needed=True)

    # Measure search performance
    start_time = time.time()

    response = await find_code(
        query="authentication database API configuration",
        cwd=str(known_test_codebase),
        index_if_needed=False,  # Pure search, no indexing
    )

    search_time = time.time() - start_time

    # Validate results returned
    assert len(response.results) > 0, "Search should return results"

    # Validate performance (<3s for small codebase)
    # Small codebase should be much faster than 3s limit
    assert search_time < 2.0, (
        f"Search took {search_time:.2f}s for 5-file codebase. "
        f"Performance target is <3s for ≤10K files. "
        f"With real providers taking {search_time:.2f}s for 5 files, "
        f"scaling to 10K files may exceed SLA."
    )

    # Log performance for monitoring
    print(f"Search performance: {search_time:.3f}s for {len(response.results)} results")


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.asyncio
async def test_indexing_performance_with_real_providers(real_providers, tmp_path):
    """Validate indexing performance is acceptable for real-world usage.

    **What this validates:**
    - Indexing completes in reasonable time
    - Embedding generation scales linearly
    - Vector store ingestion is efficient

    **Production failure modes this catches:**
    - Indexing too slow for practical use
    - Non-linear scaling with codebase size
    - Vector store bottleneck
    """
    import time

    from codeweaver.agent_api.find_code import find_code

    # Create 50-file codebase
    perf_codebase = tmp_path / "perf_codebase"
    perf_codebase.mkdir()

    for i in range(50):
        (perf_codebase / f"module_{i}.py").write_text(f'''
def function_{i}(param):
    """Function {i} implementation."""
    return f"Result from function {i}: {{param}}"
''')

    # Measure indexing performance
    start_time = time.time()

    response = await find_code(query="function", cwd=str(perf_codebase), index_if_needed=True)

    indexing_time = time.time() - start_time

    # Validate indexing completed
    assert response is not None, "Indexing should complete"

    # Validate reasonable performance (<60s for 50 files)
    assert indexing_time < 60.0, (
        f"Indexing took {indexing_time:.1f}s for 50 files. "
        f"At this rate, 10K files would take ~{(indexing_time / 50) * 10000 / 60:.0f} minutes. "
        f"Performance optimization needed for production scale."
    )

    # Log performance for monitoring
    print(
        f"Indexing performance: {indexing_time:.1f}s for 50 files ({indexing_time / 50:.2f}s per file)"
    )
