# sourcery skip: docstrings-for-classes, require-parameter-annotation, require-return-annotation
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Integration test fixtures for provider configuration."""

from __future__ import annotations

import contextlib
import logging
import os

from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codeweaver.core.utils import has_package
from codeweaver.providers import (
    FastEmbedEmbeddingProvider,
    MemoryVectorStoreProvider,
    MemoryVectorStoreProviderSettings,
)


if TYPE_CHECKING:
    from codeweaver.core import CodeChunk, DictView
    from codeweaver.providers import (
        EmbeddingModelCapabilities,
        FastEmbedEmbeddingProvider,
        FastEmbedRerankingProvider,
        FastEmbedSparseProvider,
        RerankingModelCapabilities,
        SentenceTransformersEmbeddingProvider,
        SentenceTransformersRerankingProvider,
        SentenceTransformersSparseProvider,
        SparseEmbeddingModelCapabilities,
    )
    from codeweaver.server import (
        CodeWeaverSettingsDict,
        EmbeddingProviderSettings,
        RerankingProviderSettings,
        SparseEmbeddingProviderSettings,
    )

logger = logging.getLogger(__name__)

# ===========================================================================
# CLI Mock Fixtures
# ===========================================================================

os.environ["CODEWEAVER_TEST_MODE"] = "true"

# Disable SSL verification warnings for tests (WSL time sync issues cause false positives)
import warnings


with contextlib.suppress(ImportError):
    from urllib3.exceptions import SystemTimeWarning

    warnings.filterwarnings("ignore", category=SystemTimeWarning)

# Also suppress general SSL and verification warnings that can be triggered by time issues
warnings.filterwarnings("ignore", message=".*System time is way off.*")
warnings.filterwarnings("ignore", message=".*SSL verification errors.*")
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")


def _set_settings() -> DictView[CodeWeaverSettingsDict]:
    """Get the global settings for tests.

    With CODEWEAVER_TEST_MODE="true", CodeWeaverSettings automatically loads
    codeweaver.test.toml which uses lightweight models:
    - embedding: minishlab/potion-base-8M (256-dim, fast)
    - sparse: qdrant/bm25 (fast BM25 tokenization)
    - reranking: cross-encoder/ms-marco-TinyBERT-L2-v2 (tiny, fast)
    - vector_store: memory (in-memory, no Docker needed)

    No manual loading needed - the config system handles it automatically.
    """
    from codeweaver.core.config.loader import get_settings

    # Just return the settings map - config system already loaded codeweaver.test.toml
    # because CODEWEAVER_TEST_MODE="true" (set at top of this file)
    return get_settings().view()  # ty:ignore[invalid-return-type]


_settings: DictView[CodeWeaverSettingsDict] = _set_settings()

HAS_SENTENCE_TRANSFORMERS = has_package("sentence_transformers") is not None
HAS_FASTEMBED = has_package("fastembed") is not None or has_package("fastembed_gpu") is not None


def _get_configs(
    *, sparse: bool = False, rerank: bool = False
) -> EmbeddingProviderSettings | SparseEmbeddingProviderSettings | RerankingProviderSettings:
    """Get provider settings for testing based on available libraries.

    Uses the TESTING profile (same as BACKUP) which provides lightweight local models
    for development and testing.

    Args:
        sparse: If True, return sparse embedding settings
        rerank: If True, return reranking settings

    Returns:
        Provider settings for the requested provider type
    """
    from codeweaver.providers.config.profiles import ProviderProfile

    # Get the testing profile configuration
    profile = ProviderProfile.TESTING.value

    # Extract the appropriate settings based on parameters
    if rerank:
        # Reranking settings are stored as a tuple, get the first element
        return profile.reranking[0]
    return profile.sparse_embedding if sparse else profile.embedding


@pytest.fixture
def mock_confirm(clean_container) -> MagicMock:
    """Mock UserInteraction for CLI tests.

    Returns a mock Interaction object that automatically returns True for all confirmations.
    Tests can override by setting mock_confirm.confirm.return_value to False.
    """
    from codeweaver.cli.ui import UserInteraction

    mock = MagicMock()
    mock.confirm.return_value = True

    # Override in DI container
    clean_container.override(UserInteraction, mock)

    return mock


# ===========================================================================
# Mock Provider Fixtures
# ===========================================================================


@pytest.fixture
def mock_embedding_provider() -> AsyncMock:
    """Provide a mock embedding provider that returns test embeddings."""
    mock_provider = AsyncMock()
    # Return batch of embeddings (list of lists)
    mock_provider.embed_query = AsyncMock(
        return_value=[[0.1, 0.2, 0.3, 0.4, 0.5]]  # Single query embedding in batch format
    )
    mock_provider.embed_batch = AsyncMock(
        return_value=[
            [0.1, 0.2, 0.3, 0.4, 0.5],  # First chunk embedding
            [0.2, 0.3, 0.4, 0.5, 0.6],  # Second chunk embedding
        ]
    )
    return mock_provider


def _get_caps() -> tuple[
    EmbeddingModelCapabilities | None,
    SparseEmbeddingModelCapabilities | None,
    RerankingModelCapabilities | None,
]:
    from codeweaver.providers.embedding.capabilities.resolver import (
        EmbeddingCapabilityResolver,
        SparseEmbeddingCapabilityResolver,
    )
    from codeweaver.providers.reranking.capabilities.resolver import RerankingCapabilityResolver

    settings = (_get_configs(), _get_configs(sparse=True), _get_configs(rerank=True))

    embed_resolver = EmbeddingCapabilityResolver()
    sparse_resolver = SparseEmbeddingCapabilityResolver()
    rerank_resolver = RerankingCapabilityResolver()

    return (
        embed_resolver.resolve(settings[0].model_name),
        sparse_resolver.resolve(settings[1].model_name),
        rerank_resolver.resolve(settings[2].model_name),
    )


@pytest.fixture
async def actual_dense_embedding_provider() -> (
    SentenceTransformersEmbeddingProvider | FastEmbedEmbeddingProvider
):
    """Provide an actual dense embedding provider using SentenceTransformers."""
    caps, _, _ = _get_caps()
    config = _get_configs()
    # Manually instantiate for tests instead of using registry
    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersEmbeddingProvider,
    )
    from codeweaver.providers.embedding.registry import EmbeddingRegistry

    return SentenceTransformersEmbeddingProvider(
        client=None,  # Not needed for ST provider usually or handles internally
        registry=EmbeddingRegistry(),
        caps=caps,
        config=config,
        cache_manager=None,
    )


@pytest.fixture
def mock_sparse_provider() -> AsyncMock:
    """Provide a mock sparse embedding provider."""
    mock_provider = AsyncMock()
    # Sparse embeddings in new format with indices and values
    mock_provider.embed_query = AsyncMock(
        return_value=[{"indices": [0, 2, 4], "values": [0.1, 0.3, 0.5]}]  # Sparse query embedding
    )
    mock_provider.embed_batch = AsyncMock(
        return_value=[
            {"indices": [0, 2, 4], "values": [0.1, 0.3, 0.5]},  # First sparse embedding
            {"indices": [1, 3], "values": [0.2, 0.4]},  # Second sparse embedding
        ]
    )
    return mock_provider


@pytest.fixture
async def actual_sparse_embedding_provider() -> (
    SentenceTransformersSparseProvider | FastEmbedSparseProvider
):
    """Provide an actual sparse embedding provider using SentenceTransformers."""
    _, caps, _ = _get_caps()
    config = _get_configs(sparse=True)

    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersSparseEmbeddingProvider,
    )
    from codeweaver.providers.embedding.registry import EmbeddingRegistry

    return SentenceTransformersSparseEmbeddingProvider(
        client=None, registry=EmbeddingRegistry(), caps=caps, config=config
    )


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Provide a mock vector store that returns search results."""
    from codeweaver.core import (
        ChunkKind,
        CodeChunk,
        ExtCategory,
        SearchResult,
        SemanticSearchLanguage,
        Span,
        uuid7,
    )

    mock_store = AsyncMock()

    # Create test chunks for search results
    def create_test_chunk(name: str, content: str, file_path: Path) -> CodeChunk:
        chunk_id = uuid7()
        return CodeChunk(
            chunk_id=chunk_id,
            ext_category=ExtCategory.from_language(SemanticSearchLanguage.PYTHON, ChunkKind.CODE),
            chunk_name=name,
            file_path=file_path,
            language=SemanticSearchLanguage.PYTHON,
            content=content,
            line_range=Span(start=1, end=10, source_id=chunk_id),
        )

    # Create mock search results
    test_chunks = [
        create_test_chunk(
            "test_function", "def test_function():\n    pass", Path("tests/test_file.py")
        ),
        create_test_chunk(
            "authenticate",
            "def authenticate(user, password):\n    return True",
            Path("src/auth.py"),
        ),
    ]

    search_results = [
        SearchResult(
            content=chunk,
            file_path=chunk.file_path,
            score=0.9 - i * 0.1,
            dense_score=0.9 - i * 0.1,
            sparse_score=0.8 - i * 0.1,
            relevance_score=0.9 - i * 0.1,
        )
        for i, chunk in enumerate(test_chunks)
    ]

    mock_store.search = AsyncMock(return_value=search_results)
    return mock_store


