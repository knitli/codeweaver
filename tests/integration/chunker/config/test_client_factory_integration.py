# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration tests for client factory with real provider instantiation.

Tests the complete flow from settings to provider instance with client creation.

NOTE: These tests are DEPRECATED and SKIPPED because ProviderRegistry was removed
during the DI migration. Provider instantiation is now handled through the DI container.
"""

from unittest.mock import Mock, patch

import pytest

from codeweaver.core import Provider, ProviderCategory


def make_lazy_provider_mock(name: str, resolved_class: Mock, instance: Mock | None = None) -> Mock:
    """Helper to create and configure a lazy provider mock."""
    lazy_mock = Mock()
    lazy_mock.__name__ = name
    lazy_mock._resolve.return_value = resolved_class
    # mock_provider_lazy is invoked like the provider class
    lazy_mock.return_value = instance if instance is not None else Mock()
    return lazy_mock


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skip(reason="ProviderRegistry removed - functionality tested through DI container"),
]


@pytest.mark.external_api
@pytest.mark.mock_only
@pytest.mark.qdrant
class TestProviderInstantiationWithClientFactory:
    """Test complete provider instantiation flow with client creation."""

    @pytest.fixture
    def registry(self):
        """Create a ProviderRegistry for testing."""
        from unittest.mock import Mock

        from codeweaver.core import ProviderRegistry

        # Create mock settings to avoid Unset type annotation issues
        mock_settings = Mock()
        mock_settings.provider = Mock()

        registry = ProviderRegistry.__new__(ProviderRegistry)
        registry._settings = mock_settings
        registry._embedding_providers = {}
        registry._sparse_embedding_providers = {}
        registry._vector_store_providers = {}
        registry._reranking_providers = {}
        registry._agent_providers = {}
        registry._data_providers = {}
        registry._embedding_instances = {}
        registry._sparse_embedding_instances = {}
        registry._vector_store_instances = {}
        registry._reranking_instances = {}
        registry._agent_instances = {}
        registry._data_instances = {}

        return registry

    def test_create_provider_with_client_from_map(self, registry):
        """Test create_provider integrates with client factory."""
        # Mock the CLIENT_MAP and client class
        from inspect import Parameter, Signature

        from codeweaver.providers import Client

        mock_client_instance = Mock()
        mock_client_class = Mock(return_value=mock_client_instance)
        # Add __signature__ to make it pass clean_args type checking
        mock_client_class.__signature__ = Signature([
            Parameter("api_key", Parameter.KEYWORD_ONLY, default=None)
        ])
        mock_lateimport = Mock()
        mock_lateimport._resolve.return_value = mock_client_class

        mock_provider_class = Mock()
        mock_provider_instance = Mock()
        mock_provider_lazy = make_lazy_provider_mock(
            "MockVoyageProvider", mock_provider_class, mock_provider_instance
        )
        mock_provider_class.return_value = mock_provider_instance

        mock_client_map = {
            Provider.VOYAGE: (
                Client(
                    provider=Provider.VOYAGE,
                    category=ProviderCategory.EMBEDDING,
                    client=mock_lateimport,
                    provider_class=mock_provider_lazy,
                ),
            )
        }

        with patch("codeweaver.providersCLIENT_MAP", mock_client_map):
            with patch.dict("os.environ", {"VOYAGE_API_KEY": "test_key"}):
                # Register the provider
                registry.register(Provider.VOYAGE, ProviderCategory.EMBEDDING, mock_provider_lazy)

                # Create provider
                registry.create_provider(
                    Provider.VOYAGE,
                    ProviderCategory.EMBEDDING,
                    provider_settings={"api_key": "test_key"},
                )

                # Verify client was created and passed to provider
                mock_provider_lazy.assert_called_once()
                call_kwargs = mock_provider_lazy.call_args[1]
                assert "client" in call_kwargs
                assert call_kwargs["client"] == mock_client_instance

    def test_create_provider_skips_client_if_provided(self, registry):
        """Test that existing client in kwargs is not overridden."""
        from codeweaver.providers import Client

        mock_existing_client = Mock()
        mock_client_class = Mock()
        mock_lateimport = Mock()
        mock_lateimport._resolve.return_value = mock_client_class

        mock_provider_class = Mock()
        mock_provider_lazy = make_lazy_provider_mock("MockVoyageProvider", mock_provider_class)

        mock_client_map = {
            Provider.VOYAGE: (
                Client(
                    provider=Provider.VOYAGE,
                    category=ProviderCategory.EMBEDDING,
                    client=mock_lateimport,
                    provider_class=mock_provider_lazy,
                ),
            )
        }

        with patch("codeweaver.providersCLIENT_MAP", mock_client_map):
            registry.register(Provider.VOYAGE, ProviderCategory.EMBEDDING, mock_provider_lazy)

            # Pass explicit client
            registry.create_provider(
                Provider.VOYAGE,
                ProviderCategory.EMBEDDING,
                client=mock_existing_client,  # Explicit client
            )

            # Should use existing client, not create new one
            mock_provider_lazy.assert_called_once()
            call_kwargs = mock_provider_lazy.call_args[1]
            assert call_kwargs["client"] == mock_existing_client
            # Mock client class should not have been called
            mock_client_class.assert_not_called()

    def test_create_provider_handles_client_creation_failure(self, registry):
        """Test graceful degradation when client creation fails."""
        from codeweaver.providers import Client

        mock_client_class = Mock(side_effect=Exception("Connection failed"))
        mock_lateimport = Mock()
        mock_lateimport._resolve.return_value = mock_client_class

        mock_provider_class = Mock()
        mock_provider_lazy = make_lazy_provider_mock("MockVoyageProvider", mock_provider_class)
        mock_provider_lazy.return_value = Mock()

        mock_client_map = {
            Provider.VOYAGE: (
                Client(
                    provider=Provider.VOYAGE,
                    category=ProviderCategory.EMBEDDING,
                    client=mock_lateimport,
                    provider_class=mock_provider_lazy,
                ),
            )
        }

        with patch("codeweaver.providersCLIENT_MAP", mock_client_map):
            with patch.dict("os.environ", {"VOYAGE_API_KEY": "test_key"}):
                registry.register(Provider.VOYAGE, ProviderCategory.EMBEDDING, mock_provider_lazy)

                # Should not raise, just log warning
                registry.create_provider(Provider.VOYAGE, ProviderCategory.EMBEDDING)

                # Provider should still be created (without client)
                mock_provider_lazy.assert_called_once()
                call_kwargs = mock_provider_lazy.call_args[1]
                # Client should not be in kwargs since creation failed
                assert "client" not in call_kwargs


@pytest.mark.external_api
@pytest.mark.mock_only
@pytest.mark.qdrant
class TestVectorStoreProviderWithClientFactory:
    """Test vector store provider instantiation with client factory."""

    @pytest.fixture
    def registry(self):
        """Create a ProviderRegistry for testing."""
        from unittest.mock import Mock

        from codeweaver.core import ProviderRegistry

        # Create mock settings to avoid Unset type annotation issues
        mock_settings = Mock()
        mock_settings.provider = Mock()

        registry = ProviderRegistry.__new__(ProviderRegistry)
        registry._settings = mock_settings
        registry._embedding_providers = {}
        registry._sparse_embedding_providers = {}
        registry._vector_store_providers = {}
        registry._reranking_providers = {}
        registry._agent_providers = {}
        registry._data_providers = {}
        registry._embedding_instances = {}
        registry._sparse_embedding_instances = {}
        registry._vector_store_instances = {}
        registry._reranking_instances = {}
        registry._agent_instances = {}
        registry._data_instances = {}

        return registry

    def test_qdrant_provider_with_memory_mode(self, registry):
        """Test Qdrant provider creation in memory mode."""
        from codeweaver.providers import Client

        mock_client_instance = Mock()
        mock_client_instance.location = ":memory:"
        # Fix: Mock should fail first (no URL), then succeed with memory mode
        mock_client_class = Mock(side_effect=[Exception("No URL provided"), mock_client_instance])
        mock_lateimport = Mock()
        mock_lateimport._resolve.return_value = mock_client_class

        mock_provider_class = Mock()
        mock_provider_lazy = make_lazy_provider_mock("MockQdrantProvider", mock_provider_class)
        mock_provider_lazy.return_value = Mock()

        mock_client_map = {
            Provider.QDRANT: (
                Client(
                    provider=Provider.QDRANT,
                    category=ProviderCategory.VECTOR_STORE,
                    client=mock_lateimport,
                    provider_class=mock_provider_lazy,
                ),
            )
        }

        with patch("codeweaver.providersCLIENT_MAP", mock_client_map):
            registry.register(Provider.QDRANT, ProviderCategory.VECTOR_STORE, mock_provider_lazy)

            # Create provider without settings (should use memory mode)
            registry.create_provider(Provider.QDRANT, ProviderCategory.VECTOR_STORE)

            # Verify client was created with memory mode (second call after exception)
            assert mock_client_class.call_count == 2
            # Check that location=':memory:' was passed (may have other kwargs from global config)
            assert mock_client_class.call_args[1]["location"] == ":memory:"

            # Verify client was passed to provider
            mock_provider_lazy.assert_called_once()
            call_kwargs = mock_provider_lazy.call_args[1]
            assert "client" in call_kwargs
            assert call_kwargs["client"] == mock_client_instance

    def test_qdrant_provider_with_url_mode(self, registry):
        """Test Qdrant provider creation with URL."""
        from codeweaver.providers import Client

        mock_client_instance = Mock()
        mock_client_class = Mock(return_value=mock_client_instance)
        mock_lateimport = Mock()
        mock_lateimport._resolve.return_value = mock_client_class

        mock_provider_class = Mock()
        mock_provider_lazy = make_lazy_provider_mock("MockQdrantProvider", mock_provider_class)
        mock_provider_lazy.return_value = Mock()

        mock_client_map = {
            Provider.QDRANT: (
                Client(
                    provider=Provider.QDRANT,
                    category=ProviderCategory.VECTOR_STORE,
                    client=mock_lateimport,
                    provider_class=mock_provider_lazy,
                ),
            )
        }

        # Patch os.getenv to return None for QDRANT__SERVICE__API_KEY
        # This prevents the environment variable from interfering with test expectations
        import os

        original_getenv = os.getenv

        def mock_getenv(key, default=None):
            if key == "QDRANT__SERVICE__API_KEY":
                return None
            return original_getenv(key, default)

        with patch("os.getenv", side_effect=mock_getenv):
            with patch("codeweaver.providersCLIENT_MAP", mock_client_map):
                registry.register(
                    Provider.QDRANT, ProviderCategory.VECTOR_STORE, mock_provider_lazy
                )

                # Create provider with URL
                registry.create_provider(
                    Provider.QDRANT,
                    ProviderCategory.VECTOR_STORE,
                    provider_settings={"url": "http://localhost:6333", "api_key": "test_key"},
                )

                # Verify client was created with URL (explicit settings override global config)
                mock_client_class.assert_called_once()
                call_kwargs = mock_client_class.call_args[1]
                assert call_kwargs["url"] == "http://localhost:6333"
                assert call_kwargs["api_key"] == "test_key"


@pytest.mark.external_api
@pytest.mark.mock_only
@pytest.mark.qdrant
class TestProviderCategoryStringHandling:
    """Test that string provider_category values work correctly."""

    @pytest.fixture
    def registry(self):
        """Create a ProviderRegistry for testing."""
        from unittest.mock import Mock

        from codeweaver.core import ProviderRegistry

        # Create mock settings to avoid Unset type annotation issues
        mock_settings = Mock()
        mock_settings.provider = Mock()

        registry = ProviderRegistry.__new__(ProviderRegistry)
        registry._settings = mock_settings
        registry._embedding_providers = {}
        registry._sparse_embedding_providers = {}
        registry._vector_store_providers = {}
        registry._reranking_providers = {}
        registry._agent_providers = {}
        registry._data_providers = {}
        registry._embedding_instances = {}
        registry._sparse_embedding_instances = {}
        registry._vector_store_instances = {}
        registry._reranking_instances = {}
        registry._agent_instances = {}
        registry._data_instances = {}

        return registry

    def test_string_provider_category_in_create_provider(self, registry):
        """Test create_provider works with string provider_category."""
        from inspect import Parameter, Signature

        from codeweaver.providers import Client

        mock_client_instance = Mock()
        mock_client_class = Mock(return_value=mock_client_instance)
        # Add __signature__ to make it pass clean_args type checking
        mock_client_class.__signature__ = Signature([
            Parameter("api_key", Parameter.KEYWORD_ONLY, default=None)
        ])
        mock_lateimport = Mock()
        mock_lateimport._resolve.return_value = mock_client_class

        mock_provider_class = Mock()
        mock_provider_lazy = make_lazy_provider_mock("MockVoyageProvider", mock_provider_class)
        mock_provider_lazy.return_value = Mock()

        mock_client_map = {
            Provider.VOYAGE: (
                Client(
                    provider=Provider.VOYAGE,
                    category=ProviderCategory.EMBEDDING,
                    client=mock_lateimport,
                    provider_class=mock_provider_lazy,
                ),
            )
        }

        with patch("codeweaver.providersCLIENT_MAP", mock_client_map):
            with patch.dict("os.environ", {"VOYAGE_API_KEY": "test_key"}):
                registry.register(Provider.VOYAGE, ProviderCategory.EMBEDDING, mock_provider_lazy)

                # Use string instead of enum
                registry.create_provider(
                    Provider.VOYAGE,
                    "embedding",  # String
                    provider_settings={"api_key": "test_key"},
                )

                # Should work correctly
                mock_provider_lazy.assert_called_once()
                call_kwargs = mock_provider_lazy.call_args[1]
                assert "client" in call_kwargs


@pytest.mark.external_api
@pytest.mark.mock_only
@pytest.mark.qdrant
class TestGlobalRegistryIntegration:
    """Test integration with global get_provider_registry()."""

    def test_get_provider_registry_has_client_factory(self):
        """Test that global registry has client factory methods."""
        from unittest.mock import Mock

        from codeweaver.core import ProviderRegistry

        # Create mock registry instance
        mock_settings = Mock()
        registry = ProviderRegistry.__new__(ProviderRegistry)
        registry._settings = mock_settings

        # Verify methods exist
        assert hasattr(registry, "_create_client_from_map")
        assert hasattr(registry, "_instantiate_client")
        assert callable(registry._create_client_from_map)
        assert callable(registry._instantiate_client)
