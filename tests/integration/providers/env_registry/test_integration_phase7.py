# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Phase 7 integration tests - Registry to Provider.other_env_vars integration."""

import pytest

from codeweaver.core.types import Provider
from codeweaver.providers.env_registry.conversion import (
    get_provider_configs,
    get_provider_env_vars_from_registry,
)


# All 31 providers from Phase 6
ALL_PROVIDERS = [
    # OpenAI-compatible (18)
    "openai",
    "deepseek",
    "fireworks",
    "together",
    "cerebras",
    "moonshot",
    "morph",
    "nebius",
    "openrouter",
    "ovhcloud",
    "sambanova",
    "groq",
    "alibaba",
    "github",
    "litellm",
    "ollama",
    "perplexity",
    "x-ai",
    # Cloud platforms (3)
    "azure",
    "heroku",
    "vercel",
    # Specialized (10)
    "voyage",
    "anthropic",
    "hf-inference",
    "bedrock",
    "cohere",
    "tavily",
    "google",
    "mistral",
    "gateway",
    "qdrant",
]


@pytest.mark.external_api
@pytest.mark.parametrize
@pytest.mark.qdrant
class TestRegistryToProviderIntegration:
    """Test registry integration with Provider.other_env_vars."""

    @pytest.mark.parametrize("provider_name", ALL_PROVIDERS)
    def test_all_providers_in_registry(self, provider_name: str) -> None:
        """Verify all 31 providers are in the registry."""
        configs = get_provider_configs(provider_name)
        assert configs is not None, f"Provider {provider_name} not found in registry"
        assert len(configs) > 0, f"Provider {provider_name} has no configurations"
        assert all(
            config.provider == provider_name for config in configs
        ), f"Provider {provider_name} config mismatch"

    @pytest.mark.parametrize("provider_name", ALL_PROVIDERS)
    def test_registry_conversion_to_env_vars(self, provider_name: str) -> None:
        """Test conversion from registry to ProviderEnvVars format."""
        env_vars = get_provider_env_vars_from_registry(provider_name)
        assert env_vars is not None, f"Provider {provider_name} conversion failed"
        assert len(env_vars) > 0, f"Provider {provider_name} has no env vars"

        # Verify structure
        for env_var in env_vars:
            assert isinstance(env_var, dict), "env_var should be a dict (ProviderEnvVars)"
            assert "client" in env_var or "api_key" in env_var or "note" in env_var, (
                f"env_var for {provider_name} missing required fields"
            )

    def test_provider_enum_uses_registry(self) -> None:
        """Test Provider enum uses registry through other_env_vars."""
        # Test a few key providers
        test_cases = [
            ("OPENAI", "OPENAI_API_KEY"),
            ("DEEPSEEK", "DEEPSEEK_API_KEY"),
            ("AZURE", "AZURE_OPENAI_API_KEY"),
            ("VOYAGE", "VOYAGE_API_KEY"),
            ("ANTHROPIC", "ANTHROPIC_API_KEY"),
            ("QDRANT", "QDRANT__SERVICE__API_KEY"),
        ]

        for provider_str, expected_env in test_cases:
            provider = getattr(Provider, provider_str)
            env_vars = provider.other_env_vars

            assert env_vars is not None, f"Provider {provider_str} has no env vars"
            assert len(env_vars) > 0, f"Provider {provider_str} has empty env vars"

            # Check that expected environment variable is present
            found = False
            for env_var_dict in env_vars:
                if "api_key" in env_var_dict and env_var_dict["api_key"].env == expected_env:
                    found = True
                    break

            assert found, f"Provider {provider_str} missing {expected_env}"

    def test_multi_config_providers(self) -> None:
        """Test providers with multiple configurations."""
        # Azure should have 3 configurations (openai, cohere, anthropic)
        azure_configs = get_provider_configs("azure")
        assert azure_configs is not None
        assert len(azure_configs) >= 3, "Azure should have at least 3 client configurations"

        # Anthropic should have 2 configurations (API key, auth token)
        anthropic_configs = get_provider_configs("anthropic")
        assert anthropic_configs is not None
        assert (
            len(anthropic_configs) >= 2
        ), "Anthropic should have at least 2 auth configurations"

        # Google should have 2 configurations (Gemini, Google)
        google_configs = get_provider_configs("google")
        assert google_configs is not None
        assert len(google_configs) >= 2, "Google should have at least 2 configurations"

    def test_inheritance_providers(self) -> None:
        """Test providers that inherit from OpenAI."""
        openai_compatible_providers = [
            "deepseek",
            "fireworks",
            "together",
            "cerebras",
            "moonshot",
            "morph",
            "nebius",
            "openrouter",
            "ovhcloud",
            "sambanova",
            "groq",
            "alibaba",
            "github",
            "litellm",
            "ollama",
            "perplexity",
            "x-ai",
        ]

        for provider_name in openai_compatible_providers:
            configs = get_provider_configs(provider_name)
            assert configs is not None, f"Provider {provider_name} not found"

            # Check that first config has inherits_from
            first_config = configs[0]
            assert (
                first_config.inherits_from == "openai"
            ), f"Provider {provider_name} should inherit from openai"

    def test_env_var_field_conversion(self) -> None:
        """Test that EnvVarConfig fields are properly converted to EnvVarInfo."""
        # Test OPENAI which has comprehensive fields
        env_vars = get_provider_env_vars_from_registry("openai")
        assert env_vars is not None
        openai_vars = env_vars[0]

        # Check api_key field conversion
        assert "api_key" in openai_vars
        api_key_info = openai_vars["api_key"]
        assert api_key_info.env == "OPENAI_API_KEY"
        assert api_key_info.is_secret is True
        assert api_key_info.variable_name == "api_key"

        # Check log_level field with choices
        assert "log_level" in openai_vars
        log_level_info = openai_vars["log_level"]
        assert log_level_info.env == "OPENAI_LOG"
        assert log_level_info.choices is not None
        assert "debug" in log_level_info.choices

    def test_other_field_conversion(self) -> None:
        """Test that 'other' frozenset[tuple] is converted to dict."""
        # OPENAI has 'other' fields
        env_vars = get_provider_env_vars_from_registry("openai")
        assert env_vars is not None
        openai_vars = env_vars[0]

        if "other" in openai_vars:
            other_dict = openai_vars["other"]
            assert isinstance(other_dict, dict), "'other' should be converted to dict"

            # Check httpx proxy vars are present
            if "http_proxy" in other_dict:
                proxy_info = other_dict["http_proxy"]
                assert proxy_info.env == "HTTPS_PROXY"

    def test_backward_compatibility(self) -> None:
        """Test that Provider.other_env_vars maintains backward compatibility."""
        # For providers not in registry, should fall back to hardcoded
        # Memory provider is not in registry (it's a special case)
        memory_provider = Provider.MEMORY
        memory_env_vars = memory_provider.other_env_vars

        # Should not crash, even if None
        assert memory_env_vars is None or isinstance(memory_env_vars, tuple)