_shared_memory_vector_store: MemoryVectorStoreProvider | None = None


@pytest.fixture
async def actual_vector_store() -> MemoryVectorStoreProvider:
    """Provide an actual in-memory vector store provider.

    Uses a singleton instance and a FIXED collection name to ensure that
    different components (e.g., Indexer and Search) share the same in-memory data.
    """
    from codeweaver.core import get_container
    from codeweaver.providers import MemoryVectorStoreProvider, VectorStoreProvider

    global _shared_memory_vector_store
    if _shared_memory_vector_store is None:
        # Get embedding capabilities to construct EmbeddingCapabilityGroup
        from codeweaver.providers.types import ConfiguredCapability, EmbeddingCapabilityGroup

        dense_caps, sparse_caps, _ = _get_caps()
        dense_config = _get_configs()
        sparse_config = _get_configs(sparse=True)

        # Create ConfiguredCapability objects
        capabilities = [
            ConfiguredCapability(capability=dense_caps, config=dense_config),
            ConfiguredCapability(capability=sparse_caps, config=sparse_config),
        ]

        # Create EmbeddingCapabilityGroup
        caps = EmbeddingCapabilityGroup.from_capabilities(capabilities)

        # Create in-memory Qdrant client explicitly
        from qdrant_client import AsyncQdrantClient

        client = AsyncQdrantClient(location=":memory:")

        # Create collection config with test collection name
        from codeweaver.providers import CollectionConfig

        collection = CollectionConfig(collection_name="codeweaver-test-collection")
        config = MemoryVectorStoreProviderSettings(collection=collection)

        # Create provider with explicit in-memory client
        _shared_memory_vector_store = MemoryVectorStoreProvider(
            client=client, config=config, caps=caps
        )

        # Initialize the provider (this sets up internal state)
        await _shared_memory_vector_store._initialize()

    # Override in DI container
    get_container().override(VectorStoreProvider, _shared_memory_vector_store)

    import sys

    logger.debug(
        "actual_vector_store returning instance %d with collection %s",
        id(_shared_memory_vector_store),
        getattr(_shared_memory_vector_store, "_collection", "N/A"),
    )
    sys.stdout.flush()
    return _shared_memory_vector_store


