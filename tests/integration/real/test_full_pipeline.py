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
# Fixtures
# =============================================================================


# =============================================================================
# Full Pipeline Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
@pytest.mark.timeout(600)  # 10 minutes for real embedding generation + indexing
async def test_full_pipeline_index_then_search(
    indexed_test_project, actual_vector_store, clean_container
):
    """Validate complete workflow: index fresh codebase, then search it."""
    from codeweaver.server.agent_api import IntentType, find_code

    # Search for specific functionality in the indexed codebase.
    # Settings and vector store are already configured by indexed_test_project fixture.
    search_response = await find_code(
        query="authentication user login", intent=IntentType.UNDERSTAND
    )

    # Validate search found the code we indexed
    assert len(search_response.matches) > 0

    # Validate correct file was found
    result_files = [r.file.path.name for r in search_response.matches[:3]]
    assert "auth.py" in result_files


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
@pytest.mark.timeout(600)  # 10 minutes for real embedding generation + indexing
async def test_incremental_indexing_updates_search_results(
    indexed_test_project, actual_vector_store, clean_container
):
    """Validate that adding new files updates search results."""
    from codeweaver.engine import IndexingService
    from codeweaver.server.agent_api import IntentType, find_code

    # Add a new file with distinct content
    new_file = Path(indexed_test_project) / "payments.py"
    new_file.write_text('''"""
Payment processing module.

Handles credit card payments, Stripe integration, and refunds.
"""

def process_payment(amount: float, card_token: str) -> str:
    """Process credit card payment through Stripe."""
    return "txn_123"
''')

    # Re-index using the indexer already configured by indexed_test_project fixture
    indexer = await clean_container.resolve(IndexingService)
    await indexer.index_project(force_reindex=True)

    # Search for new file's content
    response = await find_code(
        query="payment processing credit card Stripe", intent=IntentType.UNDERSTAND
    )

    # Validate new file appears in results
    result_files = [r.file.path.name for r in response.matches]
    assert "payments.py" in result_files


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
@pytest.mark.timeout(900)  # 15 minutes for 20 files with real embeddings
async def test_pipeline_handles_large_codebase(tmp_path, actual_vector_store, clean_container):
    """Validate pipeline handles larger codebase (~20 files) efficiently."""
    import time

    import codeweaver.core.dependencies
    import codeweaver.engine.dependencies
    import codeweaver.server.dependencies  # noqa: F401 - ensures @dependency_provider decorators run

    from codeweaver.core.config.loader import get_settings_async
    from codeweaver.core.config.settings_type import CodeWeaverSettingsType
    from codeweaver.core.types.sentinel import UNSET
    from codeweaver.engine import IndexingService
    from codeweaver.providers import VectorStoreProvider
    from codeweaver.providers.config.categories.vector_store import (
        MemoryVectorStoreProviderSettings,
    )
    from codeweaver.providers.config.clients.vector_store import QdrantClientOptions
    from codeweaver.providers.config.profiles import ProviderProfile
    from codeweaver.providers.config.providers import ProviderSettings
    from codeweaver.providers.dependencies.providers import (
        PrimaryVectorStoreProviderDep,
        VectorStoreProvidersDep,
    )
    from codeweaver.server import CodeWeaverState
    from codeweaver.server.agent_api import IntentType, find_code

    # Create a larger test codebase
    large_codebase = tmp_path / "large_codebase"
    large_codebase.mkdir()
    (large_codebase / ".git").mkdir()  # Git marker for project root

    # Generate 20 Python files
    for i in range(20):
        module_name = f"module_{i:02d}"
        (large_codebase / f"{module_name}.py").write_text(f"def {module_name}_function(): pass")

    project_path = large_codebase.resolve()

    async def get_test_settings() -> CodeWeaverSettingsType:
        settings = await get_settings_async()
        settings.project_path = project_path
        settings.project_name = f"test_large_{project_path.name}"
        if settings.provider is UNSET:
            profile_settings = ProviderProfile.TESTING.as_provider_settings()
            profile_settings["vector_store"] = (
                MemoryVectorStoreProviderSettings(
                    project_name=f"test_large_{project_path.name}",
                    client_options=QdrantClientOptions(location=":memory:"),
                ),
            )
            settings.provider = ProviderSettings.model_construct(**profile_settings)
        return settings

    clean_container.override(CodeWeaverSettingsType, get_test_settings)
    clean_container.override(VectorStoreProvider, actual_vector_store)
    clean_container.override(VectorStoreProvidersDep, (actual_vector_store,))
    clean_container.override(PrimaryVectorStoreProviderDep, actual_vector_store)

    # Store settings in singletons for sync access
    test_settings = await clean_container.resolve(CodeWeaverSettingsType)
    clean_container._singletons[CodeWeaverSettingsType] = test_settings

    # Initialize global state
    state = await clean_container.resolve(CodeWeaverState)
    from codeweaver.server import server

    server._state = state

    try:
        start_time = time.time()
        indexer = await clean_container.resolve(IndexingService)
        await indexer.index_project(force_reindex=True)
        indexing_time = time.time() - start_time

        # Search
        response = await find_code(query="module function", intent=IntentType.UNDERSTAND)

        assert response is not None
        assert indexing_time < 30.0
        assert len(response.matches) > 0
    finally:
        server._state = None
        clean_container.clear_overrides()


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
@pytest.mark.timeout(600)  # 10 minutes for real embedding generation + indexing
async def test_pipeline_handles_file_updates(
    indexed_test_project, actual_vector_store, clean_container
):
    """Validate that modifying files updates their embeddings."""
    from codeweaver.engine import IndexingService
    from codeweaver.server.agent_api import IntentType, find_code

    # Modify auth.py significantly
    auth_file = Path(indexed_test_project) / "auth.py"
    auth_file.write_text("def oauth2_authenticate(): pass")

    # Re-index using the indexer already configured by indexed_test_project fixture
    indexer = await clean_container.resolve(IndexingService)
    await indexer.index_project(force_reindex=True)

    # Search should now find OAuth content
    response_after = await find_code(query="OAuth2 JWT token", intent=IntentType.UNDERSTAND)

    # Validate updated content is found
    result_files = [r.file.path.name for r in response_after.matches[:3]]
    assert "auth.py" in result_files


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
@pytest.mark.timeout(600)  # 10 minutes for real embedding generation + indexing
async def test_pipeline_coordination_with_errors(tmp_path, actual_vector_store, clean_container):
    """Validate pipeline handles partial failures gracefully."""
    import codeweaver.core.dependencies
    import codeweaver.engine.dependencies
    import codeweaver.server.dependencies  # noqa: F401 - ensures @dependency_provider decorators run

    from codeweaver.core.config.loader import get_settings_async
    from codeweaver.core.config.settings_type import CodeWeaverSettingsType
    from codeweaver.core.types.sentinel import UNSET
    from codeweaver.engine import IndexingService
    from codeweaver.providers import VectorStoreProvider
    from codeweaver.providers.config.categories.vector_store import (
        MemoryVectorStoreProviderSettings,
    )
    from codeweaver.providers.config.clients.vector_store import QdrantClientOptions
    from codeweaver.providers.config.profiles import ProviderProfile
    from codeweaver.providers.config.providers import ProviderSettings
    from codeweaver.providers.dependencies.providers import (
        PrimaryVectorStoreProviderDep,
        VectorStoreProvidersDep,
    )
    from codeweaver.server import CodeWeaverState
    from codeweaver.server.agent_api import IntentType, find_code

    # Create codebase with mix of good and problematic files
    mixed_codebase = tmp_path / "mixed_codebase"
    mixed_codebase.mkdir()
    (mixed_codebase / ".git").mkdir()

    (mixed_codebase / "good.py").write_text("def working_function(): return 'success'")
    (mixed_codebase / "bad.py").write_text("def broken_function(")

    project_path = mixed_codebase.resolve()

    async def get_test_settings() -> CodeWeaverSettingsType:
        settings = await get_settings_async()
        settings.project_path = project_path
        settings.project_name = f"test_mixed_{project_path.name}"
        if settings.provider is UNSET:
            profile_settings = ProviderProfile.TESTING.as_provider_settings()
            profile_settings["vector_store"] = (
                MemoryVectorStoreProviderSettings(
                    project_name=f"test_mixed_{project_path.name}",
                    client_options=QdrantClientOptions(location=":memory:"),
                ),
            )
            settings.provider = ProviderSettings.model_construct(**profile_settings)
        return settings

    clean_container.override(CodeWeaverSettingsType, get_test_settings)
    clean_container.override(VectorStoreProvider, actual_vector_store)
    clean_container.override(VectorStoreProvidersDep, (actual_vector_store,))
    clean_container.override(PrimaryVectorStoreProviderDep, actual_vector_store)

    # Store settings in singletons for sync access
    test_settings = await clean_container.resolve(CodeWeaverSettingsType)
    clean_container._singletons[CodeWeaverSettingsType] = test_settings

    # Initialize global state
    state = await clean_container.resolve(CodeWeaverState)
    from codeweaver.server import server

    server._state = state

    try:
        indexer = await clean_container.resolve(IndexingService)
        await indexer.index_project(force_reindex=True)

        response = await find_code(query="function", intent=IntentType.UNDERSTAND)

        assert response is not None
    finally:
        server._state = None
        clean_container.clear_overrides()


