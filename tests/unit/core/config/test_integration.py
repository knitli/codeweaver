# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Integration tests for config resolution system."""

import pytest

from codeweaver.core.config.defaults import clear_defaults, register_default_provider
from codeweaver.core.config.registry import clear_configurables, register_configurable
from codeweaver.core.config.resolver import resolve_all_configs
from codeweaver.core.di import get_container


class MockEmbeddingConfig:
    """Mock embedding config for testing."""

    def __init__(self, dimension: int | None = None, datatype: str | None = None):
        self._dimension = dimension
        self._datatype = datatype
        self.config_dependencies_called = False
        self.apply_resolved_called = False

    def config_dependencies(self) -> dict[str, type]:
        """Embedding configs don't depend on others."""
        self.config_dependencies_called = True
        return {}

    async def apply_resolved_config(self, **resolved) -> None:
        """Nothing to apply - we're a provider."""
        self.apply_resolved_called = True

    async def get_dimension(self) -> int | None:
        """Return the configured dimension."""
        return self._dimension

    async def get_datatype(self) -> str | None:
        """Return the configured datatype."""
        return self._datatype


class MockVectorStoreConfig:
    """Mock vector store config for testing."""

    def __init__(self):
        self.resolved_dimension: int | None = None
        self.resolved_datatype: str | None = None
        self.configured_for_dimension = False
        self.configured_for_datatype = False

    def config_dependencies(self) -> dict[str, type]:
        """Vector store depends on embedding config."""
        return {"embedding": MockEmbeddingConfig}

    async def apply_resolved_config(self, **resolved) -> None:
        """Apply configuration from embedding."""
        if embedding := resolved.get("embedding"):
            dimension = await embedding.get_dimension()
            datatype = await embedding.get_datatype()

            if dimension:
                self.resolved_dimension = dimension
                self._configure_for_dimension(dimension)

            if datatype:
                self.resolved_datatype = datatype
                self._configure_for_datatype(datatype)

    def _configure_for_dimension(self, dimension: int) -> None:
        """Mock dimension configuration."""
        self.configured_for_dimension = True

    def _configure_for_datatype(self, datatype: str) -> None:
        """Mock datatype configuration."""
        self.configured_for_datatype = True


@pytest.fixture(autouse=True)
def _cleanup():
    """Clean up after each test."""
    yield
    clear_configurables()
    clear_defaults()
    get_container().clear()


@pytest.mark.asyncio
async def test_full_embedding_to_vector_store_resolution():
    """Test full config resolution from embedding to vector store."""
    # Create embedding config with specific values
    embedding_config = MockEmbeddingConfig(dimension=512, datatype="float16")

    # Register in DI container
    container = get_container()
    container.register(MockEmbeddingConfig, lambda: embedding_config, singleton=True)

    # Create vector store config
    vector_store_config = MockVectorStoreConfig()

    # Register both for resolution
    register_configurable(embedding_config)
    register_configurable(vector_store_config)

    # Trigger resolution
    await resolve_all_configs()

    # Verify vector store was configured
    assert vector_store_config.resolved_dimension == 512
    assert vector_store_config.resolved_datatype == "float16"
    assert vector_store_config.configured_for_dimension
    assert vector_store_config.configured_for_datatype


@pytest.mark.asyncio
async def test_resolution_with_defaults():
    """Test resolution using default providers."""
    # Register default providers
    register_default_provider("primary.embedding.dimension", lambda: 768)
    register_default_provider("primary.embedding.datatype", lambda: "uint8")

    # Create embedding config without explicit values
    # (in real code, it would use the defaults)
    embedding_config = MockEmbeddingConfig()

    # Override get_dimension to use defaults
    async def get_dimension_with_default():
        from codeweaver.core.config.defaults import get_default

        return get_default("primary.embedding.dimension")

    async def get_datatype_with_default():
        from codeweaver.core.config.defaults import get_default

        return get_default("primary.embedding.datatype")

    embedding_config.get_dimension = get_dimension_with_default
    embedding_config.get_datatype = get_datatype_with_default

    # Register in DI
    container = get_container()
    container.register(MockEmbeddingConfig, lambda: embedding_config, singleton=True)

    # Create vector store
    vector_store_config = MockVectorStoreConfig()
    register_configurable(vector_store_config)

    # Trigger resolution
    await resolve_all_configs()

    # Should use default values
    assert vector_store_config.resolved_dimension == 768
    assert vector_store_config.resolved_datatype == "uint8"


@pytest.mark.asyncio
async def test_resolution_with_missing_embedding_config():
    """Test resolution when embedding config is not available (monorepo scenario)."""
    # Create vector store config without registering embedding config
    vector_store_config = MockVectorStoreConfig()
    register_configurable(vector_store_config)

    # Should not raise - should gracefully handle missing dependency
    await resolve_all_configs()

    # Should have no resolved values
    assert vector_store_config.resolved_dimension is None
    assert vector_store_config.resolved_datatype is None
    assert not vector_store_config.configured_for_dimension
    assert not vector_store_config.configured_for_datatype


@pytest.mark.asyncio
async def test_resolution_with_partial_config():
    """Test resolution when embedding config has only dimension."""
    embedding_config = MockEmbeddingConfig(dimension=384, datatype=None)

    container = get_container()
    container.register(MockEmbeddingConfig, lambda: embedding_config, singleton=True)

    vector_store_config = MockVectorStoreConfig()
    register_configurable(vector_store_config)

    await resolve_all_configs()

    # Should configure dimension but not datatype
    assert vector_store_config.resolved_dimension == 384
    assert vector_store_config.resolved_datatype is None
    assert vector_store_config.configured_for_dimension
    assert not vector_store_config.configured_for_datatype


@pytest.mark.asyncio
async def test_multiple_vector_stores_same_embedding():
    """Test multiple vector stores using the same embedding config."""
    embedding_config = MockEmbeddingConfig(dimension=1024, datatype="int8")

    container = get_container()
    container.register(MockEmbeddingConfig, lambda: embedding_config, singleton=True)

    # Create two vector store configs
    vector_store1 = MockVectorStoreConfig()
    vector_store2 = MockVectorStoreConfig()

    register_configurable(vector_store1)
    register_configurable(vector_store2)

    await resolve_all_configs()

    # Both should be configured identically
    assert vector_store1.resolved_dimension == 1024
    assert vector_store1.resolved_datatype == "int8"
    assert vector_store2.resolved_dimension == 1024
    assert vector_store2.resolved_datatype == "int8"