async def _reset_vector_store_collection(store: MemoryVectorStoreProvider) -> None:
    """Delete and recreate the shared vector store collection to ensure a clean state."""
    if store and store.client and store.collection_name:
        with contextlib.suppress(Exception):
            await store.client.delete_collection(store.collection_name)
        if hasattr(store, "_known_collections"):
            store._known_collections.clear()
        with contextlib.suppress(Exception):
            await store._ensure_collection(store.collection_name)


def _reset_embedding_caches() -> None:
    """Reset embedding registry and cache manager state between tests.

    Clears the global EmbeddingRegistry singleton and removes embedding-related
    DI singletons (EmbeddingRegistry, EmbeddingCacheManager, EmbeddingProvider,
    SparseEmbeddingProvider, IndexingService) so the next test starts with fresh
    instances. Without this, the hash-based deduplication in EmbeddingCacheManager
    carries over between tests: re-indexed chunks with new UUIDs but same content
    are "deduplicated away" with no embeddings registered, causing upsert to fail.

    Key subtlety: EmbeddingRegistry.__init__ calls container.register() to register
    itself as a lambda factory. Over multiple tests, stale lambdas accumulate in
    _factories[EmbeddingRegistry] and _get_factory() returns the last one (the stale
    old instance). We must prune these lambda factories so _get_main_registry() is
    the sole factory, ensuring that each resolution calls get_embedding_registry()
    which returns the freshly-reset _main_registry.
    """
    import contextlib

    from codeweaver.core import get_container
    from codeweaver.providers.embedding.registry import reset_embedding_registry

    # Reset the module-level global registry so next call creates a fresh instance
    reset_embedding_registry()

    container = get_container()

    with contextlib.suppress(Exception):
        from codeweaver.providers.embedding.registry import EmbeddingRegistry

        # Remove the singleton so the next resolve calls the factory (not cache)
        container._singletons.pop(EmbeddingRegistry, None)

        # Prune stale lambda factories registered by EmbeddingRegistry.__init__.
        # Keep only named factories (like _get_main_registry from @dependency_provider).
        # The lambda entries point to old registry instances and shadow the proper factory.
        if EmbeddingRegistry in container._factories:
            container._factories[EmbeddingRegistry] = [
                (f, tags)
                for f, tags in container._factories[EmbeddingRegistry]
                if getattr(f, "__name__", None) != "<lambda>"
            ]

    with contextlib.suppress(Exception):
        from codeweaver.providers.embedding.cache_manager import EmbeddingCacheManager

        container._singletons.pop(EmbeddingCacheManager, None)

    # Remove embedding provider singletons (they hold a reference to cache_manager).
    with contextlib.suppress(Exception):
        from codeweaver.providers import EmbeddingProvider, SparseEmbeddingProvider

        container._singletons.pop(EmbeddingProvider, None)
        container._singletons.pop(SparseEmbeddingProvider, None)

    # Remove IndexingService singleton (it holds references to embedding providers).
    with contextlib.suppress(Exception):
        from codeweaver.engine import IndexingService

        container._singletons.pop(IndexingService, None)

    # Also clear tagged singletons that may hold embedding provider instances.
    with contextlib.suppress(Exception):
        keys_to_remove = [
            k
            for k in container._tagged_singletons
            if any(tag in k[1] for tag in ("embedding", "sparse_embedding"))
        ]
        for k in keys_to_remove:
            container._tagged_singletons.pop(k, None)


