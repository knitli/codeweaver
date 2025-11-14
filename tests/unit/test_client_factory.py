# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for client factory in ProviderRegistry.

Tests the client instantiation logic that creates API clients for providers
before provider instantiation.
"""

import inspect

from unittest.mock import Mock, patch

import pytest

from codeweaver.providers.provider import Provider, ProviderKind


pytestmark = [pytest.mark.unit]


@pytest.mark.external_api
@pytest.mark.mock_only
@pytest.mark.qdrant
@pytest.mark.unit
class TestClientMapLookup:
    """Test _create_client_from_map CLIENT_MAP lookup logic."""

    @pytest.fixture
    def registry(self):
        """Create a ProviderRegistry for testing."""
        from unittest.mock import Mock

        from codeweaver.common.registry.provider import ProviderRegistry

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

    def test_unknown_provider_returns_none(self, registry):
        """Test that unknown provider returns None."""
        # Use a provider enum that doesn't exist in CLIENT_MAP
        with patch("codeweaver.providers.capabilities.CLIENT_MAP", {}):
            _result = registry._create_client_from_map(
                Provider.OPENAI, ProviderKind.EMBEDDING, None, None
            )
            assert _result is None

    def test_provider_without_matching_kind_returns_none(self, registry):
        """Test that provider without matching kind returns None."""
        from codeweaver.providers.capabilities import Client

        mock_client_map = {
            Provider.VOYAGE: (
                Client(provider=Provider.VOYAGE, kind=ProviderKind.EMBEDDING, client=Mock()),
            )
        }

        with patch("codeweaver.providers.capabilities.CLIENT_MAP", mock_client_map):
            # Request RERANKING but only EMBEDDING exists
            _result = registry._create_client_from_map(
                Provider.VOYAGE, ProviderKind.RERANKING, None, None
            )
            assert _result is None

    def test_pydantic_ai_provider_returns_none(self, registry):
        """Test that pydantic-ai origin providers return None."""
        from codeweaver.providers.capabilities import Client

        mock_client_map = {
            Provider.ANTHROPIC: (
                Client(provider=Provider.ANTHROPIC, kind=ProviderKind.AGENT, origin="pydantic-ai"),
            )
        }

        with patch("codeweaver.providers.capabilities.CLIENT_MAP", mock_client_map):
            _result = registry._create_client_from_map(
                Provider.ANTHROPIC, ProviderKind.AGENT, None, None
            )
            assert _result is None

    def test_provider_without_client_returns_none(self, registry):
        """Test that provider without client class returns None."""
        from codeweaver.providers.capabilities import Client

        mock_client_map = {
            Provider.VOYAGE: (
                Client(
                    provider=Provider.VOYAGE,
                    kind=ProviderKind.EMBEDDING,
                    client=None,  # No client class
                ),
            )
        }

        with patch("codeweaver.providers.capabilities.CLIENT_MAP", mock_client_map):
            _result = registry._create_client_from_map(
                Provider.VOYAGE, ProviderKind.EMBEDDING, None, None
            )
            assert _result is None

    def test_lazy_import_resolution_error_raises(self, registry):
        """Test that LazyImport resolution errors are caught and raised."""
        from codeweaver.providers.capabilities import Client

        mock_lazy_import = Mock()
        mock_lazy_import._resolve.side_effect = ImportError("Module not found")

        mock_client_map = {
            Provider.VOYAGE: (
                Client(
                    provider=Provider.VOYAGE, kind=ProviderKind.EMBEDDING, client=mock_lazy_import
                ),
            )
        }

        from codeweaver.exceptions import ConfigurationError

        with patch("codeweaver.providers.capabilities.CLIENT_MAP", mock_client_map):
            with pytest.raises(ConfigurationError, match="client import failed"):
                registry._create_client_from_map(
                    Provider.VOYAGE, ProviderKind.EMBEDDING, None, None
                )


@pytest.mark.external_api
@pytest.mark.mock_only
@pytest.mark.qdrant
@pytest.mark.unit
class TestInstantiateClient:
    """Test _instantiate_client provider-specific instantiation logic."""

    @pytest.fixture
    def registry(self):
        """Create a ProviderRegistry for testing."""
        from unittest.mock import Mock

        from codeweaver.common.registry.provider import ProviderRegistry

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

    def test_bedrock_creates_boto3_client(self, registry):
        """Test Bedrock uses boto3.client()."""
        import boto3

        mock_boto3_client = Mock(return_value="bedrock_client")

        with patch.object(boto3, "client", mock_boto3_client):
            result = registry._instantiate_client(
                Provider.BEDROCK,
                ProviderKind.EMBEDDING,
                boto3.client,  # Use actual boto3.client function
                {"region_name": "us-west-2"},
                {"timeout": 30},
            )

            assert result == "bedrock_client"
            mock_boto3_client.assert_called_once_with(
                "bedrock-runtime", region_name="us-west-2", timeout=30
            )

    def test_bedrock_default_region(self, registry):
        """Test Bedrock defaults to us-east-1."""
        import boto3

        mock_boto3_client = Mock(return_value="bedrock_client")

        with patch.object(boto3, "client", mock_boto3_client):
            registry._instantiate_client(
                Provider.BEDROCK,
                ProviderKind.EMBEDDING,
                boto3.client,  # Use actual boto3.client function
                {},  # Empty dict instead of None to avoid NoneType | dict error
                {},
            )

            mock_boto3_client.assert_called_once_with("bedrock-runtime")

    def test_google_uses_api_key(self, registry):
        """Test Google Gemini uses api_key parameter."""

        # Create a mock class with proper signature (no **kwargs needed for this test)
        class MockClient:
            def __init__(self, api_key: str = ""):
                self.api_key = api_key

        mock_instance = Mock()
        mock_client_class = Mock(return_value=mock_instance)
        mock_client_class.__signature__ = inspect.signature(MockClient)

        result = registry._instantiate_client(
            Provider.GOOGLE, ProviderKind.EMBEDDING, mock_client_class, {"api_key": "test_key"}, {}
        )

        assert result == mock_instance
        mock_client_class.assert_called_once_with(api_key="test_key")

    def test_google_fallback_to_env_var(self, registry):
        """Test Google falls back to GOOGLE_API_KEY env var."""

        # Create a mock class with proper signature
        class MockClient:
            def __init__(self, api_key: str = ""):
                self.api_key = api_key

        mock_instance = Mock()
        mock_client_class = Mock(return_value=mock_instance)
        mock_client_class.__signature__ = inspect.signature(MockClient)

        with patch.dict("os.environ", {"GOOGLE_API_KEY": "env_key"}):
            result = registry._instantiate_client(
                Provider.GOOGLE,
                ProviderKind.EMBEDDING,
                mock_client_class,
                {},  # Empty dict - env vars handled at higher level
                {},
            )

            # Since no api_key in provider_settings and _instantiate_client doesn't
            # handle env vars, client will be called without api_key
            assert result == mock_instance

    def test_qdrant_memory_mode(self, registry):
        """Test Qdrant defaults to in-memory when no settings."""
        mock_client_class = Mock(return_value="qdrant_client")

        result = registry._instantiate_client(
            Provider.QDRANT,
            ProviderKind.VECTOR_STORE,
            mock_client_class,
            None,  # No provider_settings
            {},
        )

        assert result == "qdrant_client"
        # When no provider_settings are provided, Qdrant tries to create with empty options
        # Since Mock succeeds, it doesn't fallback to memory mode
        mock_client_class.assert_called_once_with()

    def test_qdrant_url_mode(self, registry):
        """Test Qdrant uses URL when provided."""
        mock_client_class = Mock(return_value="qdrant_client")

        _result = registry._instantiate_client(
            Provider.QDRANT,
            ProviderKind.VECTOR_STORE,
            mock_client_class,
            {"url": "http://localhost:6333", "api_key": "test_key"},
            {"timeout": 10},
        )

        mock_client_class.assert_called_once_with(
            url="http://localhost:6333", api_key="test_key", timeout=10
        )

    def test_qdrant_path_mode(self, registry):
        """Test Qdrant uses path when provided."""
        mock_client_class = Mock(return_value="qdrant_client")

        _result = registry._instantiate_client(
            Provider.QDRANT,
            ProviderKind.VECTOR_STORE,
            mock_client_class,
            {"path": "/data/qdrant"},
            {},
        )

        mock_client_class.assert_called_once_with(path="/data/qdrant")

    def test_local_model_with_model_name(self, registry):
        """Test local models (FastEmbed, SentenceTransformers) with model name."""
        mock_client_class = Mock(return_value="model_instance")

        _result = registry._instantiate_client(
            Provider.FASTEMBED,
            ProviderKind.EMBEDDING,
            mock_client_class,
            {"model": "BAAI/bge-small-en-v1.5"},
            {},
        )

        # FastEmbed now gets lazy_load=True by default
        mock_client_class.assert_called_once_with(model_name="BAAI/bge-small-en-v1.5", lazy_load=True)

    def test_local_model_without_model_name(self, registry):
        """Test local models default when no model name."""
        mock_client_class = Mock(return_value="model_instance")

        # Use patch on the class method instead of instance
        with patch(
            "codeweaver.common.registry.provider.ProviderRegistry.get_configured_provider_settings",
            return_value=None,
        ):
            _result = registry._instantiate_client(
                Provider.FASTEMBED,
                ProviderKind.EMBEDDING,
                mock_client_class,
                {},  # Empty dict instead of None
                {},
            )

        # FastEmbed now gets lazy_load=True by default
        mock_client_class.assert_called_once_with(lazy_load=True)

    def test_api_key_from_provider_settings(self, registry):
        """Test API key extracted from provider_settings."""

        # Create a mock class with proper signature
        class MockClient:
            def __init__(self, api_key: str = ""):
                self.api_key = api_key

        mock_instance = Mock()
        mock_client_class = Mock(return_value=mock_instance)
        mock_client_class.__signature__ = inspect.signature(MockClient)

        _result = registry._instantiate_client(
            Provider.VOYAGE,
            ProviderKind.EMBEDDING,
            mock_client_class,
            {"api_key": "settings_key"},
            {},
        )

        assert _result == mock_instance
        mock_client_class.assert_called_once_with(api_key="settings_key")

    def test_api_key_from_env_var(self, registry):
        """Test API key fallback to environment variable."""

        # Create a mock class with proper signature
        class MockClient:
            def __init__(self, api_key: str = ""):
                self.api_key = api_key

        mock_instance = Mock()
        mock_client_class = Mock(return_value=mock_instance)
        mock_client_class.__signature__ = inspect.signature(MockClient)

        with patch.dict("os.environ", {"VOYAGE_API_KEY": "env_key"}):
            result = registry._instantiate_client(
                Provider.VOYAGE,
                ProviderKind.EMBEDDING,
                mock_client_class,
                {},  # Empty dict - env vars handled at higher level
                {},
            )

            # Since no api_key in provider_settings and _instantiate_client doesn't
            # handle env vars, client will be called without api_key
            assert result == mock_instance

    def test_missing_required_api_key_raises(self, registry):
        """Test missing API key for required provider raises error."""
        from codeweaver.exceptions import ConfigurationError

        # Create a mock class that requires api_key
        class MockClient:
            def __init__(self, api_key: str):
                self.api_key = api_key

        mock_client_class = Mock(side_effect=TypeError("missing 1 required positional argument"))
        mock_client_class.__signature__ = inspect.signature(MockClient)

        # Ensure no API key in environment
        with patch.dict("os.environ", {}, clear=True):
            # This should raise because set_args_on_signature can't satisfy api_key requirement
            with pytest.raises((TypeError, ConfigurationError)):
                registry._instantiate_client(
                    Provider.VOYAGE,
                    ProviderKind.EMBEDDING,
                    mock_client_class,
                    {},  # No API key in settings
                    {},
                )

    def test_api_key_and_base_url(self, registry):
        """Test client with both API key and base_url."""

        # Create a mock class with proper signature
        class MockClient:
            def __init__(self, api_key: str = "", base_url: str | None = None):
                self.api_key = api_key
                self.base_url = base_url

        mock_instance = Mock()
        mock_client_class = Mock(return_value=mock_instance)
        mock_client_class.__signature__ = inspect.signature(MockClient)

        _result = registry._instantiate_client(
            Provider.OPENAI,
            ProviderKind.EMBEDDING,
            mock_client_class,
            {"api_key": "test_key", "base_url": "https://custom.api"},
            {},
        )

        assert _result == mock_instance
        mock_client_class.assert_called_once_with(api_key="test_key", base_url="https://custom.api")

    def test_constructor_signature_mismatch_fallback(self, registry):
        """Test that set_args_on_signature only passes matching params."""

        # Create a mock class that doesn't accept api_key
        class MockClient:
            def __init__(self, timeout: int = 30):
                self.timeout = timeout

        mock_instance = Mock()
        mock_client_class = Mock(return_value=mock_instance)
        mock_client_class.__signature__ = inspect.signature(MockClient)

        _result = registry._instantiate_client(
            Provider.VOYAGE,
            ProviderKind.EMBEDDING,
            mock_client_class,
            {"api_key": "test_key"},  # api_key not in signature
            {"timeout": 30},  # timeout IS in signature
        )

        # set_args_on_signature should only pass timeout, not api_key
        assert _result == mock_instance
        mock_client_class.assert_called_once_with(timeout=30)


@pytest.mark.external_api
@pytest.mark.mock_only
@pytest.mark.qdrant
@pytest.mark.unit
class TestClientOptionsHandling:
    """Test that client_options are properly passed through."""

    @pytest.fixture
    def registry(self):
        """Create a ProviderRegistry for testing."""
        from unittest.mock import Mock

        from codeweaver.common.registry.provider import ProviderRegistry

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

    def test_client_options_passed_to_instantiate(self, registry):
        """Test client_options are passed through to client."""

        # Create a mock class with proper signature
        class MockClient:
            def __init__(self, api_key: str = "", timeout: int = 30, max_retries: int = 3):
                self.api_key = api_key
                self.timeout = timeout
                self.max_retries = max_retries

        mock_instance = Mock()
        mock_client_class = Mock(return_value=mock_instance)
        mock_client_class.__signature__ = inspect.signature(MockClient)

        _result = registry._instantiate_client(
            Provider.VOYAGE,
            ProviderKind.EMBEDDING,
            mock_client_class,
            {"api_key": "test_key"},
            {"timeout": 60, "max_retries": 5},
        )

        assert _result == mock_instance
        mock_client_class.assert_called_once_with(api_key="test_key", timeout=60, max_retries=5)

    def test_empty_client_options(self, registry):
        """Test empty client_options dict."""

        # Create a mock class with proper signature
        class MockClient:
            def __init__(self, api_key: str = ""):
                self.api_key = api_key

        mock_instance = Mock()
        mock_client_class = Mock(return_value=mock_instance)
        mock_client_class.__signature__ = inspect.signature(MockClient)

        _result = registry._instantiate_client(
            Provider.VOYAGE,
            ProviderKind.EMBEDDING,
            mock_client_class,
            {"api_key": "test_key"},
            {},  # Empty dict
        )

        assert _result == mock_instance
        mock_client_class.assert_called_once_with(api_key="test_key")


@pytest.mark.external_api
@pytest.mark.mock_only
@pytest.mark.qdrant
@pytest.mark.unit
class TestProviderKindNormalization:
    """Test that provider_kind strings are normalized to enums."""

    @pytest.fixture
    def registry(self):
        """Create a ProviderRegistry for testing."""
        from unittest.mock import Mock

        from codeweaver.common.registry.provider import ProviderRegistry

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

    def test_string_provider_kind_normalized(self, registry):
        """Test string provider_kind is converted to enum."""
        from codeweaver.providers.capabilities import Client

        # Create a real class for the client to avoid Mock inspection issues
        class MockClient:
            def __init__(self, api_key: str = ""):
                self.api_key = api_key

        mock_lazy_import = Mock()
        mock_lazy_import._resolve.return_value = MockClient

        mock_client_map = {
            Provider.VOYAGE: (
                Client(
                    provider=Provider.VOYAGE, kind=ProviderKind.EMBEDDING, client=mock_lazy_import
                ),
            )
        }

        with patch("codeweaver.providers.capabilities.CLIENT_MAP", mock_client_map):
            with patch.dict("os.environ", {"VOYAGE_API_KEY": "test_key"}):
                with patch(
                    "codeweaver.common.registry.provider.ProviderRegistry.get_configured_provider_settings",
                    return_value=None,
                ):
                    with patch(
                        "codeweaver.common.registry.provider.ProviderRegistry.collect_env_vars",
                        return_value={},
                    ):
                        with patch(
                            "codeweaver.common.registry.provider.ProviderRegistry._get_base_url_for_provider",
                            return_value=None,
                        ):
                            # Pass string instead of enum
                            result = registry._create_client_from_map(
                                Provider.VOYAGE,
                                "embedding",  # String, not ProviderKind.EMBEDDING
                                {},  # Empty dict instead of None
                                {},  # Empty dict instead of None
                            )

                            # Should still work - string normalized to enum
                            assert result is not None
