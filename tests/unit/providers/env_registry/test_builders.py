# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for provider environment registry builder functions."""

import pytest

from codeweaver.providers.env_registry.builders import (
    httpx_env_vars,
    multi_client_provider,
    openai_compatible_provider,
    simple_api_key_provider,
)
from codeweaver.providers.env_registry.models import EnvVarConfig, ProviderEnvConfig


@pytest.mark.usefixtures("reset_provider_env_registry")
@pytest.mark.unit
class TestHttpxEnvVars:
    """Tests for httpx_env_vars() builder."""

    def test_returns_frozenset(self) -> None:
        """Test httpx_env_vars returns frozenset."""
        result = httpx_env_vars()
        assert isinstance(result, frozenset)

    def test_contains_proxy_config(self) -> None:
        """Test includes HTTP proxy configuration."""
        result = httpx_env_vars()
        keys = [key for key, _ in result]
        assert "http_proxy" in keys

    def test_contains_ssl_cert_config(self) -> None:
        """Test includes SSL certificate configuration."""
        result = httpx_env_vars()
        keys = [key for key, _ in result]
        assert "ssl_cert_file" in keys

    def test_proxy_env_var_name(self) -> None:
        """Test proxy uses HTTPS_PROXY env var."""
        result = httpx_env_vars()
        proxy_cfg = next(cfg for key, cfg in result if key == "http_proxy")
        assert proxy_cfg.env == "HTTPS_PROXY"

    def test_ssl_cert_env_var_name(self) -> None:
        """Test SSL cert uses SSL_CERT_FILE env var."""
        result = httpx_env_vars()
        ssl_cfg = next(cfg for key, cfg in result if key == "ssl_cert_file")
        assert ssl_cfg.env == "SSL_CERT_FILE"


@pytest.mark.unit
class TestOpenAICompatibleProvider:
    """Tests for openai_compatible_provider() builder."""

    def test_basic_provider(self) -> None:
        """Test basic OpenAI-compatible provider creation."""
        cfg = openai_compatible_provider("TestProvider", api_key_env="TEST_API_KEY")

        assert cfg.provider == "testprovider"
        assert "openai" in cfg.clients
        assert cfg.api_key is not None
        assert cfg.api_key.env == "TEST_API_KEY"
        assert cfg.api_key.is_secret
        assert cfg.inherits_from == "openai"

    def test_provider_name_lowercased(self) -> None:
        """Test provider name is lowercased."""
        cfg = openai_compatible_provider("DeepSeek", api_key_env="DEEPSEEK_API_KEY")
        assert cfg.provider == "deepseek"

    def test_api_key_configuration(self) -> None:
        """Test API key is properly configured."""
        cfg = openai_compatible_provider("Test", api_key_env="TEST_KEY")

        assert cfg.api_key is not None
        assert cfg.api_key.env == "TEST_KEY"
        assert cfg.api_key.variable_name == "api_key"
        assert cfg.api_key.is_secret
        assert "Test" in cfg.api_key.description

    def test_with_base_url(self) -> None:
        """Test provider with custom base URL."""
        cfg = openai_compatible_provider(
            "Test",
            api_key_env="TEST_KEY",
            base_url_env="TEST_URL",
            default_url="https://test.example.com",
        )

        assert cfg.host is not None
        assert cfg.host.env == "TEST_URL"
        assert cfg.host.default == "https://test.example.com"
        assert cfg.host.variable_name == "base_url"

    def test_without_base_url(self) -> None:
        """Test provider without base URL."""
        cfg = openai_compatible_provider("Test", api_key_env="TEST_KEY")
        assert cfg.host is None

    def test_additional_clients(self) -> None:
        """Test adding additional client names."""
        cfg = openai_compatible_provider(
            "Test", api_key_env="TEST_KEY", additional_clients=("groq", "cerebras")
        )

        assert "openai" in cfg.clients
        assert "groq" in cfg.clients
        assert "cerebras" in cfg.clients
        assert len(cfg.clients) == 3

    def test_custom_note(self) -> None:
        """Test custom provider note."""
        cfg = openai_compatible_provider("Test", api_key_env="TEST_KEY", note="Custom note text")
        assert cfg.note == "Custom note text"

    def test_default_note(self) -> None:
        """Test default provider note."""
        cfg = openai_compatible_provider("Test", api_key_env="TEST_KEY")
        assert cfg.note is not None
        assert "Test" in cfg.note
        assert "service" in cfg.note

    def test_includes_httpx_vars(self) -> None:
        """Test includes httpx environment variables."""
        cfg = openai_compatible_provider("Test", api_key_env="TEST_KEY")

        other_keys = [key for key, _ in cfg.other]
        assert "http_proxy" in other_keys
        assert "ssl_cert_file" in other_keys

    def test_extra_vars(self) -> None:
        """Test adding extra custom variables."""
        extra = {"custom": EnvVarConfig(env="CUSTOM_VAR", description="Custom")}

        cfg = openai_compatible_provider("Test", api_key_env="TEST_KEY", extra_vars=extra)

        other_keys = [key for key, _ in cfg.other]
        assert "custom" in other_keys


