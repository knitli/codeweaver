# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Integration test fixtures for provider configuration."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


if TYPE_CHECKING:
    from codeweaver.core.chunks import CodeChunk
    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersEmbeddingProvider,
        SentenceTransformersRerankingProvider,
        SentenceTransformersSparseProvider,
    )

# ===========================================================================
# Mock Provider Fixtures
# ===========================================================================


@pytest.fixture
def mock_embedding_provider():
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


@pytest.fixture
def actual_dense_embedding_provider() -> SentenceTransformersEmbeddingProvider:
    """Provide an actual dense embedding provider using SentenceTransformers."""
    from sentence_transformers import SentenceTransformer

    from codeweaver.providers.embedding.capabilities.ibm_granite import (
        get_ibm_granite_embedding_capabilities,
    )
    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersEmbeddingProvider,
    )

    # nice lightweight model
    caps = next(
        cap
        for cap in get_ibm_granite_embedding_capabilities()
        if cap.name == "ibm-granite/granite-embedding-english-r2"
    )
    return SentenceTransformersEmbeddingProvider(
        capabilities=caps, client=SentenceTransformer(caps.name)
    )


@pytest.fixture
def mock_sparse_provider():
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
def actual_sparse_embedding_provider() -> SentenceTransformersSparseProvider:
    """Provide an actual sparse embedding provider using SentenceTransformers."""
    from sentence_transformers import SparseEncoder

    from codeweaver.providers.embedding.capabilities.base import get_sparse_caps
    from codeweaver.providers.embedding.providers.sentence_transformers import (
        SentenceTransformersSparseProvider,
    )

    cap = next(
        cap
        for cap in get_sparse_caps()
        if cap.name == "opensearch-project/opensearch-neural-sparse-encoding-doc-v2-mini"
    )
    return SentenceTransformersSparseProvider(capabilities=cap, client=SparseEncoder(cap.name))


@pytest.fixture
def mock_vector_store():
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
def mock_reranking_provider():
    """Provide a mock reranking provider."""
    from typing import NamedTuple

    # Define a simple RerankResult structure for testing
    class RerankResult(NamedTuple):
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
def actual_reranking_provider() -> SentenceTransformersRerankingProvider:
    """Provide an actual reranking provider using SentenceTransformers."""
    from fastembed import TextEmbedding

    from codeweaver.providers.reranking.capabilities.ms_marco import (
        get_marco_reranking_capabilities,
    )

    # nice lightweight model
    caps = next(
        cap
        for cap in get_marco_reranking_capabilities()
        if cap.name == "Xenova/ms-marco-MiniLM-L6-v2"
    )
    return SentenceTransformersRerankingProvider(capabilities=caps, client=TextEmbedding(caps.name))


# ===========================================================================
# Provider Registry Configuration Fixtures
# ===========================================================================


@pytest.fixture
def mock_provider_registry(
    mock_embedding_provider, mock_sparse_provider, mock_vector_store, mock_reranking_provider
):
    """Configure mock provider registry with all providers."""
    from enum import Enum

    # Create simple mock enums for providers
    class MockProviderEnum(Enum):
        VOYAGE = "voyage"
        FASTEMBED = "fastembed"
        QDRANT = "qdrant"

    mock_registry = MagicMock()

    # Configure get_provider_enum_for to return mock provider enums
    def get_provider_enum_for(kind: str):
        if kind == "embedding":
            return MockProviderEnum.VOYAGE
        if kind == "sparse_embedding":
            return MockProviderEnum.FASTEMBED
        if kind == "vector_store":
            return MockProviderEnum.QDRANT
        if kind == "reranking":
            return MockProviderEnum.VOYAGE
        return None

    mock_registry.get_provider_enum_for = MagicMock(side_effect=get_provider_enum_for)

    # Configure get_provider_instance to return mock providers
    def get_provider_instance(enum_value, kind: str, singleton: bool = True):
        if kind == "embedding":
            return mock_embedding_provider
        if kind == "sparse_embedding":
            return mock_sparse_provider
        if kind == "vector_store":
            return mock_vector_store
        if kind == "reranking":
            return mock_reranking_provider
        return None

    mock_registry.get_provider_instance = MagicMock(side_effect=get_provider_instance)

    return mock_registry


@pytest.fixture
def configured_providers(mock_provider_registry):
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
def mock_settings_with_providers():
    """Provide mock settings with provider configuration."""
    from codeweaver.config.settings import CodeWeaverSettings as Settings

    mock_settings = MagicMock(spec=Settings)
    mock_settings.providers = {
        "embedding": {"provider": "voyage", "model": "voyage-code-2"},
        "sparse_embedding": {"provider": "fastembed", "model": "prithivida/Splade_PP_en_v1"},
        "vector_store": {"provider": "qdrant", "collection": "test_collection"},
        "reranking": {"provider": "voyage", "model": "voyage-rerank-2"},
    }
    return mock_settings


