# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for provider environment registry models."""

import dataclasses

import pytest

from codeweaver.core.types.env import EnvFormat, VariableInfo
from codeweaver.providers.env_registry.models import EnvVarConfig, ProviderEnvConfig


@pytest.mark.unit
class TestEnvVarConfig:
    """Tests for EnvVarConfig dataclass."""

    def test_basic_creation(self) -> None:
        """Test basic EnvVarConfig creation."""
        cfg = EnvVarConfig(env="TEST_KEY", description="Test API Key")
        assert cfg.env == "TEST_KEY"
        assert cfg.description == "Test API Key"
        assert not cfg.is_secret
        assert cfg.variable_name is None
        assert cfg.variables is None
        assert cfg.fmt is None
        assert cfg.choices is None
        assert cfg.default is None

    def test_full_creation(self) -> None:
        """Test EnvVarConfig with all fields."""
        cfg = EnvVarConfig(
            env="TEST_KEY",
            description="Test API Key",
            variable_name="api_key",
            variables=(VariableInfo(variable="key", dest="client"),),
            is_secret=True,
            fmt=EnvFormat.STRING,
            choices=frozenset({"a", "b", "c"}),
            default="a",
        )
        assert cfg.env == "TEST_KEY"
        assert cfg.description == "Test API Key"
        assert cfg.variable_name == "api_key"
        assert len(cfg.variables) == 1
        assert cfg.is_secret
        assert cfg.fmt == EnvFormat.STRING
        assert cfg.choices == frozenset({"a", "b", "c"})
        assert cfg.default == "a"

    def test_immutable(self) -> None:
        """Test EnvVarConfig is immutable."""
        cfg = EnvVarConfig(env="TEST", description="Test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.env = "CHANGED"  # type: ignore[misc]

    def test_choices_as_frozenset(self) -> None:
        """Test choices must be frozenset for immutability."""
        cfg = EnvVarConfig(
            env="TEST", description="Test", choices=frozenset({"debug", "info", "warning"})
        )
        assert isinstance(cfg.choices, frozenset)
        assert "debug" in cfg.choices

    def test_validation_disabled_by_default(self) -> None:
        """Test validation only runs with DEBUG_PROVIDER_VALIDATION."""
        # Should not raise even with empty env (no validation by default)
        cfg = EnvVarConfig(env="", description="Test")
        assert cfg.env == ""

    @pytest.mark.skipif(not __debug__, reason="Validation only runs in debug mode")
    def test_validation_with_debug_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test validation runs with DEBUG_PROVIDER_VALIDATION set."""
        monkeypatch.setenv("DEBUG_PROVIDER_VALIDATION", "1")

        with pytest.raises(ValueError, match="env cannot be empty"):
            EnvVarConfig(env="", description="Test")


@pytest.mark.unit
class TestProviderEnvConfig:
    """Tests for ProviderEnvConfig dataclass."""

    def test_minimal_creation(self) -> None:
        """Test minimal ProviderEnvConfig creation."""
        cfg = ProviderEnvConfig(provider="test", clients=("test_client",))
        assert cfg.provider == "test"
        assert cfg.clients == ("test_client",)
        assert cfg.note is None
        assert cfg.api_key is None
        assert len(cfg.other) == 0

    def test_with_standard_fields(self) -> None:
        """Test ProviderEnvConfig with standard fields."""
        api_key = EnvVarConfig(env="TEST_KEY", description="Key", is_secret=True)
        host = EnvVarConfig(env="TEST_HOST", description="Host")

        cfg = ProviderEnvConfig(
            provider="test", clients=("test_client",), api_key=api_key, host=host
        )

        assert cfg.api_key == api_key
        assert cfg.host == host

    def test_with_other_fields(self) -> None:
        """Test ProviderEnvConfig with custom 'other' fields."""
        custom_var = EnvVarConfig(env="CUSTOM", description="Custom")

        cfg = ProviderEnvConfig(
            provider="test", clients=("test_client",), other=frozenset([("custom", custom_var)])
        )

        assert len(cfg.other) == 1
        assert cfg.get_other("custom") == custom_var
        assert cfg.get_other("nonexistent") is None

    def test_all_vars_includes_standard_and_other(self) -> None:
        """Test all_vars() includes both standard and 'other' fields."""
        api_key = EnvVarConfig(env="API_KEY", description="Key")
        custom = EnvVarConfig(env="CUSTOM", description="Custom")

        cfg = ProviderEnvConfig(
            provider="test",
            clients=("test_client",),
            api_key=api_key,
            other=frozenset([("custom", custom)]),
        )

        all_vars = cfg.all_vars()
        assert len(all_vars) == 2
        assert api_key in all_vars
        assert custom in all_vars

    def test_all_vars_returns_tuple(self) -> None:
        """Test all_vars() returns immutable tuple."""
        cfg = ProviderEnvConfig(
            provider="test",
            clients=("test_client",),
            api_key=EnvVarConfig(env="KEY", description="Key"),
        )

        all_vars = cfg.all_vars()
        assert isinstance(all_vars, tuple)

    def test_inheritance(self) -> None:
        """Test inheritance configuration."""
        cfg = ProviderEnvConfig(provider="test", clients=("test_client",), inherits_from="base")

        assert cfg.inherits_from == "base"

    def test_multi_client(self) -> None:
        """Test multi-client configuration."""
        cfg = ProviderEnvConfig(provider="test", clients=("openai", "anthropic", "cohere"))

        assert len(cfg.clients) == 3
        assert "openai" in cfg.clients
        assert "anthropic" in cfg.clients

    def test_to_dict_basic(self) -> None:
        """Test to_dict() serialization - basic."""
        cfg = ProviderEnvConfig(provider="test", clients=("test_client",), note="Test provider")

        result = cfg.to_dict()
        assert result["provider"] == "test"
        assert result["clients"] == ["test_client"]
        assert result["note"] == "Test provider"

    def test_to_dict_with_fields(self) -> None:
        """Test to_dict() serialization - with fields."""
        api_key = EnvVarConfig(
            env="TEST_KEY", description="Key", is_secret=True, variable_name="api_key"
        )

        cfg = ProviderEnvConfig(provider="test", clients=("test_client",), api_key=api_key)

        result = cfg.to_dict()
        assert "api_key" in result
        assert result["api_key"]["env"] == "TEST_KEY"
        assert result["api_key"]["is_secret"]
        assert result["api_key"]["variable_name"] == "api_key"

    def test_to_dict_with_other(self) -> None:
        """Test to_dict() serialization - with 'other' fields."""
        custom = EnvVarConfig(env="CUSTOM", description="Custom field")

        cfg = ProviderEnvConfig(
            provider="test", clients=("test_client",), other=frozenset([("custom_field", custom)])
        )

        result = cfg.to_dict()
        assert "other" in result
        assert "custom_field" in result["other"]
        assert result["other"]["custom_field"]["env"] == "CUSTOM"

    def test_to_dict_with_inheritance(self) -> None:
        """Test to_dict() includes inheritance."""
        cfg = ProviderEnvConfig(provider="test", clients=("test_client",), inherits_from="base")

        result = cfg.to_dict()
        assert result["inherits_from"] == "base"

    def test_immutable(self) -> None:
        """Test ProviderEnvConfig is immutable."""
        cfg = ProviderEnvConfig(provider="test", clients=("test_client",))
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.provider = "changed"  # type: ignore[misc]

    def test_all_standard_fields(self) -> None:
        """Test ProviderEnvConfig with all standard fields."""
        cfg = ProviderEnvConfig(
            provider="test",
            clients=("test_client",),
            api_key=EnvVarConfig(env="KEY", description="Key"),
            host=EnvVarConfig(env="HOST", description="Host"),
            endpoint=EnvVarConfig(env="ENDPOINT", description="Endpoint"),
            region=EnvVarConfig(env="REGION", description="Region"),
            port=EnvVarConfig(env="PORT", description="Port"),
            log_level=EnvVarConfig(env="LOG", description="Log Level"),
            account_id=EnvVarConfig(env="ACCOUNT", description="Account"),
            tls_on_off=EnvVarConfig(env="TLS", description="TLS"),
            tls_cert_path=EnvVarConfig(env="CERT", description="Cert"),
            tls_key_path=EnvVarConfig(env="KEY_PATH", description="Key Path"),
        )

        all_vars = cfg.all_vars()
        assert len(all_vars) == 10  # All standard fields
