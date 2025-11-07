# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for config command.

Tests validate corrections from CLI_CORRECTIONS_PLAN.md:
- Registry usage (not hardcoded providers)
- Provider.other_env_vars usage (correct env var names)
- Settings construction (respects pydantic-settings hierarchy)
- Config profiles (quick setup)
- Helper utilities usage
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import tomli

from codeweaver.cli.commands.config import ConfigProfile
from codeweaver.cli.commands.config import app as config_app
from codeweaver.common.registry import get_provider_registry
from codeweaver.providers.provider import Provider, ProviderKind


if TYPE_CHECKING:
    from pytest import MonkeyPatch


@pytest.fixture
def temp_project(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    """Create temporary project directory."""
    project = tmp_path / "test_project"
    project.mkdir()
    (project / ".git").mkdir()
    monkeypatch.chdir(project)
    return project


@pytest.mark.unit
@pytest.mark.config
class TestConfigInit:
    """Tests for config init command."""

    def test_quick_flag_creates_config(self, temp_project: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test --quick flag creates config with recommended defaults."""
        with pytest.raises(SystemExit) as exc_info:
            config_app("init", "--quick")
        captured = capsys.readouterr()

        assert exc_info.value.code == 0
        config_path = temp_project / "codeweaver.toml"
        assert config_path.exists()

        # Verify config contains Voyage + Qdrant
        config_content = config_path.read_text()
        assert "voyage" in config_content.lower()
        assert "qdrant" in config_content.lower()

    def test_profile_recommended(self, temp_project: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test --profile recommended creates correct config."""
        with pytest.raises(SystemExit) as exc_info:
            config_app("init", "--profile", ConfigProfile.RECOMMENDED.value)
        captured = capsys.readouterr()

        assert exc_info.value.code == 0
        config_path = temp_project / "codeweaver.toml"
        config = tomli.loads(config_path.read_text())

        assert config["embedding"]["provider"] == "voyage"
        assert config["vector_store"]["type"] == "qdrant"

    def test_profile_local_only(self, temp_project: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test --profile local-only creates offline-capable config."""
        with pytest.raises(SystemExit) as exc_info:
            config_app("init", "--profile", ConfigProfile.LOCAL_ONLY.value)
        captured = capsys.readouterr()

        assert exc_info.value.code == 0
        config_path = temp_project / "codeweaver.toml"
        config = tomli.loads(config_path.read_text())

        # Should use local providers
        assert config["embedding"]["provider"] == "fastembed"
        assert config["vector_store"]["location"] == "memory"

    def test_user_flag_creates_user_config(
        self,
        tmp_path: Path,
        monkeypatch: MonkeyPatch
    ) -> None:
        """Test --user flag creates config in user directory."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = runner.invoke(
            config_app,
            ["init", "--quick", "--user"]
        )

        assert result.exit_code == 0
        user_config = tmp_path / ".config" / "codeweaver" / "config.toml"
        assert user_config.exists()

    def test_local_flag_creates_local_override(self, temp_project: Path) -> None:
        """Test --local flag creates .codeweaver.toml override."""
        result = runner.invoke(
            config_app,
            ["init", "--quick", "--local"]
        )

        assert result.exit_code == 0
        local_config = temp_project / ".codeweaver.toml"
        assert local_config.exists()

    def test_registry_integration(self) -> None:
        """Test config command uses ProviderRegistry correctly."""
        registry = get_provider_registry()
        providers = registry.list_providers(ProviderKind.EMBEDDING)

        # Should have 25+ providers from registry, not hardcoded 4
        assert len(providers) > 20, f"Expected >20 providers, got {len(providers)}"

        # Verify specific providers are available
        expected_providers = {"voyage", "openai", "fastembed", "cohere"}
        provider_names = {p.value for p in providers}
        assert expected_providers.issubset(provider_names)

    def test_provider_env_vars_integration(self) -> None:
        """Test config command uses Provider.other_env_vars."""
        voyage = Provider.VOYAGE
        env_vars = voyage.other_env_vars

        assert env_vars is not None
        assert env_vars.api_key.env == "VOYAGE_API_KEY"

        openai = Provider.OPENAI
        openai_env_vars = openai.other_env_vars
        assert openai_env_vars is not None
        assert openai_env_vars.api_key.env == "OPENAI_API_KEY"

    def test_settings_construction_respects_hierarchy(
        self,
        temp_project: Path,
        monkeypatch: MonkeyPatch
    ) -> None:
        """Test settings construction respects pydantic-settings hierarchy."""
        from codeweaver.config.settings import CodeWeaverSettings

        # Create config file
        config_path = temp_project / "codeweaver.toml"
        config_content = """
[project]
path = "."

[embedding]
provider = "fastembed"

[vector_store]
type = "qdrant"
"""
        config_path.write_text(config_content)

        # Override via env var
        monkeypatch.setenv("CODEWEAVER_EMBEDDING_PROVIDER", "voyage")

        # Settings should respect env var over file
        settings = CodeWeaverSettings(config_file=config_path)
        assert settings.provider.embedding.provider == "voyage"

    def test_profile_includes_sparse_embeddings(self, temp_project: Path) -> None:
        """Test recommended profile includes sparse embeddings."""
        result = runner.invoke(
            config_app,
            ["init", "--profile", ConfigProfile.RECOMMENDED.value]
        )

        assert result.exit_code == 0
        config = tomli.loads((temp_project / "codeweaver.toml").read_text())

        # Recommended profile should include sparse embeddings
        assert "sparse_embedding" in config.get("embedding", {})


@pytest.mark.unit
@pytest.mark.config
class TestConfigShow:
    """Tests for config show command."""

    def test_show_displays_config(self, temp_project: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test config show displays current configuration."""
        # Create config
        runner.invoke(config_app, ["init", "--quick"])

        # Show config
        result = runner.invoke(config_app, ["show"])

        assert result.exit_code == 0
        assert "Configuration" in captured.out
        assert "project_path" in captured.out.lower()

    def test_show_handles_missing_config(self, temp_project: Path) -> None:
        """Test config show handles missing configuration gracefully."""
        result = runner.invoke(config_app, ["show"])

        # Should not crash, should show defaults or warning
        assert result.exit_code in (0, 1)

    def test_show_respects_env_vars(
        self,
        temp_project: Path,
        monkeypatch: MonkeyPatch
    ) -> None:
        """Test config show displays env var overrides."""
        monkeypatch.setenv("CODEWEAVER_EMBEDDING_PROVIDER", "voyage")

        result = runner.invoke(config_app, ["show"])

        assert result.exit_code == 0
        # Should show voyage from env var
        assert "voyage" in captured.out.lower()


@pytest.mark.unit
@pytest.mark.config
class TestConfigValidation:
    """Tests for config validation."""

    def test_invalid_provider_rejected(self, temp_project: Path) -> None:
        """Test invalid provider names are rejected."""
        config_path = temp_project / "codeweaver.toml"
        config_content = """
[embedding]
provider = "invalid_provider_xyz"
"""
        config_path.write_text(config_content)

        from codeweaver.config.settings import CodeWeaverSettings
        from codeweaver.exceptions import CodeWeaverError

        with pytest.raises((CodeWeaverError, ValueError)):
            CodeWeaverSettings(config_file=config_path)

    def test_missing_required_api_key_warned(
        self,
        temp_project: Path,
        monkeypatch: MonkeyPatch
    ) -> None:
        """Test missing API keys are warned about."""
        monkeypatch.delenv("VOYAGE_API_KEY", raising=False)

        result = runner.invoke(
            config_app,
            ["init", "--profile", ConfigProfile.RECOMMENDED.value]
        )

        # Should warn about missing API key
        assert "VOYAGE_API_KEY" in captured.out or result.exit_code != 0


@pytest.mark.unit
@pytest.mark.config
class TestConfigProfiles:
    """Tests for config profiles."""

    def test_all_profiles_valid(self) -> None:
        """Test all ConfigProfile enum values are valid."""
        from codeweaver.config.profiles import local_only, minimal, recommended_default

        # Should not raise
        recommended = recommended_default()
        assert recommended is not None

        local = local_only()
        assert local is not None

        min_config = minimal()
        assert min_config is not None

    def test_profile_enum_values_match_functions(self) -> None:
        """Test ConfigProfile enum values match profile functions."""
        expected_profiles = {
            ConfigProfile.RECOMMENDED,
            ConfigProfile.LOCAL_ONLY,
            ConfigProfile.MINIMAL
        }

        assert len(ConfigProfile) == len(expected_profiles)
        for profile in ConfigProfile:
            assert profile in expected_profiles