@pytest.mark.external_api
@pytest.mark.parametrize
@pytest.mark.qdrant
class TestSpecificProviderConfigurations:
    """Test specific provider configurations for correctness."""

    def test_qdrant_tls_configuration(self) -> None:
        """Test Qdrant TLS and logging configuration."""
        configs = get_provider_configs("qdrant")
        assert configs is not None
        qdrant_config = configs[0]

        assert qdrant_config.tls_on_off is not None
        assert qdrant_config.tls_cert_path is not None
        assert qdrant_config.tls_key_path is not None
        assert qdrant_config.log_level is not None

        # Convert to env vars and check
        env_vars = get_provider_env_vars_from_registry("qdrant")
        assert env_vars is not None
        qdrant_vars = env_vars[0]

        assert qdrant_vars["tls_on_off"].env == "QDRANT__SERVICE__ENABLE_TLS"
        assert qdrant_vars["tls_cert_path"].env == "QDRANT__TLS__CERT"
        assert qdrant_vars["log_level"].env == "QDRANT__LOG_LEVEL"

    def test_bedrock_aws_configuration(self) -> None:
        """Test Bedrock AWS-specific configuration."""
        configs = get_provider_configs("bedrock")
        assert configs is not None
        bedrock_config = configs[0]

        assert bedrock_config.region is not None
        assert bedrock_config.account_id is not None
        assert bedrock_config.api_key is not None  # AWS_SECRET_ACCESS_KEY

        # Check clients
        assert "bedrock" in bedrock_config.clients
        assert "anthropic" in bedrock_config.clients

    def test_azure_multi_client_configuration(self) -> None:
        """Test Azure multi-client configuration."""
        configs = get_provider_configs("azure")
        assert configs is not None
        assert len(configs) == 3

        # Check OpenAI client config
        openai_config = next(c for c in configs if "openai" in c.clients)
        assert openai_config.api_key is not None
        assert openai_config.api_key.env == "AZURE_OPENAI_API_KEY"
        assert openai_config.endpoint is not None
        assert openai_config.region is not None

        # Check Cohere client config
        cohere_config = next(c for c in configs if "cohere" in c.clients)
        assert cohere_config.api_key is not None
        assert cohere_config.api_key.env == "AZURE_COHERE_API_KEY"

        # Check Anthropic client config
        anthropic_config = next(c for c in configs if "anthropic" in c.clients)
        assert anthropic_config.api_key is not None
        assert anthropic_config.api_key.env == "ANTHROPIC_FOUNDRY_API_KEY"

    def test_heroku_model_id_configuration(self) -> None:
        """Test Heroku model_id in 'other' field."""
        configs = get_provider_configs("heroku")
        assert configs is not None
        heroku_config = configs[0]

        # Should have model_id in other
        assert heroku_config.other is not None
        assert len(heroku_config.other) > 0

        # Find model_id in other
        model_id_config = next((conf for key, conf in heroku_config.other if key == "model_id"), None)
        assert model_id_config is not None
        assert model_id_config.env == "INFERENCE_MODEL_ID"

    def test_vercel_multiple_auth_methods(self) -> None:
        """Test Vercel API key and OIDC token configurations."""
        configs = get_provider_configs("vercel")
        assert configs is not None
        assert len(configs) == 2

        # Check API key config
        api_key_config = next(
            c for c in configs if c.api_key and c.api_key.env == "VERCEL_AI_GATEWAY_API_KEY"
        )
        assert api_key_config is not None

        # Check OIDC token config
        oidc_config = next(c for c in configs if c.api_key and c.api_key.env == "VERCEL_OIDC_TOKEN")
        assert oidc_config is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