@pytest.fixture(autouse=True)
async def cleanup_shared_vector_store(
    actual_vector_store: MemoryVectorStoreProvider,
) -> AsyncGenerator[None, None]:
    """Automatically clean up the shared vector store before and after each test."""
    # Clean embedding caches before test to prevent deduplication poisoning from
    # previous tests (EmbeddingCacheManager._hash_stores persists across tests
    # as a DI singleton, causing re-indexed chunks to be skipped without embedding).
    _reset_embedding_caches()
    # Clean vector store before test to ensure no stale data from previous runs
    await _reset_vector_store_collection(actual_vector_store)
    yield
    # Clean after test to start fresh for the next test
    await _reset_vector_store_collection(actual_vector_store)
    _reset_embedding_caches()


@pytest.fixture
def mock_reranking_provider() -> AsyncMock:
    """Provide a mock reranking provider."""
    from typing import NamedTuple

    # Define a simple RerankResult structure for testing
    class RerankResult(NamedTuple):
        """Mock result"""

        chunk: CodeChunk
        score: float
        original_index: int

    mock_provider = AsyncMock()

    async def create_rerank_results(query: str, chunks: list[CodeChunk]) -> list[RerankResult]:
        # Create rerank results that maintain order but adjust scores
        # Note: async function to match the rerank signature
        return [
            RerankResult(chunk=chunk, score=0.95 - i * 0.05, original_index=i)
            for i, chunk in enumerate(chunks)
        ]

    mock_provider.rerank = AsyncMock(side_effect=create_rerank_results)
    return mock_provider


@pytest.fixture
async def actual_reranking_provider() -> (
    SentenceTransformersRerankingProvider | FastEmbedRerankingProvider
):
    """Provide an actual reranking provider using SentenceTransformers."""
    _, _, caps = _get_caps()
    config = _get_configs(rerank=True)

    from codeweaver.core.types import Provider
    from codeweaver.providers.reranking.providers.sentence_transformers import (
        SentenceTransformersRerankingProvider,
    )

    return SentenceTransformersRerankingProvider(
        client=None, config=config, caps=caps, _provider=Provider.SENTENCE_TRANSFORMERS
    )


# ===========================================================================
# Provider Registry Configuration Fixtures
# ===========================================================================

# Removed Mock Registry Fixtures (mock_provider_registry, configured_providers)
# as they are no longer needed with DI overrides.


@pytest.fixture
def configured_providers(
    mock_embedding_provider: MagicMock,
    mock_sparse_provider: MagicMock,
    mock_vector_store: MagicMock,
    mock_reranking_provider: MagicMock,
) -> Generator[None, None, None]:
    """Fixture that overrides providers in the DI container."""
    from codeweaver.core import get_container
    from codeweaver.providers import (
        EmbeddingProvider,
        RerankingProvider,
        SparseEmbeddingProvider,
        VectorStoreProvider,
    )

    container = get_container()
    container.override(EmbeddingProvider, mock_embedding_provider)
    container.override(SparseEmbeddingProvider, mock_sparse_provider)
    container.override(VectorStoreProvider, mock_vector_store)
    container.override(RerankingProvider, mock_reranking_provider)

    call_count = [0]  # Use list for mutable counter

    def mock_time() -> float:
        call_count[0] += 1
        # Return monotonically increasing time values (start from a baseline)
        return 1000000.0 + call_count[0] * 0.001

    with patch("time.time", side_effect=mock_time):
        yield
        container.clear_overrides()


# ===========================================================================
# Settings Fixtures
# ===========================================================================


@pytest.fixture
def reset_settings() -> Generator[None, None, None]:
    """Reset DI container settings to defaults.

    This fixture provides a clean settings state by resetting the DI container.
    It's useful for tests that need to ensure settings isolation between test runs.

    Usage:
        def test_something(reset_settings):
            # Test runs with fresh settings from codeweaver.test.toml
            ...

    The fixture:
    1. Clears DI container overrides before test
    2. Resets container to force new settings creation
    3. Yields control to test
    4. Clears overrides again after test
    """
    from codeweaver.core.di import get_container, reset_container_state

    # Clear any existing overrides
    container = get_container()
    container.clear_overrides()

    # Reset container to force new settings on next resolution
    reset_container_state()

    yield

    # Cleanup: clear overrides after test
    container = get_container()
    container.clear_overrides()


@pytest.fixture
def mock_settings_with_providers() -> MagicMock:
    """Provide mock settings with provider configuration."""
    from codeweaver.server import CodeWeaverSettings as Settings

    mock_settings = MagicMock(spec=Settings)
    mock_settings.providers = {
        "embedding": {"provider": "voyage", "model": "voyage-code-3"},
        "sparse_embedding": {"provider": "fastembed", "model": "prithivida/Splade_PP_en_v1"},
        "vector_store": {"provider": "qdrant", "collection": "test_collection"},
        "reranking": {"provider": "voyage", "model": "voyage-rerank-2.5"},
    }
    return mock_settings