# ===========================================================================
# Real Provider Fixtures (Tier 2: Actual Behavior Validation)
# ===========================================================================


@pytest.fixture
def real_embedding_provider(
    actual_dense_embedding_provider,
) -> SentenceTransformersEmbeddingProvider:
    """Provide a REAL embedding provider for behavior validation.

    Uses the existing actual_dense_embedding_provider fixture which is already
    working and tested. This avoids duplicating provider initialization logic.

    Model: IBM Granite English R2 - lightweight, fast, good quality
    No API key required - runs entirely locally.

    Use this fixture for tests marked with @pytest.mark.real_providers.

    Note: This fixture found a production bug! The SentenceTransformersEmbeddingProvider
    has a Pydantic initialization issue where it sets instance attributes before
    calling super().__init__(). The actual_dense_embedding_provider works around this.
    """
    return actual_dense_embedding_provider


@pytest.fixture
def real_sparse_provider(actual_sparse_embedding_provider) -> SentenceTransformersSparseProvider:
    """Provide a REAL sparse embedding provider for hybrid search validation.

    Uses the existing actual_sparse_embedding_provider fixture.

    Model: OpenSearch neural sparse encoding - lightweight and effective
    No API key required - runs entirely locally.
    """
    return actual_sparse_embedding_provider


@pytest.fixture
def real_reranking_provider(actual_reranking_provider) -> SentenceTransformersRerankingProvider:
    """Provide a REAL reranking provider for relevance scoring validation.

    Uses the existing actual_reranking_provider fixture.

    Model: MS MARCO MiniLM - lightweight cross-encoder for reranking
    No API key required - runs entirely locally.
    """
    return actual_reranking_provider


@pytest.fixture
async def real_vector_store(tmp_path: Path):
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
    from qdrant_client import AsyncQdrantClient

    from codeweaver.config.providers import MemoryConfig
    from codeweaver.providers.vector_stores.inmemory import MemoryVectorStoreProvider

    # Create in-memory Qdrant client
    client = AsyncQdrantClient(location=":memory:")

    # Create config for the vector store
    config = MemoryConfig(
        persist_directory=str(tmp_path / "vector_store"), collection_name="test_real_collection"
    )

    # Create the vector store provider
    provider = MemoryVectorStoreProvider(client=client, config=config)

    # Initialize (creates collection if needed)
    await provider._initialize()

    yield provider

    # Cleanup: Delete collection after test
    try:
        await client.delete_collection(config.collection_name)
    except Exception:
        pass  # Already deleted or doesn't exist


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
    real_embedding_provider, real_sparse_provider, real_vector_store, real_reranking_provider
):
    """Configure provider registry with REAL providers for behavior validation.

    This fixture creates a complete provider ecosystem using actual implementations:
    - Real embedding generation (SentenceTransformers)
    - Real sparse embeddings (OpenSearch)
    - Real vector storage (Qdrant in-memory)
    - Real reranking (MS MARCO)

    Tests using this fixture validate actual search behavior, not just structure.

    Use for tests marked with @pytest.mark.real_providers.
    """
    from enum import Enum
    from unittest.mock import MagicMock

    # Create simple mock enums for providers
    class RealProviderEnum(Enum):
        SENTENCE_TRANSFORMERS = "sentence_transformers"
        OPENSEARCH = "opensearch"
        QDRANT_MEMORY = "qdrant_memory"
        MS_MARCO = "ms_marco"

    mock_registry = MagicMock()

    # Configure get_provider_enum_for to return real provider enums
    def get_provider_enum_for(kind: str):
        if kind == "embedding":
            return RealProviderEnum.SENTENCE_TRANSFORMERS
        if kind == "sparse_embedding":
            return RealProviderEnum.OPENSEARCH
        if kind == "vector_store":
            return RealProviderEnum.QDRANT_MEMORY
        if kind == "reranking":
            return RealProviderEnum.MS_MARCO
        return None

    mock_registry.get_provider_enum_for = MagicMock(side_effect=get_provider_enum_for)

    # Configure get_provider_instance to return real providers
    def get_provider_instance(enum_value, kind: str, singleton: bool = True):
        if kind == "embedding":
            return real_embedding_provider
        if kind == "sparse_embedding":
            return real_sparse_provider
        if kind == "vector_store":
            return real_vector_store
        if kind == "reranking":
            return real_reranking_provider
        return None

    mock_registry.get_provider_instance = MagicMock(side_effect=get_provider_instance)

    return mock_registry


@pytest.fixture
def real_providers(real_provider_registry):
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