@pytest.mark.unit
class TestSimpleApiKeyProvider:
    """Tests for simple_api_key_provider() builder."""

    def test_basic_provider(self) -> None:
        """Test basic simple provider creation."""
        cfg = simple_api_key_provider("Voyage", client="voyage", api_key_env="VOYAGE_API_KEY")

        assert cfg.provider == "voyage"
        assert cfg.clients == ("voyage",)
        assert cfg.api_key is not None
        assert cfg.api_key.env == "VOYAGE_API_KEY"
        assert cfg.api_key.is_secret

    def test_no_inheritance(self) -> None:
        """Test simple provider has no inheritance."""
        cfg = simple_api_key_provider("Test", client="test", api_key_env="TEST_KEY")
        assert cfg.inherits_from is None

    def test_with_base_url(self) -> None:
        """Test simple provider with base URL."""
        cfg = simple_api_key_provider(
            "Test", client="test", api_key_env="TEST_KEY", base_url_env="TEST_URL"
        )

        assert cfg.host is not None
        assert cfg.host.env == "TEST_URL"

    def test_additional_vars(self) -> None:
        """Test adding additional custom variables."""
        additional = {"timeout": EnvVarConfig(env="TIMEOUT", description="Timeout")}

        cfg = simple_api_key_provider(
            "Test", client="test", api_key_env="TEST_KEY", additional_vars=additional
        )

        other_keys = [key for key, _ in cfg.other]
        assert "timeout" in other_keys

    def test_includes_httpx_vars(self) -> None:
        """Test includes httpx variables."""
        cfg = simple_api_key_provider("Test", client="test", api_key_env="TEST_KEY")

        other_keys = [key for key, _ in cfg.other]
        assert "http_proxy" in other_keys


@pytest.mark.unit
class TestMultiClientProvider:
    """Tests for multi_client_provider() builder."""

    def test_updates_provider_name(self) -> None:
        """Test updates provider name on all configs."""
        config1 = ProviderEnvConfig(
            provider="old_name",
            clients=("openai",),
            api_key=EnvVarConfig(env="KEY1", description="Key 1"),
        )
        config2 = ProviderEnvConfig(
            provider="old_name",
            clients=("cohere",),
            api_key=EnvVarConfig(env="KEY2", description="Key 2"),
        )

        result = multi_client_provider("azure", [config1, config2])

        assert len(result) == 2
        assert all(cfg.provider == "azure" for cfg in result)

    def test_preserves_other_fields(self) -> None:
        """Test preserves all other fields."""
        api_key = EnvVarConfig(env="KEY", description="Key", is_secret=True)
        host = EnvVarConfig(env="HOST", description="Host")
        custom = EnvVarConfig(env="CUSTOM", description="Custom")

        config = ProviderEnvConfig(
            provider="old",
            clients=("openai",),
            note="Test note",
            api_key=api_key,
            host=host,
            other=frozenset([("custom", custom)]),
            inherits_from="base",
        )

        result = multi_client_provider("azure", [config])

        assert len(result) == 1
        new_cfg = result[0]
        assert new_cfg.clients == ("openai",)
        assert new_cfg.note == "Test note"
        assert new_cfg.api_key == api_key
        assert new_cfg.host == host
        assert new_cfg.get_other("custom") == custom
        assert new_cfg.inherits_from == "base"

    def test_handles_multiple_configs(self) -> None:
        """Test handles multiple client configurations."""
        configs = [
            ProviderEnvConfig(
                provider="old",
                clients=("openai",),
                api_key=EnvVarConfig(env="OPENAI_KEY", description="OpenAI"),
            ),
            ProviderEnvConfig(
                provider="old",
                clients=("cohere",),
                api_key=EnvVarConfig(env="COHERE_KEY", description="Cohere"),
            ),
            ProviderEnvConfig(
                provider="old",
                clients=("anthropic",),
                api_key=EnvVarConfig(env="ANTHROPIC_KEY", description="Anthropic"),
            ),
        ]

        result = multi_client_provider("azure", configs)

        assert len(result) == 3
        assert all(cfg.provider == "azure" for cfg in result)
        assert result[0].clients == ("openai",)
        assert result[1].clients == ("cohere",)
        assert result[2].clients == ("anthropic",)

    def test_empty_list(self) -> None:
        """Test handles empty config list."""
        result = multi_client_provider("azure", [])
        assert result == []