# ===========================================================================
# Real Provider Fixtures (Tier 2: Actual Behavior Validation)
# ===========================================================================


@pytest.fixture
def real_embedding_provider(
    actual_dense_embedding_provider: SentenceTransformersEmbeddingProvider
    | FastEmbedEmbeddingProvider,
) -> SentenceTransformersEmbeddingProvider | FastEmbedEmbeddingProvider:
    """Provide a REAL embedding provider for behavior validation."""
    return actual_dense_embedding_provider


@pytest.fixture
def real_sparse_provider(
    actual_sparse_embedding_provider: SentenceTransformersSparseProvider | FastEmbedSparseProvider,
) -> SentenceTransformersSparseProvider | FastEmbedSparseProvider:
    """Provide a sparse embedding provider - real if available, mock otherwise."""
    # Check if SparseEncoder is available
    return actual_sparse_embedding_provider


@pytest.fixture
def real_reranking_provider(
    actual_reranking_provider: SentenceTransformersRerankingProvider,
) -> SentenceTransformersRerankingProvider:
    """Provide a REAL reranking provider for relevance scoring validation."""
    return actual_reranking_provider


@pytest.fixture
async def real_vector_store(
    known_test_codebase: Path, actual_vector_store: MemoryVectorStoreProvider
) -> AsyncGenerator[MemoryVectorStoreProvider]:
    """Provide a REAL Qdrant vector store in memory mode for behavior validation.

    Creates an actual in-memory Qdrant instance that:
    1. Stores real embeddings
    2. Performs real similarity search
    3. Cleans up automatically after test

    This allows validating that:
    - Embeddings are stored correctly
    - Search actually finds relevant results
    - Vector similarity works as expected

    Perfect for CI - no Docker required, just in-memory mode.
    """
    instance: MemoryVectorStoreProvider = actual_vector_store

    # FORCE fixed collection name for test alignment
    collection_name = "codeweaver-test-collection"

    # Explicitly set collection name in config to override any global settings
    if not instance.config:
        instance.config = {}
    instance.config["collection_name"] = collection_name
    instance._collection = collection_name

    # Already initialized by actual_vector_store fixture
    yield instance

    # Cleanup: Delete collection after test
    if instance._client:
        with contextlib.suppress(Exception):
            await instance._client.delete_collection(collection_name)