# =============================================================================
# Performance Validation
# =============================================================================


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.benchmark
@pytest.mark.asyncio
@pytest.mark.timeout(600)  # 10 minutes including fixture setup
async def test_search_performance_with_real_providers(
    indexed_test_project, actual_vector_store, clean_container
):
    """Validate search performance meets requirements with real providers."""
    import time

    from codeweaver.server.agent_api import IntentType, find_code

    # Settings and vector store are already configured by indexed_test_project fixture.
    start_time = time.time()
    response = await find_code(
        query="authentication database API configuration", intent=IntentType.UNDERSTAND
    )
    search_time = time.time() - start_time

    assert len(response.matches) > 0
    assert search_time < 2.0


@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.asyncio
@pytest.mark.timeout(1200)  # 20 minutes for 50 files with real embeddings
async def test_indexing_performance_with_real_providers(
    tmp_path, actual_vector_store, clean_container
):
    """Validate indexing performance is acceptable for real-world usage."""
    import time

    import codeweaver.core.dependencies
    import codeweaver.engine.dependencies
    import codeweaver.server.dependencies  # noqa: F401 - ensures @dependency_provider decorators run

    from codeweaver.core.config.loader import get_settings_async
    from codeweaver.core.config.settings_type import CodeWeaverSettingsType
    from codeweaver.core.types.sentinel import UNSET
    from codeweaver.engine import IndexingService
    from codeweaver.providers import VectorStoreProvider
    from codeweaver.providers.config.categories.vector_store import (
        MemoryVectorStoreProviderSettings,
    )
    from codeweaver.providers.config.clients.vector_store import QdrantClientOptions
    from codeweaver.providers.config.profiles import ProviderProfile
    from codeweaver.providers.config.providers import ProviderSettings
    from codeweaver.providers.dependencies.providers import (
        PrimaryVectorStoreProviderDep,
        VectorStoreProvidersDep,
    )
    from codeweaver.server import CodeWeaverState
    from codeweaver.server.agent_api import IntentType, find_code

    # Create 50-file codebase
    perf_codebase = tmp_path / "perf_codebase"
    perf_codebase.mkdir()
    (perf_codebase / ".git").mkdir()

    for i in range(50):
        (perf_codebase / f"module_{i}.py").write_text(f"def function_{i}(): pass")

    project_path = perf_codebase.resolve()

    async def get_test_settings() -> CodeWeaverSettingsType:
        settings = await get_settings_async()
        settings.project_path = project_path
        settings.project_name = f"test_perf_{project_path.name}"
        if settings.provider is UNSET:
            profile_settings = ProviderProfile.TESTING.as_provider_settings()
            profile_settings["vector_store"] = (
                MemoryVectorStoreProviderSettings(
                    project_name=f"test_perf_{project_path.name}",
                    client_options=QdrantClientOptions(location=":memory:"),
                ),
            )
            settings.provider = ProviderSettings.model_construct(**profile_settings)
        return settings

    clean_container.override(CodeWeaverSettingsType, get_test_settings)
    clean_container.override(VectorStoreProvider, actual_vector_store)
    clean_container.override(VectorStoreProvidersDep, (actual_vector_store,))
    clean_container.override(PrimaryVectorStoreProviderDep, actual_vector_store)

    # Store settings in singletons for sync access
    test_settings = await clean_container.resolve(CodeWeaverSettingsType)
    clean_container._singletons[CodeWeaverSettingsType] = test_settings

    # Initialize global state
    state = await clean_container.resolve(CodeWeaverState)
    from codeweaver.server import server

    server._state = state

    try:
        start_time = time.time()
        indexer = await clean_container.resolve(IndexingService)
        await indexer.index_project(force_reindex=True)
        indexing_time = time.time() - start_time

        response = await find_code(query="function", intent=IntentType.UNDERSTAND)

        assert response is not None
        assert indexing_time < 60.0
    finally:
        server._state = None
        clean_container.clear_overrides()
