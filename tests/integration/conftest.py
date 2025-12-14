# sourcery skip: docstrings-for-classes
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Integration test fixtures for provider configuration."""

from __future__ import annotations

import contextlib
import os

from collections.abc import AsyncGenerator, Generator
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codeweaver.common.registry.provider import ProviderRegistry
from codeweaver.providers.embedding.providers.fastembed import FastEmbedEmbeddingProvider
from codeweaver.providers.vector_stores.inmemory import MemoryVectorStoreProvider


if TYPE_CHECKING:
    from codeweaver.config.providers import (
        EmbeddingProviderSettings,
        RerankingProviderSettings,
        SparseEmbeddingProviderSettings,
    )
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.core.chunks import CodeChunk
    from codeweaver.core.types.dictview import DictView
    from codeweaver.providers.embedding.capabilities.base import (
        EmbeddingModelCapabilities,
        SparseEmbeddingModelCapabilities,
    )
    from codeweaver.providers.embedding.providers.fastembed import (
        FastEmbedEmbeddingProvider,
        FastEmbedSparseProvider,
    )
    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersEmbeddingProvider,
        SentenceTransformersSparseProvider,
    )
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
    from codeweaver.providers.reranking.providers.fastembed import FastEmbedRerankingProvider
    from codeweaver.providers.reranking.providers.sentence_transformers import (
        SentenceTransformersRerankingProvider,
    )

# ===========================================================================
# CLI Mock Fixtures
# ===========================================================================

os.environ["CODEWEAVER_TEST_MODE"] = "true"

# Disable SSL verification warnings for tests (WSL time sync issues cause false positives)
import warnings

from urllib3.exceptions import SystemTimeWarning


warnings.filterwarnings("ignore", category=SystemTimeWarning)


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
    from codeweaver.config.settings import get_settings_map

    # Just return the settings map - config system already loaded codeweaver.test.toml
    # because CODEWEAVER_TEST_MODE="true" (set at top of this file)
    return get_settings_map()


_settings: DictView[CodeWeaverSettingsDict] = _set_settings()

HAS_SENTENCE_TRANSFORMERS = find_spec("sentence_transformers") is not None
HAS_FASTEMBED = find_spec("fastembed") is not None


def _get_configs(
    *, sparse: bool = False, rerank: bool = False
) -> EmbeddingProviderSettings | SparseEmbeddingProviderSettings | RerankingProviderSettings:
    """Get the model name for testing based on available libraries."""
    from codeweaver.config.profiles import get_profile

    profile = get_profile("backup", vector_deployment="local")
    if rerank:
        # reranking is a tuple with one element
        return profile["reranking"][0]  # ty:ignore[non-subscriptable,invalid-key]
    # the profile returns single values for each setting -- so while it can be a tuple, it isn't.
    return profile["sparse_embedding"] if sparse else profile["embedding"]  # ty:ignore[invalid-key,invalid-return-type]


@pytest.fixture
def mock_confirm(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock rich.prompt.Confirm for CLI tests.

    Returns a mock Confirm object that automatically returns True for all confirmations.
    Tests can override by setting mock_confirm.ask.return_value to False.

    Patches module-level imports of Confirm to avoid stdin access issues during testing
    when pytest captures output. Only patches locations where Confirm is imported at
    module level, not inside functions.
    """
    mock = MagicMock()
    mock.ask.return_value = True

    # Patch the module-level import in init.py (imported at line 27)
    monkeypatch.setattr("codeweaver.cli.commands.init.Confirm", mock)
    # Also patch the base location to catch any other imports
    monkeypatch.setattr("rich.prompt.Confirm", mock)

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
    EmbeddingModelCapabilities, SparseEmbeddingModelCapabilities, RerankingModelCapabilities
]:
    from codeweaver.common.registry.models import get_model_registry

    model_registry = get_model_registry()
    settings = (_get_configs(), _get_configs(sparse=True), _get_configs(rerank=True))
    return (
        model_registry.get_embedding_capabilities(
            settings[0]["provider"], settings[0]["model_settings"]["model"]
        )[0],  # ty:ignore[non-subscriptable]
        model_registry.get_sparse_embedding_capabilities(
            settings[1]["provider"], settings[1]["model_settings"]["model"]
        )[0],  # ty:ignore[non-subscriptable]
        model_registry.get_reranking_capabilities(
            settings[2]["provider"], settings[2]["model_settings"]["model"]
        )[0],  # ty:ignore[non-subscriptable]
    )