@pytest.fixture
def known_test_codebase(tmp_path: Path) -> Path:
    """Create a small, known test codebase for search quality validation.

    Creates 5 Python files with distinct, searchable content:
    - auth.py: Authentication and login functions
    - database.py: Database connection and query functions
    - api.py: REST API endpoints and routing
    - config.py: Configuration loading and validation
    - utils.py: Utility functions and helpers

    Each file has distinct semantic content allowing us to write queries like:
    - "authentication" → should find auth.py in top results
    - "database connection" → should find database.py
    - "REST API" → should find api.py

    This fixture validates that the ENTIRE search pipeline works:
    - Chunking extracts meaningful code segments
    - Embeddings capture semantic meaning
    - Search finds relevant code
    - Ranking prioritizes best matches

    Returns:
        Path to the test codebase root directory
    """
    codebase_root = tmp_path / "test_codebase"
    codebase_root.mkdir()

    # auth.py - Authentication module
    (codebase_root / "auth.py").write_text('''"""
Authentication module with login, logout, and session management.

Provides user authentication, password validation, and session tracking.
"""

def authenticate_user(username: str, password: str) -> bool:
    """Authenticate user credentials against database.

    Validates username and password, checks against stored hashes.
    Returns True if authentication succeeds, False otherwise.
    """
    if not username or not password:
        raise ValueError("Username and password are required")

    # Simplified for testing - real implementation would hash passwords
    valid_users = {
        "admin": "hashed_admin_password",
        "user1": "hashed_user_password",
    }

    return valid_users.get(username) == password


def create_session(user_id: str, expires_in_seconds: int = 3600) -> str:
    """Create authenticated session for user.

    Generates session token, stores in session store, sets expiration.
    Returns session token for use in subsequent requests.
    """
    import time
    import uuid

    session_id = str(uuid.uuid4())
    session_data = {
        "user_id": user_id,
        "created_at": time.time(),
        "expires_at": time.time() + expires_in_seconds,
    }

    # Store session (simplified)
    return session_id


def logout_user(session_id: str) -> None:
    """Logout user and invalidate session.

    Removes session from session store, preventing further use.
    """
    # Remove from session store (simplified)
    pass
''')

    # database.py - Database module
    (codebase_root / "database.py").write_text('''"""
Database connection and query execution module.

Provides connection pooling, query execution, and transaction management.
"""

import sqlite3
from contextlib import contextmanager


def create_connection(db_path: str, timeout: int = 10):
    """Create database connection with error handling.

    Establishes connection to SQLite database with configured timeout.
    Raises ConnectionError if connection fails.
    """
    try:
        conn = sqlite3.connect(db_path, timeout=timeout)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn
    except sqlite3.Error as e:
        raise ConnectionError(f"Failed to connect to database: {e}") from e


@contextmanager
def get_db_transaction(db_path: str):
    """Context manager for database transactions.

    Automatically commits on success, rolls back on error.
    Ensures connection is properly closed.
    """
    conn = create_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute_query(conn, query: str, params: tuple = ()):
    """Execute SQL query with parameters.

    Safely executes parameterized query, returns cursor with results.
    Use with SELECT statements to fetch data.
    """
    cursor = conn.cursor()
    cursor.execute(query, params)
    return cursor


class UserRepository:
    """User data access layer with CRUD operations."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def find_user_by_username(self, username: str):
        """Find user by username, return user data."""
        with get_db_transaction(self.db_path) as conn:
            cursor = execute_query(
                conn,
                "SELECT id, username, email FROM users WHERE username = ?",
                (username,)
            )
            return cursor.fetchone()
''')

    # api.py - REST API module
    (codebase_root / "api.py").write_text('''"""
REST API endpoints and routing for web service.

Provides HTTP endpoints for authentication, user management, and data access.
"""

from typing import Any


def handle_login(request_data: dict[str, Any]) -> dict[str, Any]:
    """Handle login POST request.

    Authenticates user credentials, creates session, returns session token.
    Returns 401 error if authentication fails.
    """
    username = request_data.get("username")
    password = request_data.get("password")

    if not username or not password:
        return {"error": "Missing credentials", "status": 400}

    # Call authentication module
    # from auth import authenticate_user, create_session
    # if authenticate_user(username, password):
    #     session_id = create_session(username)
    #     return {"session_id": session_id, "status": 200}

    return {"error": "Invalid credentials", "status": 401}


def handle_get_user(user_id: str) -> dict[str, Any]:
    """Handle GET user endpoint.

    Retrieves user data by ID, returns user profile.
    Returns 404 if user not found.
    """
    # Call database module
    # from database import UserRepository
    # repo = UserRepository("users.db")
    # user = repo.find_user_by_username(user_id)

    return {"user_id": user_id, "status": 200}


def setup_routes(app):
    """Configure API routes.

    Registers all HTTP endpoints with framework router.
    """
    app.route("/login", methods=["POST"])(handle_login)
    app.route("/users/<user_id>", methods=["GET"])(handle_get_user)
''')

    # config.py - Configuration module
    (codebase_root / "config.py").write_text('''"""
Configuration loading and validation module.

Loads settings from environment variables and config files.
"""

import os
from pathlib import Path


def load_config_from_env() -> dict[str, str]:
    """Load configuration from environment variables.

    Reads environment variables for database path, API keys, timeouts.
    Returns configuration dictionary with validated values.
    """
    config = {
        "database_path": os.getenv("DB_PATH", "app.db"),
        "session_timeout": int(os.getenv("SESSION_TIMEOUT", "3600")),
        "debug_mode": os.getenv("DEBUG", "false").lower() == "true",
        "api_host": os.getenv("API_HOST", "0.0.0.0"),
        "api_port": int(os.getenv("API_PORT", "8000")),
    }

    return config


def load_config_from_file(config_path: Path) -> dict[str, str]:
    """Load configuration from YAML or JSON file.

    Parses config file, validates schema, returns configuration dict.
    """
    import json

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open() as f:
        config = json.load(f)

    return config


def validate_config(config: dict[str, str]) -> None:
    """Validate configuration values.

    Checks required fields, validates types, ensures paths exist.
    Raises ValueError if configuration is invalid.
    """
    required = ["database_path", "session_timeout"]

    for key in required:
        if key not in config:
            raise ValueError(f"Missing required config: {key}")

    if config["session_timeout"] <= 0:
        raise ValueError("Session timeout must be positive")
''')

    # utils.py - Utilities module
    (codebase_root / "utils.py").write_text('''"""
Utility functions and helper methods.

Provides string formatting, validation, and common operations.
"""

import hashlib
import re
from typing import Any


def hash_password(password: str, salt: str = "") -> str:
    """Hash password with salt using SHA-256.

    Creates secure password hash for storage in database.
    """
    combined = f"{password}{salt}"
    return hashlib.sha256(combined.encode()).hexdigest()


def validate_email(email: str) -> bool:
    """Validate email address format.

    Checks email against regex pattern, returns True if valid.
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def format_timestamp(timestamp: float) -> str:
    """Format Unix timestamp to human-readable string.

    Converts timestamp to ISO 8601 format string.
    """
    from datetime import datetime
    return datetime.fromtimestamp(timestamp).isoformat()


def sanitize_input(user_input: str) -> str:
    """Sanitize user input to prevent injection attacks.

    Removes dangerous characters, escapes HTML entities.
    """
    # Remove potential SQL injection characters
    dangerous = ["'", '"', ";", "--", "/*", "*/"]
    sanitized = user_input

    for char in dangerous:
        sanitized = sanitized.replace(char, "")

    return sanitized.strip()
''')

    return codebase_root


