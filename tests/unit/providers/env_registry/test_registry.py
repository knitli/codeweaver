# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for provider environment registry."""

import pytest

from codeweaver.providers.env_registry.models import EnvVarConfig, ProviderEnvConfig
from codeweaver.providers.env_registry.registry import ProviderEnvRegistry


@pytest.fixture(autouse=True)
def reset_registry() -> None:
    """Reset registry before each test."""
    ProviderEnvRegistry._reset()


@pytest.mark.unit
class TestProviderEnvRegistry:
    """Tests for ProviderEnvRegistry."""

    def test_register_single_config(self) -> None:
        """Test registering a single provider config."""
        cfg = ProviderEnvConfig(
            provider="test",
            clients=("test",),
            api_key=EnvVarConfig(env="TEST_KEY", description="Key"),
        )

        ProviderEnvRegistry.register("test", cfg)
        result = ProviderEnvRegistry.get("test")

        assert len(result) == 1
        assert result[0] == cfg

    def test_register_list_of_configs(self) -> None:
        """Test registering multiple configs for one provider."""
        cfg1 = ProviderEnvConfig(
            provider="test",
            clients=("openai",),
            api_key=EnvVarConfig(env="KEY1", description="Key 1"),
        )
        cfg2 = ProviderEnvConfig(
            provider="test",
            clients=("cohere",),
            api_key=EnvVarConfig(env="KEY2", description="Key 2"),
        )

        ProviderEnvRegistry.register("test", [cfg1, cfg2])
        result = ProviderEnvRegistry.get("test")

        assert len(result) == 2
        assert cfg1 in result
        assert cfg2 in result

    def test_get_nonexistent_provider(self) -> None:
        """Test getting nonexistent provider returns empty list."""
        result = ProviderEnvRegistry.get("nonexistent")
        assert result == []

    def test_get_case_insensitive(self) -> None:
        """Test provider name lookup is case-insensitive."""
        cfg = ProviderEnvConfig(
            provider="test", clients=("test",), api_key=EnvVarConfig(env="KEY", description="Key")
        )

        ProviderEnvRegistry.register("test", cfg)

        assert ProviderEnvRegistry.get("test") == [cfg]
        assert ProviderEnvRegistry.get("TEST") == [cfg]
        assert ProviderEnvRegistry.get("Test") == [cfg]

    def test_external_registration(self) -> None:
        """Test external provider registration."""
        cfg = ProviderEnvConfig(
            provider="custom",
            clients=("custom",),
            api_key=EnvVarConfig(env="CUSTOM_KEY", description="Custom"),
        )

        ProviderEnvRegistry.register("custom", cfg, external=True)
        result = ProviderEnvRegistry.get("custom")

        assert len(result) == 1
        assert result[0] == cfg

    def test_external_registration_conflict(self) -> None:
        """Test external registration conflicts with built-in provider."""
        # Register built-in provider
        cfg1 = ProviderEnvConfig(
            provider="test",
            clients=("test",),
            api_key=EnvVarConfig(env="KEY1", description="Built-in"),
        )
        ProviderEnvRegistry.register("test", cfg1)

        # Attempt to register external with same name
        cfg2 = ProviderEnvConfig(
            provider="test",
            clients=("test",),
            api_key=EnvVarConfig(env="KEY2", description="External"),
        )

        with pytest.raises(ValueError, match="conflicts with built-in provider"):
            ProviderEnvRegistry.register("test", cfg2, external=True)

    def test_inheritance_resolution(self) -> None:
        """Test inheritance resolution includes parent configs."""
        parent = ProviderEnvConfig(
            provider="parent",
            clients=("parent",),
            api_key=EnvVarConfig(env="PARENT_KEY", description="Parent"),
        )
        child = ProviderEnvConfig(
            provider="child",
            clients=("child",),
            api_key=EnvVarConfig(env="CHILD_KEY", description="Child"),
            inherits_from="parent",
        )

        ProviderEnvRegistry.register("parent", parent)
        ProviderEnvRegistry.register("child", child)

        result = ProviderEnvRegistry.get("child")

        assert len(result) == 2
        assert parent in result
        assert child in result
        # Parent should come before child
        assert result.index(parent) < result.index(child)

    def test_no_inheritance(self) -> None:
        """Test provider without inheritance."""
        cfg = ProviderEnvConfig(
            provider="test", clients=("test",), api_key=EnvVarConfig(env="KEY", description="Key")
        )

        ProviderEnvRegistry.register("test", cfg)
        result = ProviderEnvRegistry.get("test")

        assert len(result) == 1
        assert result[0] == cfg

    def test_get_api_key_envs(self) -> None:
        """Test get_api_key_envs returns API key env var names."""
        cfg = ProviderEnvConfig(
            provider="test",
            clients=("test",),
            api_key=EnvVarConfig(env="TEST_API_KEY", description="Key"),
        )

        ProviderEnvRegistry.register("test", cfg)
        result = ProviderEnvRegistry.get_api_key_envs("test")

        assert result == ("TEST_API_KEY",)

    def test_get_api_key_envs_no_api_key(self) -> None:
        """Test get_api_key_envs with provider that has no API key."""
        cfg = ProviderEnvConfig(provider="test", clients=("test",))

        ProviderEnvRegistry.register("test", cfg)
        result = ProviderEnvRegistry.get_api_key_envs("test")

        assert result == ()

    def test_get_api_key_envs_cached(self) -> None:
        """Test get_api_key_envs is cached."""
        cfg = ProviderEnvConfig(
            provider="test", clients=("test",), api_key=EnvVarConfig(env="KEY", description="Key")
        )

        ProviderEnvRegistry.register("test", cfg)

        # First call
        result1 = ProviderEnvRegistry.get_api_key_envs("test")
        # Second call (should be cached)
        result2 = ProviderEnvRegistry.get_api_key_envs("test")

        assert result1 == result2
        assert result1 is result2  # Same object (cached)

    def test_get_for_client(self) -> None:
        """Test get_for_client filters by client name."""
        cfg1 = ProviderEnvConfig(
            provider="test",
            clients=("openai",),
            api_key=EnvVarConfig(env="KEY1", description="Key 1"),
        )
        cfg2 = ProviderEnvConfig(
            provider="test",
            clients=("cohere",),
            api_key=EnvVarConfig(env="KEY2", description="Key 2"),
        )

        ProviderEnvRegistry.register("test", [cfg1, cfg2])

        openai_configs = ProviderEnvRegistry.get_for_client("test", "openai")
        cohere_configs = ProviderEnvRegistry.get_for_client("test", "cohere")

        assert len(openai_configs) == 1
        assert openai_configs[0] == cfg1

        assert len(cohere_configs) == 1
        assert cohere_configs[0] == cfg2

    def test_get_for_client_multiple_clients(self) -> None:
        """Test config with multiple clients matches any of them."""
        cfg = ProviderEnvConfig(
            provider="test",
            clients=("openai", "anthropic", "cohere"),
            api_key=EnvVarConfig(env="KEY", description="Key"),
        )

        ProviderEnvRegistry.register("test", cfg)

        assert ProviderEnvRegistry.get_for_client("test", "openai") == (cfg,)
        assert ProviderEnvRegistry.get_for_client("test", "anthropic") == (cfg,)
        assert ProviderEnvRegistry.get_for_client("test", "cohere") == (cfg,)

    def test_all_providers(self) -> None:
        """Test all_providers returns all registered provider names."""
        cfg1 = ProviderEnvConfig(provider="test1", clients=("test1",))
        cfg2 = ProviderEnvConfig(provider="test2", clients=("test2",))
        cfg3 = ProviderEnvConfig(provider="test3", clients=("test3",))

        ProviderEnvRegistry.register("test1", cfg1)
        ProviderEnvRegistry.register("test2", cfg2)
        ProviderEnvRegistry.register("test3", cfg3)

        providers = ProviderEnvRegistry.all_providers()

        # Auto-initialization adds built-in providers; check test providers are included
        assert "test1" in providers
        assert "test2" in providers
        assert "test3" in providers
        # Should be sorted
        assert providers == tuple(sorted(providers))

    def test_all_configs(self) -> None:
        """Test all_configs returns all registered configs."""
        cfg1 = ProviderEnvConfig(provider="test1", clients=("test1",))
        cfg2 = ProviderEnvConfig(provider="test2", clients=("test2",))

        ProviderEnvRegistry.register("test1", cfg1)
        ProviderEnvRegistry.register("test2", cfg2)

        all_configs = ProviderEnvRegistry.all_configs()

        # Auto-initialization adds built-in providers; check test providers are included
        assert "test1" in all_configs
        assert "test2" in all_configs
        assert all_configs["test1"] == [cfg1]
        assert all_configs["test2"] == [cfg2]

    def test_to_dict(self) -> None:
        """Test to_dict exports configs as dictionaries."""
        cfg = ProviderEnvConfig(
            provider="test",
            clients=("test",),
            api_key=EnvVarConfig(env="KEY", description="Key", is_secret=True),
        )

        ProviderEnvRegistry.register("test", cfg)
        result = ProviderEnvRegistry.to_dict()

        assert "test" in result
        assert isinstance(result["test"], list)
        assert len(result["test"]) == 1
        assert isinstance(result["test"][0], dict)
        assert result["test"][0]["provider"] == "test"
        assert "api_key" in result["test"][0]

    def test_lazy_initialization(self) -> None:
        """Test registry initializes lazily."""
        assert not ProviderEnvRegistry._initialized

        # Access should trigger initialization
        ProviderEnvRegistry.all_providers()

        assert ProviderEnvRegistry._initialized

    def test_thread_safe_initialization(self) -> None:
        """Test initialization is thread-safe (single init)."""
        # This test verifies _ensure_initialized() only runs once
        # even if called multiple times

        assert not ProviderEnvRegistry._initialized

        ProviderEnvRegistry._ensure_initialized()
        assert ProviderEnvRegistry._initialized

        # Second call should be no-op
        ProviderEnvRegistry._ensure_initialized()
        assert ProviderEnvRegistry._initialized

    def test_reset(self) -> None:
        """Test _reset clears registry and caches."""
        cfg = ProviderEnvConfig(
            provider="test", clients=("test",), api_key=EnvVarConfig(env="KEY", description="Key")
        )

        ProviderEnvRegistry.register("test", cfg)
        assert ProviderEnvRegistry.get("test") == [cfg]

        ProviderEnvRegistry._reset()

        assert not ProviderEnvRegistry._initialized
        assert ProviderEnvRegistry.get("test") == []