@pytest.fixture
def actual_dense_embedding_provider() -> (
    SentenceTransformersEmbeddingProvider | FastEmbedEmbeddingProvider
):
    """Provide an actual dense embedding provider using SentenceTransformers."""
    caps, _, _ = _get_caps()
    from codeweaver.common.registry.provider import get_provider_registry

    registry = get_provider_registry()
    # Registry will get capabilities from the configured "testing" profile settings
    return registry.get_provider_instance(caps.provider, "embedding", singleton=True)  # type: ignore


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
def actual_sparse_embedding_provider() -> (
    SentenceTransformersSparseProvider | FastEmbedSparseProvider
):
    """Provide an actual sparse embedding provider using SentenceTransformers."""
    _, caps, _ = _get_caps()
    from codeweaver.common.registry.provider import get_provider_registry

    registry = get_provider_registry()
    # Pass caps explicitly so registry doesn't need to look them up from global settings
    return registry.get_provider_instance(
        caps.provider, "sparse_embedding", singleton=True, caps=caps
    )  # type: ignore


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Provide a mock vector store that returns search results."""
    from codeweaver.agent_api.find_code.results import SearchResult
    from codeweaver.common.utils.utils import uuid7
    from codeweaver.core.chunks import CodeChunk
    from codeweaver.core.language import SemanticSearchLanguage
    from codeweaver.core.metadata import ChunkKind, ExtKind
    from codeweaver.core.spans import Span

    mock_store = AsyncMock()

    # Create test chunks for search results
    def create_test_chunk(name: str, content: str, file_path: Path) -> CodeChunk:
        chunk_id = uuid7()
        return CodeChunk(
            chunk_id=chunk_id,
            ext_kind=ExtKind.from_language(SemanticSearchLanguage.PYTHON, ChunkKind.CODE),
            chunk_name=name,
            file_path=file_path,
            language=SemanticSearchLanguage.PYTHON,
            content=content,
            line_range=Span(start=1, end=10, _source_id=chunk_id),
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


@pytest.fixture
def actual_vector_store() -> MemoryVectorStoreProvider:
    """Provide an actual in-memory vector store provider.

    Creates the instance directly without going through registry to avoid
    registry caching issues in tests. This ensures we get a fresh instance
    that can be properly initialized and controlled by the test.
    """
    from codeweaver.providers.provider import Provider
    from codeweaver.providers.vector_stores.inmemory import MemoryVectorStoreProvider

    # Create instance directly, not through registry
    # This avoids the real registry's singleton cache
    return MemoryVectorStoreProvider(_provider=Provider.MEMORY)


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
def actual_reranking_provider() -> (
    SentenceTransformersRerankingProvider | FastEmbedRerankingProvider
):
    """Provide an actual reranking provider using SentenceTransformers."""
    _, _, caps = _get_caps()
    from codeweaver.common.registry.provider import get_provider_registry

    registry = get_provider_registry()
    # Pass caps explicitly so registry doesn't need to look them up from global settings
    return registry.get_provider_instance(caps.provider, "reranking", singleton=True, caps=caps)  # type: ignore


# ===========================================================================
# Provider Registry Configuration Fixtures
# ===========================================================================


@pytest.fixture
def mock_provider_registry(
    mock_embedding_provider: MagicMock,
    mock_sparse_provider: MagicMock,
    mock_vector_store: MagicMock,
    mock_reranking_provider: MagicMock,
) -> MagicMock:
    """Configure mock provider registry with all providers."""
    from enum import Enum

    class MockProviderEnum(Enum):
        VOYAGE = "voyage"
        FASTEMBED = "fastembed"
        QDRANT = "qdrant"

    mock_registry = MagicMock()

    # Configure get_provider_enum_for to return mock provider enums
    def get_provider_enum_for(kind: str) -> MockProviderEnum | None:
        if kind == "embedding":
            return MockProviderEnum.VOYAGE
        if kind == "sparse_embedding":
            return MockProviderEnum.FASTEMBED
        if kind == "vector_store":
            return MockProviderEnum.QDRANT
        return MockProviderEnum.VOYAGE if kind == "reranking" else None

    mock_registry.get_provider_enum_for = MagicMock(side_effect=get_provider_enum_for)

    # Configure get_provider_instance to return mock providers
    def get_provider_instance(
        enum_value: MockProviderEnum, kind: str, singleton: bool = True
    ) -> AsyncMock | None:
        if kind == "embedding":
            return mock_embedding_provider
        if kind == "sparse_embedding":
            return mock_sparse_provider
        if kind == "vector_store":
            return mock_vector_store
        return mock_reranking_provider if kind == "reranking" else None

    mock_registry.get_provider_instance = MagicMock(side_effect=get_provider_instance)

    return mock_registry


@pytest.fixture
def configured_providers(mock_provider_registry: MagicMock) -> Generator[MagicMock, None, None]:
    """Fixture that patches the provider registry with mock providers.

    This fixture automatically configures the provider registry for tests
    that need embedding, vector store, and reranking providers.

    Usage:
        @pytest.mark.asyncio
        async def test_something(configured_providers):
            # find_code and other functions will use mock providers
            response = await find_code("test query")
    """
    # Patch both the provider registry and time.time to ensure monotonic timing

    call_count = [0]  # Use list for mutable counter

    def mock_time() -> float:
        call_count[0] += 1
        # Return monotonically increasing time values (start from a baseline)
        return 1000000.0 + call_count[0] * 0.001

    with (
        patch(
            "codeweaver.common.registry.get_provider_registry", return_value=mock_provider_registry
        ),
        patch("codeweaver.agent_api.find_code.time.time", side_effect=mock_time),
    ):
        yield mock_provider_registry


# ===========================================================================
# Settings Fixtures
# ===========================================================================


@pytest.fixture
def mock_settings_with_providers() -> MagicMock:
    """Provide mock settings with provider configuration."""
    from codeweaver.config.settings import CodeWeaverSettings as Settings

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
    from codeweaver.common.utils.utils import generate_collection_name

    instance: MemoryVectorStoreProvider = actual_vector_store

    # CRITICAL FIX: Generate collection name from known_test_codebase (test project path), not codeweaver project path
    # This ensures indexer and search use the same collection name for test isolation
    # known_test_codebase = tmp_path / "test_codebase", matching the path used by indexed_test_project
    collection_name = generate_collection_name(project_path=known_test_codebase)

    # Explicitly set collection name in config to override any global settings
    if not instance.config:
        instance.config = {}
    instance.config["collection_name"] = collection_name

    # Initialize before accessing client
    await instance._initialize()
    client = instance.client

    yield instance

    # Cleanup: Delete collection after test
    with contextlib.suppress(Exception):
        await client.delete_collection(collection_name)


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
) -> MagicMock:
    """Configure provider registry with REAL providers for behavior validation.

    This fixture creates a complete provider ecosystem using actual implementations:
    - Real embedding generation (SentenceTransformers)
    - Real or mock sparse embeddings (depending on SparseEncoder availability)
    - Real vector storage (Qdrant in-memory)
    - Real reranking (MS MARCO)

    Tests using this fixture validate actual search behavior, not just structure.

    Use for tests marked with @pytest.mark.real_providers.

    **Note on Sparse Encoding:**
    If SparseEncoder is unavailable, uses mock sparse provider. This is expected
    for Alpha 1 and allows dense-only search validation.
    """
    from enum import Enum
    from unittest.mock import MagicMock

    class RealProviderEnum(Enum):
        SENTENCE_TRANSFORMERS = "sentence_transformers"
        OPENAI = "openai"
        FASTEMBED = "fastembed"
        MEMORY = "memory"

    mock_registry = MagicMock()

    # Configure get_provider_enum_for to return real provider enums
    def get_provider_enum_for(kind: str) -> RealProviderEnum | None:
        if kind == "vector_store":
            return RealProviderEnum.MEMORY
        # For testing/backup profile, prefer SentenceTransformers with lightweight models
        # (minishlab/potion-base-8M is 256 dims vs BAAI/bge-small-en-v1.5 at 384 dims)
        return (
            RealProviderEnum.SENTENCE_TRANSFORMERS
            if HAS_SENTENCE_TRANSFORMERS
            else RealProviderEnum.FASTEMBED
        )

    mock_registry.get_provider_enum_for = MagicMock(side_effect=get_provider_enum_for)

    # Configure get_provider_instance to return real providers
    def get_provider_instance(
        enum_value: RealProviderEnum, kind: str, singleton: bool = True
    ) -> Any | MagicMock:
        if kind == "embedding":
            return real_embedding_provider
        if kind == "sparse_embedding":
            return real_sparse_provider
        if kind == "vector_store":
            return real_vector_store
        return real_reranking_provider if kind == "reranking" else None

    mock_registry.get_provider_instance = MagicMock(side_effect=get_provider_instance)

    return mock_registry


@pytest.fixture
def real_providers(real_provider_registry: MagicMock) -> Generator[ProviderRegistry, None, None]:
    """Fixture that patches the provider registry with REAL providers.

    This is the main fixture for Tier 2 tests. It provides actual provider
    implementations that generate real embeddings, store real vectors, and
    perform real search operations.

    **When to use this vs configured_providers:**

    - Use `configured_providers` (Tier 1) for:
      * Structure validation tests
      * Error path testing
      * Fast feedback loops
      * Response format verification

    - Use `real_providers` (Tier 2) for:
      * Search quality validation
      * End-to-end pipeline testing
      * Performance benchmarking
      * Behavior validation

    **Example usage:**

    ```python
    @pytest.mark.integration
    @pytest.mark.real_providers
    async def test_search_finds_auth_code(real_providers, known_test_codebase):
        # This test validates actual search behavior
        response = await find_code("authentication logic")

        # Should actually find auth.py in top results
        assert any("auth.py" in r.file_path for r in response.results[:3])
    ```

    **Performance note:** These tests are slower (~2-10s each) because they:
    - Generate real embeddings (CPU/GPU intensive)
    - Perform real vector similarity search
    - Run actual reranking models

    Mark tests with @pytest.mark.slow if they take >5s.
    """
    call_count = [0]

    def mock_time() -> float:
        call_count[0] += 1
        return 1000000.0 + call_count[0] * 0.001

    with (
        patch(
            "codeweaver.common.registry.get_provider_registry", return_value=real_provider_registry
        ),
        patch("codeweaver.agent_api.find_code.time.time", side_effect=mock_time),
    ):
        yield real_provider_registry


# ===========================================================================
# CodeWeaverState Initialization Fixture
# ===========================================================================


@pytest.fixture
def initialized_cw_state(tmp_path: Path) -> Generator[Any, None, None]:
    """Initialize CodeWeaverState for integration tests that call find_code_tool.

    This fixture ensures CodeWeaverState is properly initialized before tests that
    call find_code_tool, which requires CodeWeaverState.get_state() to succeed.

    The fixture creates a minimal CodeWeaverState with:
    - Settings initialized
    - Registries initialized (provider, services, model)
    - Statistics tracking
    - No failover manager (optional for basic tests)

    Usage:
        @pytest.mark.asyncio
        async def test_something(initialized_cw_state):
            # find_code_tool will work now
            response = await find_code_tool("test query", ...)
    """
    from codeweaver.common.registry import (
        get_model_registry,
        get_provider_registry,
        get_services_registry,
    )
    from codeweaver.common.statistics import get_session_statistics
    from codeweaver.common.telemetry.client import PostHogClient
    from codeweaver.config.settings import get_settings
    from codeweaver.server.server import CodeWeaverState

    # Initialize settings
    settings = get_settings()
    yield CodeWeaverState(
        initialized=True,
        settings=settings,
        project_path=tmp_path,
        config_path=None,
        provider_registry=get_provider_registry(),
        services_registry=get_services_registry(),
        model_registry=get_model_registry(),
        statistics=get_session_statistics(),
        middleware_stack=(),
        indexer=None,
        health_service=None,
        failover_manager=None,
        telemetry=PostHogClient.from_settings(),
    )
    # Cleanup: Reset global state
    from codeweaver.server import server

    server._state = None
