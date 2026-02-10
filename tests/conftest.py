# sourcery skip: no-relative-imports
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# sourcery skip: require-parameter-annotation
"""Global pytest configuration and fixtures for CodeWeaver tests."""

import contextlib

from collections.abc import Generator, Sequence
from pathlib import Path
from types import AsyncGeneratorType
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from pydantic.types import UUID7
from qdrant_client import AsyncQdrantClient

from codeweaver.core import ChunkKind, CodeChunk, ConfigLanguage, ExtKind, SemanticSearchLanguage
from codeweaver.core.dependencies import SettingsDep
from codeweaver.core.di.depends import INJECTED

from .qdrant_test_manager import QdrantTestManager


if TYPE_CHECKING:
    from codeweaver.core.dependencies.core_settings import CodeWeaverSettingsType
    from codeweaver.core.di.container import Container

# ===========================================================================
# *                    Mock Tokenizer for Network-Isolated Tests
# ===========================================================================

# Token estimation constant: average characters per token for general text
CHARS_PER_TOKEN = 4


class MockTokenizer:
    """Mock tokenizer that doesn't require network access.

    This avoids tiktoken's need to download encoding files from the network.
    Uses a simple character-based estimation (1 token per CHARS_PER_TOKEN characters).
    """

    def __init__(self, model: str = "mock") -> None:
        self.encoder_name = model

    def encode(self, text: str | bytes, **kwargs: Any) -> Sequence[int]:
        """Mock encode - returns list of integers based on character positions."""
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="ignore")
        return list(range(len(text) // CHARS_PER_TOKEN + 1))

    def encode_batch(
        self, texts: Sequence[str] | Sequence[bytes], **kwargs: Any
    ) -> Sequence[Sequence[int]]:
        """Mock batch encode."""
        return [self.encode(text) for text in texts]

    def decode(self, tokens: Sequence[int], **kwargs: Any) -> str:
        """Mock decode - returns placeholder string."""
        return f"decoded_{len(tokens)}_tokens"

    def decode_batch(self, token_lists: Sequence[Sequence[int]], **kwargs: Any) -> Sequence[str]:
        """Mock batch decode."""
        return [self.decode(tokens) for tokens in token_lists]

    def estimate(self, text: str | bytes) -> int:
        """Estimate token count using simple character ratio."""
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="ignore")
        return max(1, len(text) // CHARS_PER_TOKEN)

    def estimate_batch(self, texts: Sequence[str] | Sequence[bytes]) -> int:
        """Estimate total tokens for a batch."""
        return sum(self.estimate(text) for text in texts)

    @staticmethod
    def encoders() -> Sequence[str]:
        """List mock encoder names."""
        return ["mock", "o200k_base", "gpt2"]


def _mock_get_tokenizer(tokenizer: str, model: str) -> MockTokenizer:
    """Mock replacement for codeweaver_tokenizers.get_tokenizer."""
    return MockTokenizer(model)


# ===========================================================================
# *                    Test Configuration
# ===========================================================================
# Note: Qdrant configuration now handled by qdrant_test_manager fixture
# See tests/qdrant_test_manager.py for details

# ===========================================================================
# *                    Mock Provider Fixtures
# ===========================================================================


@pytest.fixture
def mock_embedding_provider() -> AsyncMock:
    """Provide a mock embedding provider that returns test embeddings."""
    mock_provider = AsyncMock()
    mock_provider.model_name = "mock-dense-model"
    mock_provider.provider_name = "mock-provider"
    mock_provider.embed_query = AsyncMock(return_value=[[0.1] * 384])
    mock_provider.embed_documents = AsyncMock(return_value=[[0.1] * 384, [0.2] * 384])
    mock_provider.initialize_async = AsyncMock()
    return mock_provider


@pytest.fixture
def mock_sparse_provider() -> AsyncMock:
    """Provide a mock sparse embedding provider."""
    mock_provider = AsyncMock()
    mock_provider.model_name = "mock-sparse-model"
    mock_provider.provider_name = "mock-sparse-provider"
    mock_provider.embed_query = AsyncMock(
        return_value=[{"indices": [1, 2, 3], "values": [0.1, 0.2, 0.3]}]
    )
    mock_provider.embed_documents = AsyncMock(
        return_value=[
            {"indices": [1, 2, 3], "values": [0.1, 0.2, 0.3]},
            {"indices": [4, 5, 6], "values": [0.4, 0.5, 0.6]},
        ]
    )
    mock_provider.initialize_async = AsyncMock()
    return mock_provider


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    """Provide a mock vector store provider."""
    mock_store = AsyncMock()
    mock_store.collection = "mock_collection"
    mock_store.client = MagicMock()
    mock_store.client.retrieve = AsyncMock(return_value=[])
    mock_store.client.scroll = AsyncMock(return_value=([], None))
    mock_store.client.update_vectors = AsyncMock()
    mock_store.initialize = AsyncMock()
    mock_store._initialize = AsyncMock()
    mock_store.upsert = AsyncMock()
    mock_store.search = AsyncMock(return_value=[])
    mock_store.delete_by_file = AsyncMock()
    return mock_store


@pytest.fixture
def mock_reranking_provider() -> AsyncMock:
    """Provide a mock reranking provider."""
    mock_provider = AsyncMock()
    mock_provider.rerank = AsyncMock(return_value=[])
    return mock_provider


@pytest.fixture
def di_overrides(
    clean_container,
    mock_embedding_provider,
    mock_sparse_provider,
    mock_vector_store,
    mock_reranking_provider,
) -> Any:
    """Apply standard mock overrides to the DI container.

    This fixture applies mock providers to the DI container, ensuring that
    components resolved via DI use these mocks instead of real providers.
    """
    from codeweaver.providers import (
        EmbeddingProvider,
        RerankingProvider,
        SparseEmbeddingProvider,
        VectorStoreProvider,
    )

    clean_container.override(EmbeddingProvider, mock_embedding_provider)
    clean_container.override(SparseEmbeddingProvider, mock_sparse_provider)
    clean_container.override(VectorStoreProvider, mock_vector_store)
    clean_container.override(RerankingProvider, mock_reranking_provider)

    return clean_container


# ===========================================================================
# *                    Fixtures
# ===========================================================================


@pytest.fixture(autouse=True)
def mock_tokenizer_for_unit_tests(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auto-patch the tokenizer for unit tests that are marked as mock_only.

    This prevents network calls to download tiktoken encodings during unit tests.
    Only applies to tests marked with @pytest.mark.mock_only or @pytest.mark.unit.
    """
    # Check if test is marked as mock_only or unit
    markers = [marker.name for marker in request.node.iter_markers()]
    should_mock = "mock_only" in markers or ("unit" in markers and "network" not in markers)

    if should_mock:
        # Patch get_tokenizer to return our mock in all modules that use it
        modules_to_patch = [
            "codeweaver_tokenizers.get_tokenizer",
            "codeweaver.providers",
            "codeweaver.providers",
            "codeweaver.providers",
        ]
        for module_path in modules_to_patch:
            with contextlib.suppress(AttributeError):
                monkeypatch.setattr(module_path, _mock_get_tokenizer)


@pytest.fixture
def initialize_test_settings() -> Generator[None, None, None]:
    """Initialize settings for test environment.

    This fixture ensures that the global settings are properly initialized
    with minimal required configuration for tests. It resets settings after
    the test to avoid cross-test contamination.
    """
    from codeweaver.core.config.loader import get_settings
    from codeweaver.core.di import reset_container

    # Reset container to force fresh settings
    reset_container()

    # Initialize settings by calling get_settings() which will create
    # the global instance with defaults, including the "providers" key
    # This prevents KeyError when tests access provider settings
    get_settings()

    yield

    # Cleanup: reset container after test
    reset_container()


@pytest.fixture
async def qdrant_client_cleanup() -> AsyncGeneratorType:
    """Fixture that provides a cleanup function for Qdrant collections.

    Yields a cleanup function that can be called with (client, collection_name).
    Automatically cleans up at test end if not called explicitly.
    """
    collections_to_cleanup = []

    async def cleanup(client: AsyncQdrantClient, collection_name: str) -> None:
        """Clean up a Qdrant collection."""
        if collection_name:
            collections_to_cleanup.append((client, collection_name))

    yield cleanup

    # Cleanup all collections at test end
    for client, collection_name in collections_to_cleanup:
        with contextlib.suppress(Exception):
            await client.delete_collection(collection_name=collection_name)


@pytest.fixture
def temp_test_file(tmp_path: Path) -> Path:
    """Create a temporary test file."""
    test_file = tmp_path / "test_code.py"
    test_file.write_text("def test_function():\n    pass\n")
    return test_file


@pytest.fixture(autouse=True)
def clear_collection_name_cache() -> Generator[None, None, None]:
    """Clear all class-level deduplication stores before each test.

    This prevents test interference where chunks or embeddings from one test are
    marked as duplicates in subsequent tests.
    """
    from codeweaver.core import generate_collection_name

    generate_collection_name.cache_clear()
    yield
    # Clear again after test for extra safety
    generate_collection_name.cache_clear()


# ===========================================================================
# *                    Qdrant Test Instance Management
# ===========================================================================


@pytest.fixture
async def qdrant_test_manager(tmp_path: Path) -> AsyncGeneratorType:
    """Provide a QdrantTestManager for integration tests.

    This fixture:
    - Uses test-specific environment variables (QDRANT_TEST_*) to prevent pollution
    - Scans ports 6333-6400 for running Qdrant instances
    - Auto-starts Docker container if no instance found (can be disabled)
    - Finds first instance accessible without authentication
    - Creates unique collections per test
    - Automatically cleans up collections and containers after test

    Environment Variables (all optional):
        QDRANT_TEST_URL: Direct URL override (e.g., http://localhost:6336)
        QDRANT_TEST_HOST: Test host (default: localhost)
        QDRANT_TEST_PORT: Test port override (e.g., 6336)
        QDRANT_TEST_API_KEY: Test-specific API key
        QDRANT_TEST_SKIP_DOCKER: Set to '1' or 'true' to disable auto-start
        QDRANT_TEST_IMAGE: Custom Docker image (default: qdrant/qdrant:latest)
        QDRANT_TEST_CONTAINER_NAME: Custom container name (default: qdrant-test)

    Usage:
        async def test_something(qdrant_test_manager):
            async with qdrant_test_manager.collection_context() as (client, collection):
                # Use client and collection
                await client.upsert(collection, points=[...])
                # Cleanup automatic
    """
    from .qdrant_test_manager import QdrantTestManager

    # Create manager with unique storage path for this test
    storage_path = tmp_path / "qdrant_storage"
    storage_path.mkdir(exist_ok=True)

    # Try to find an accessible Qdrant instance by scanning ports
    # This ensures we find an unauthenticated instance (e.g., 6336) not an auth-required one (e.g., 6333)
    import socket

    manager = None
    for port in range(6333, 6401):  # Scan 6333-6400
        # Quick check: is port in use?
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.1)  # Very quick check
            # Use 127.0.0.1 instead of localhost to avoid DNS lookup in WSL
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                # Nothing listening on this port, skip
                continue

        # Port has something running, try it as Qdrant
        try:
            test_manager = QdrantTestManager(
                port=port, storage_path=storage_path, auto_start_docker=False
            )
            # Verify this instance is accessible without auth
            if await test_manager.verify_connection():
                manager = test_manager
                break
            # Not accessible, try next port
            await test_manager.close()
        except Exception:
            # Error with this port, try next
            continue

    # If no accessible instance found, try Docker auto-start
    if manager is None:
        try:
            manager = QdrantTestManager(storage_path=storage_path, auto_start_docker=True)
            if not await manager.verify_connection():
                pytest.skip(
                    "No accessible Qdrant instance found and Docker auto-start failed. "
                    "Start unauthenticated instance with: docker run -p 6336:6333 qdrant/qdrant:latest"
                )
        except RuntimeError as e:
            pytest.skip(str(e))

    yield manager

    # Cleanup after test (including Docker container if we started it)
    await manager.close()


@pytest.fixture
async def qdrant_test_client(qdrant_test_manager: QdrantTestManager) -> AsyncQdrantClient:
    """Provide a connected Qdrant client for testing.

    This is a convenience fixture that just returns the client.
    Use qdrant_test_manager.collection_context() for collection management.
    """
    return await qdrant_test_manager.ensure_client()


@pytest.fixture
async def qdrant_test_collection(
    qdrant_test_manager: QdrantTestManager,
) -> AsyncGeneratorType[tuple[AsyncQdrantClient, str]]:
    """Provide a test collection with automatic cleanup.

    Yields:
        Tuple of (client, collection_name)

    Usage:
        async def test_something(qdrant_test_collection):
            client, collection = qdrant_test_collection
            await client.upsert(collection, points=[...])
    """
    async with qdrant_test_manager.collection_context() as (client, collection):
        yield client, collection


@pytest.fixture
def vector_store_factory(qdrant_test_manager) -> Any:
    """Factory fixture to create configured vector store providers.

    Handles creation of settings, client, and capabilities for DI-compliant instantiation.
    """

    async def _factory(provider_cls, config_overrides=None, embedding_caps=None):
        from uuid import uuid4

        from pydantic import AnyUrl
        from qdrant_client import AsyncQdrantClient

        from codeweaver.providers import (
            CollectionConfig,
            ConfiguredCapability,
            EmbeddingCapabilityGroup,
            EmbeddingModelCapabilities,
            EmbeddingProviderSettings,
            MemoryVectorStoreProvider,
            MemoryVectorStoreProviderSettings,
            Provider,
            QdrantClientOptions,
            QdrantVectorStoreProvider,
            QdrantVectorStoreProviderSettings,
        )

        config_overrides = config_overrides or {}

        # Default caps if not provided
        if embedding_caps is None:
            from codeweaver.providers.config.embedding import FastEmbedEmbeddingConfig

            dense_caps = EmbeddingModelCapabilities(
                name="test-dense-model",
                default_dimension=768,
                default_dtype="float16",
                preferred_metrics=("cosine", "dot"),
            )
            # Create proper embedding config for the provider settings
            embedding_config = FastEmbedEmbeddingConfig(
                tag="fastembed", provider=Provider.FASTEMBED, model_name="test-dense-model"
            )
            # Mock settings to satisfy ConfiguredCapability
            mock_settings = EmbeddingProviderSettings(
                provider=Provider.FASTEMBED,
                model_name="test-dense-model",
                embedding_config=embedding_config,
            )
            configured_dense = ConfiguredCapability(capability=dense_caps, config=mock_settings)
            embedding_caps = EmbeddingCapabilityGroup(dense=configured_dense, sparse=None)

        if provider_cls is QdrantVectorStoreProvider:
            collection_name = config_overrides.get("collection_name")
            if not collection_name:
                collection_name = qdrant_test_manager.create_collection_name("factory-test")
                # Create collection if we generated the name (assumes default vector size if not specified)
                # If config_overrides has vector sizes, user might want to create it themselves, but for convenience:
                dense_size = config_overrides.get("dense_vector_size", 768)
                sparse_size = config_overrides.get("sparse_vector_size", None)
                await qdrant_test_manager.create_collection(
                    collection_name, dense_vector_size=dense_size, sparse_vector_size=sparse_size
                )

            url = config_overrides.get("url", qdrant_test_manager.url)

            settings = QdrantVectorStoreProviderSettings(
                provider=Provider.QDRANT,
                client_options=QdrantClientOptions(url=AnyUrl(url)),
                collection=CollectionConfig(collection_name=collection_name),
                batch_size=config_overrides.get("batch_size", 64),
            )
            client = AsyncQdrantClient(url=url)
            provider = QdrantVectorStoreProvider(
                client=client, _provider=Provider.QDRANT, config=settings, caps=embedding_caps
            )
            await provider._initialize()
            return provider

        if provider_cls is MemoryVectorStoreProvider:
            collection_name = config_overrides.get("collection_name", f"mem-test-{uuid4().hex[:8]}")
            persist_path = config_overrides.get("persist_path")

            in_memory_config = {
                "collection_name": collection_name,
                "auto_persist": config_overrides.get("auto_persist", False),
            }
            if persist_path:
                in_memory_config["persist_path"] = persist_path

            settings = MemoryVectorStoreProviderSettings(
                provider=Provider.MEMORY, in_memory_config=in_memory_config
            )
            client = AsyncQdrantClient(location=":memory:")
            provider = MemoryVectorStoreProvider(
                client=client, _provider=Provider.MEMORY, config=settings, caps=embedding_caps
            )
            await provider._initialize()
            return provider

        raise ValueError(f"Unknown provider class: {provider_cls}")

    return _factory


# ===========================================================================
# *                    Embedding Test Utilities
# ===========================================================================


def create_test_chunk_with_embeddings(
    chunk_id: UUID7,
    chunk_name: str,
    file_path: Path,
    language: SemanticSearchLanguage | ConfigLanguage | str,
    content: str,
    dense_embedding: list[float] | None = None,
    sparse_embedding: dict | None = None,
    line_start: int = 1,
    line_end: int = 1,
) -> CodeChunk:
    """Create a CodeChunk with embeddings registered in the EmbeddingRegistry.

    Args:
        chunk_id: UUID for the chunk
        chunk_name: Name identifier for the chunk
        file_path: Path to the source file
        language: Programming language
        content: Code content
        dense_embedding: Dense embedding vector (list of floats)
        sparse_embedding: Sparse embedding dict with 'indices' and 'values'
        line_start: Starting line number
        line_end: Ending line number

    Returns:
        CodeChunk with embeddings registered in the global registry
    """

    from codeweaver.core import BatchKeys, CodeChunk, Span, uuid7
    from codeweaver.providers import ChunkEmbeddings, EmbeddingBatchInfo, get_embedding_registry

    # Create the base chunk
    chunk = CodeChunk(
        chunk_id=chunk_id,
        ext_kind=ExtKind.from_language(language, ChunkKind.CODE),
        chunk_name=chunk_name,
        file_path=file_path,
        language=language,
        content=content,
        line_range=Span(start=line_start, end=line_end, source_id=chunk_id),
    )

    registry = get_embedding_registry()

    # Create batch IDs
    dense_batch_id = uuid7() if dense_embedding else None
    sparse_batch_id = uuid7() if sparse_embedding else None

    # Register embeddings in the registry
    dense_info = None
    sparse_info = None

    if dense_embedding:
        dense_info = EmbeddingBatchInfo.create_dense(
            batch_id=cast(UUID, dense_batch_id),
            batch_index=0,
            chunk_id=chunk_id,
            model="test-dense-model",
            embeddings=dense_embedding,
            dimension=len(dense_embedding),
        )
        # Set batch key on chunk
        dense_batch_key = BatchKeys(id=cast(UUID, dense_batch_id), idx=0, sparse=False)
        chunk = chunk.set_batch_keys(dense_batch_key)

    if sparse_embedding:
        # Convert sparse dict format to SparseEmbedding object
        from codeweaver.providers import SparseEmbedding

        sparse_emb = SparseEmbedding(
            indices=sparse_embedding.get("indices", []), values=sparse_embedding.get("values", [])
        )
        sparse_info = EmbeddingBatchInfo.create_sparse(
            batch_id=cast(UUID, sparse_batch_id),
            batch_index=0,
            chunk_id=chunk_id,
            model="test-sparse-model",
            embeddings=sparse_emb,
        )
        # Set batch key on chunk
        sparse_batch_key = BatchKeys(id=cast(UUID, sparse_batch_id), idx=0, sparse=True)
        chunk = chunk.set_batch_keys(sparse_batch_key)

    # Register in the embedding registry
    if dense_info or sparse_info:
        # Create ChunkEmbeddings with the chunk, then add embeddings
        chunk_embeddings = ChunkEmbeddings(chunk=chunk)
        if dense_info:
            chunk_embeddings = chunk_embeddings.add(dense_info)
        if sparse_info:
            chunk_embeddings = chunk_embeddings.add(sparse_info)
        registry[chunk_id] = chunk_embeddings

    return chunk


# ===========================================================================
# *                    CLI Test Fixtures
# ===========================================================================


@pytest.fixture
def clean_cli_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clean environment variables for isolated CLI testing."""
    env_vars_to_remove = [
        "CODEWEAVER_PROJECT_PATH",
        "CODEWEAVER_EMBEDDING_PROVIDER",
        "CODEWEAVER_VECTOR_STORE_TYPE",
        "VOYAGE_API_KEY",
        "OPENAI_API_KEY",
        "COHERE_API_KEY",
        "QDRANT_API_KEY",
        "QDRANT_URL",
    ]

    for var in env_vars_to_remove:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create isolated home directory for CLI testing."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def cli_test_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create test project with git repository for CLI testing."""
    project = tmp_path / "test_project"
    project.mkdir()

    # Initialize git
    git_dir = project / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n")

    # Create source structure
    src = project / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "main.py").write_text('"""Main module."""\n\ndef main():\n    pass\n')
    (src / "utils.py").write_text('"""Utilities."""\n\ndef helper():\n    pass\n')

    # Change to project directory
    monkeypatch.chdir(project)

    return project


@pytest.fixture
def cli_api_keys(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Set test API keys for CLI testing."""
    keys = {
        "VOYAGE_API_KEY": "test-voyage-key",
        "OPENAI_API_KEY": "test-openai-key",
        "COHERE_API_KEY": "test-cohere-key",
        "QDRANT_API_KEY": "test-qdrant-key",
    }

    for key, value in keys.items():
        monkeypatch.setenv(key, value)

    return keys


def _get_settings(settings: SettingsDep = INJECTED) -> "CodeWeaverSettingsType":
    return settings


@pytest.fixture(autouse=True)
def reset_cli_settings_cache() -> None:
    """Reset settings cache between CLI tests.

    Note: Settings are now managed through DI container, which is reset
    by the reset_di_container fixture. This fixture is kept for compatibility
    and performs minimal cache clearing.
    """
    if _get_settings():
        from codeweaver.core.di.container import get_container

        container = get_container()
        container.clear_request_cache()
        container.clear_overrides()
    # reset_di_container is already an autouse fixture - no need to call it


@pytest.fixture(autouse=True)
def reset_di_container() -> Generator[None, None, None]:
    """Reset DI container between tests to ensure isolation."""
    from codeweaver.core import reset_container

    reset_container()
    yield
    reset_container()
    reset_container()


@pytest.fixture
def clean_container() -> Generator["Container", None, None]:
    """Provides a fresh DI container with all overrides cleared.

    Usage:
        def test_something(clean_container):
            clean_container.override(...)
    """
    from codeweaver.core import get_container

    container = get_container()
    container.clear_overrides()
    yield container
    container.clear_overrides()


@pytest.fixture
def test_project_path(tmp_path: Path) -> Path:
    """Create a test project path for CLI testing."""
    project = tmp_path / "test_project"
    project.mkdir()
    return project