@pytest.fixture
def real_provider_registry(
    real_embedding_provider: SentenceTransformersEmbeddingProvider,
    real_sparse_provider: SentenceTransformersSparseProvider,
    real_vector_store: MemoryVectorStoreProvider,
    real_reranking_provider: SentenceTransformersRerankingProvider,
) -> None:
    """NO OP - Use real_providers fixture instead."""
    # This fixture is deprecated/removed in favor of real_providers setup
    return


@pytest.fixture
def real_providers(
    real_embedding_provider, real_sparse_provider, real_vector_store, real_reranking_provider
) -> Generator[None, None, None]:
    """Fixture that overrides providers in DI container with REAL providers."""

    from codeweaver.core import get_container
    from codeweaver.providers import (
        EmbeddingProvider,
        RerankingProvider,
        SparseEmbeddingProvider,
        VectorStoreProvider,
    )

    container = get_container()
    container.override(EmbeddingProvider, real_embedding_provider)
    container.override(SparseEmbeddingProvider, real_sparse_provider)
    container.override(VectorStoreProvider, real_vector_store)
    container.override(RerankingProvider, real_reranking_provider)

    call_count = [0]

    def mock_time() -> float:
        call_count[0] += 1
        return 1000000.0 + call_count[0] * 0.001

    with patch("time.time", side_effect=mock_time):
        yield
        container.clear_overrides()


# ===========================================================================
# CodeWeaverState Initialization Fixture
# ===========================================================================


@pytest.fixture
async def initialized_cw_state(
    tmp_path: Path, actual_vector_store, clean_container
) -> AsyncGenerator[Any, None]:
    """Initialize CodeWeaverState for integration tests using DI.

    This fixture ensures CodeWeaverState is properly initialized via the DI
    container, allowing for consistent dependency resolution and overrides.
    """
    # Ensure all dependencies are loaded
    import codeweaver.core.dependencies
    import codeweaver.server.dependencies  # noqa: F401 - ensures @dependency_provider decorators run

    from codeweaver.core.config.settings_type import CodeWeaverSettingsType
    from codeweaver.providers import VectorStoreProvider
    from codeweaver.providers.dependencies.providers import (
        PrimaryVectorStoreProviderDep,
        VectorStoreProvidersDep,
    )
    from codeweaver.server import CodeWeaverState

    # Don't reset container here - clean_container fixture already handles it
    # Force provider loading if not already done
    clean_container._load_providers()

    project_name = f"test_workflow_{tmp_path.name}"

    # Override settings to use in-memory Qdrant and set project_path before DI
    # resolves CodeWeaverState. Without this, bootstrap_settings() constructs
    # ProviderProfile.TESTING which uses path=backup-None (disk-based Qdrant),
    # causing "already accessed" RuntimeError when multiple tests run in parallel,
    # and "Unset.resolve()" AttributeError when project_path is still UNSET.
    async def get_test_settings() -> CodeWeaverSettingsType:
        from codeweaver.core.config.loader import get_settings_async
        from codeweaver.core.types.sentinel import UNSET
        from codeweaver.providers.config.categories.vector_store import (
            MemoryVectorStoreProviderSettings,
        )
        from codeweaver.providers.config.clients.vector_store import QdrantClientOptions
        from codeweaver.providers.config.profiles import ProviderProfile
        from codeweaver.providers.config.providers import ProviderSettings

        settings = await get_settings_async()
        settings.project_path = tmp_path
        settings.project_name = project_name
        if settings.provider is UNSET:
            profile_settings = ProviderProfile.TESTING.as_provider_settings()
            # Replace disk-based Qdrant (backup-None) with in-memory to avoid
            # lock conflicts across parallel tests.
            profile_settings["vector_store"] = (
                MemoryVectorStoreProviderSettings(
                    project_name=project_name,
                    client_options=QdrantClientOptions(location=":memory:"),
                ),
            )
            settings.provider = ProviderSettings.model_construct(**profile_settings)
        return settings

    clean_container.override(CodeWeaverSettingsType, get_test_settings)

    # Also override vector store providers to use the shared actual_vector_store.
    clean_container.override(VectorStoreProvider, actual_vector_store)
    clean_container.override(VectorStoreProvidersDep, (actual_vector_store,))
    clean_container.override(PrimaryVectorStoreProviderDep, actual_vector_store)

    # Resolve and cache settings in _singletons so _global_settings() can find
    # them synchronously (container[T] only checks _singletons, not overrides),
    # preventing _get_canonical_project_path from falling through to loop.to_thread.
    test_settings = await clean_container.resolve(CodeWeaverSettingsType)
    clean_container._singletons[CodeWeaverSettingsType] = test_settings

    # Resolve state via container (this will trigger resolution of all deps including settings)
    state = await clean_container.resolve(CodeWeaverState)

    # Ensure state uses the correct project path (may have been set via settings already)
    if state.settings:
        state.settings.project_path = tmp_path
        state.settings.project_name = project_name
    state.project_path = tmp_path

    # CRITICAL: Set the global state so get_state() works during tests
    from codeweaver.server import server

    server._state = state

    yield state

    # Cleanup: Reset global state and clear overrides
    from codeweaver.server import server

    server._state = None
    clean_container.clear_overrides()


@pytest.fixture
async def indexed_test_project(known_test_codebase, clean_container, actual_vector_store):
    """Create pre-indexed test project with configured settings.

    This fixture:
    1. Configures CodeWeaverSettings with project path
    2. Resolves and initializes the IndexingService via DI
    3. Indexes the test codebase
    4. Ensures global state is correctly initialized
    5. Yields the project path for tests
    """
    import codeweaver.core.dependencies
    import codeweaver.engine.dependencies
    import codeweaver.server.dependencies  # noqa: F401 - ensures @dependency_provider decorators run

    from codeweaver.core.config.loader import get_settings_async
    from codeweaver.core.config.settings_type import CodeWeaverSettingsType
    from codeweaver.engine import IndexingService
    from codeweaver.server import CodeWeaverState

    # Ensure known_test_codebase is absolute
    project_path = known_test_codebase.resolve()

    # Define a factory that returns settings with the test project path
    async def get_test_settings() -> CodeWeaverSettingsType:
        from codeweaver.core.types.sentinel import UNSET
        from codeweaver.providers.config.categories.vector_store import (
            MemoryVectorStoreProviderSettings,
        )
        from codeweaver.providers.config.profiles import ProviderProfile
        from codeweaver.providers.config.providers import ProviderSettings

        # codeweaver.test.toml is already loaded via CODEWEAVER_TEST_MODE="true"
        settings = await get_settings_async()
        settings.project_path = project_path
        settings.project_name = f"test_real_{project_path.name}"
        # get_settings_async() uses CodeWeaverSettings(**kwargs) which never calls
        # _initialize(), leaving provider=UNSET. Set it explicitly so downstream
        # DI factories (_get_provider_settings) don't fail.
        if settings.provider is UNSET:
            profile_settings = ProviderProfile.TESTING.as_provider_settings()
            # Replace disk-based Qdrant with in-memory to avoid cross-test lock conflicts.
            # The TESTING profile uses path=backup-None which causes RuntimeError when
            # multiple tests compete for the same Qdrant storage folder.
            from codeweaver.providers.config.clients.vector_store import QdrantClientOptions

            profile_settings["vector_store"] = (
                MemoryVectorStoreProviderSettings(
                    project_name=f"test_real_{project_path.name}",
                    client_options=QdrantClientOptions(location=":memory:"),
                ),
            )
            settings.provider = ProviderSettings.model_construct(**profile_settings)
        # get_settings() returns BaseCodeWeaverSettings, but in test mode it's actually CodeWeaverSettings
        return settings

    # Apply overrides to container
    clean_container.override(CodeWeaverSettingsType, get_test_settings)

    # Override vector store providers to use the shared actual_vector_store.
    # Without this, _create_vector_store_providers() creates a new in-memory
    # Qdrant instance from settings (separate from actual_vector_store), so
    # indexed data is invisible to the search path which uses actual_vector_store.
    from codeweaver.providers import VectorStoreProvider
    from codeweaver.providers.dependencies.providers import (
        PrimaryVectorStoreProviderDep,
        VectorStoreProvidersDep,
    )

    clean_container.override(VectorStoreProvider, actual_vector_store)
    clean_container.override(VectorStoreProvidersDep, (actual_vector_store,))
    clean_container.override(PrimaryVectorStoreProviderDep, actual_vector_store)

    # Resolve settings and store in _singletons for sync access via _global_settings()
    # (container[T] only checks _singletons, not overrides)
    test_settings = await clean_container.resolve(CodeWeaverSettingsType)
    clean_container._singletons[CodeWeaverSettingsType] = test_settings

    # Resolve state via container to ensure it's initialized with correct settings
    state = await clean_container.resolve(CodeWeaverState)

    # CRITICAL: Set the global state so get_state() works during tests
    from codeweaver.server import server

    server._state = state

    # Patch time for deterministic behavior if needed
    call_count = [0]

    def mock_time() -> float:
        call_count[0] += 1
        return 1000000.0 + call_count[0] * 0.001

    with patch("time.time", side_effect=mock_time):
        # Resolve indexer from container
        indexer = await clean_container.resolve(IndexingService)

        # Ensure it's using the correct project path
        indexer._project_path = project_path

        await indexer.index_project(force_reindex=True)

        yield project_path

    # Cleanup: Reset global state
    from codeweaver.server import server

    server._state = None
