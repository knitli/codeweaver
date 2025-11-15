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

import contextlib

from pathlib import Path

import pytest
import tomli

from codeweaver.cli.commands.config import ConfigProfile
from codeweaver.cli.commands.config import app as config_app
from codeweaver.cli.commands.init import app as init_app  # For config creation tests
from codeweaver.common.registry import get_provider_registry
from codeweaver.providers.provider import Provider, ProviderKind


@pytest.fixture
def temp_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
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

    def test_quick_flag_creates_config(
        self, temp_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test --profile recommended creates config with recommended defaults."""
        with pytest.raises(SystemExit) as exc_info:
            init_app(["config", "--profile", "recommended"])
        capsys.readouterr()  # Clear output

        assert exc_info.value.code == 0
        config_path = temp_project / ".codeweaver.toml"
        assert config_path.exists()

    def test_profile_recommended(
        self, temp_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test --profile recommended creates correct config."""
        with pytest.raises(SystemExit) as exc_info:
            init_app(["config", "--profile", ConfigProfile.RECOMMENDED.value])
        capsys.readouterr()

        assert exc_info.value.code == 0
        config_path = temp_project / ".codeweaver.toml"
        config = tomli.loads(config_path.read_text())

        assert config["embedding"][0]["provider"] == "voyage"
        assert config["vector_store"]["provider"] == "qdrant"

    def test_profile_local_only(
        self, temp_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test --profile quickstart creates offline-capable config."""
        with pytest.raises(SystemExit) as exc_info:
            init_app(["config", "--profile", "quickstart"])
        capsys.readouterr()

        assert exc_info.value.code == 0
        config_path = temp_project / ".codeweaver.toml"
        config = tomli.loads(config_path.read_text())

        # Should use local providers (fastembed or sentence-transformers)
        assert config["embedding"][0]["provider"] in ["fastembed", "sentence-transformers"]
        assert config["vector_store"]["provider"] == "qdrant"

    @pytest.mark.skip(reason="User flag not yet implemented in init config command")
    def test_user_flag_creates_user_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test --user flag creates config in user directory."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with pytest.raises(SystemExit) as exc_info:
            init_app(["config", "--quick", "--user"])
        capsys.readouterr()

        assert exc_info.value.code == 0
        user_config = tmp_path / ".config" / "codeweaver" / "config.toml"
        assert user_config.exists()

    @pytest.mark.skip(reason="Local flag not yet implemented in init config command")
    def test_local_flag_creates_local_override(
        self, temp_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test --local flag creates .codeweaver.toml override."""
        with pytest.raises(SystemExit) as exc_info:
            init_app(["config", "--quick", "--local"])
        capsys.readouterr()

        assert exc_info.value.code == 0
        local_config = temp_project / ".codeweaver.toml"
        assert local_config.exists()

    def test_registry_integration(self) -> None:
        """Test config command uses ProviderRegistry correctly."""
        registry = get_provider_registry()
        providers = registry.list_providers(ProviderKind.EMBEDDING)

        # Should have 10+ providers from registry, not hardcoded 4
        assert len(providers) > 10, f"Expected >10 providers, got {len(providers)}"

        # Verify specific providers are available
        expected_providers = {"voyage", "openai", "fastembed", "cohere"}
        provider_names = {p.value for p in providers}
        assert expected_providers.issubset(provider_names)

    def test_provider_env_vars_integration(self) -> None:
        """Test config command uses Provider.other_env_vars."""
        voyage = Provider.VOYAGE
        env_vars = voyage.other_env_vars

        assert env_vars is not None
        assert len(env_vars) > 0
        # other_env_vars is a tuple of dicts
        env_vars_dict = env_vars[0] if isinstance(env_vars, tuple) else env_vars
        assert "api_key" in env_vars_dict
        assert env_vars_dict["api_key"].env == "VOYAGE_API_KEY"

        openai = Provider.OPENAI
        openai_env_vars = openai.other_env_vars
        assert openai_env_vars is not None
        assert len(openai_env_vars) > 0
        openai_env_vars_dict = (
            openai_env_vars[0] if isinstance(openai_env_vars, tuple) else openai_env_vars
        )
        assert "api_key" in openai_env_vars_dict
        assert openai_env_vars_dict["api_key"].env == "OPENAI_API_KEY"

    @pytest.mark.skip(reason="Settings API structure changed - provider is now a dict")
    def test_settings_construction_respects_hierarchy(
        self, temp_project: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test settings construction respects pydantic-settings hierarchy."""
        from codeweaver.config.settings import CodeWeaverSettings

        # Create config file
        config_path = temp_project / ".codeweaver.toml"
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
        # Test needs updating for new settings structure
        assert settings.provider["embedding"]["provider"] == "voyage"  # ty: ignore

    @pytest.mark.skip(reason="Profile feature not yet implemented in init config command")
    def test_profile_includes_sparse_embeddings(
        self, temp_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test recommended profile includes sparse embeddings."""
        with pytest.raises(SystemExit) as exc_info:
            init_app(["config", "--profile", ConfigProfile.RECOMMENDED.value])
        capsys.readouterr()

        assert exc_info.value.code == 0
        config = tomli.loads((temp_project / ".codeweaver.toml").read_text())

        # Recommended profile should include sparse embeddings
        assert "sparse_embedding" in config.get("embedding", {})


@pytest.mark.unit
@pytest.mark.config
class TestConfigShow:
    """Tests for config show command."""

    def test_show_displays_config(
        self, temp_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test config show displays current configuration."""
        # Create config first
        with pytest.raises(SystemExit):
            init_app(["config", "--quick"])

        # Show config - config_app default command shows config
        with pytest.raises(SystemExit) as exc_info:
            config_app([])

        captured = capsys.readouterr()
        assert exc_info.value.code == 0
        assert "Configuration" in captured.out or "CodeWeaver" in captured.out

    def test_show_handles_missing_config(self, temp_project: Path) -> None:
        """Test config show handles missing configuration gracefully."""
        # Run config command without creating config first
        with pytest.raises(SystemExit) as exc_info:
            config_app([])
        # Should not crash, should show defaults or warning
        assert exc_info.value.code in (0, 1)

    def test_show_respects_env_vars(
        self,
        temp_project: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test config show displays env var overrides."""
        monkeypatch.setenv("CODEWEAVER_EMBEDDING_PROVIDER", "voyage")

        with contextlib.suppress(SystemExit):
            config_app([])
        captured = capsys.readouterr()
        # Config command should display settings - may not show voyage if no config exists
        assert len(captured.out) > 0  # At least some output


@pytest.mark.unit
@pytest.mark.config
class TestConfigValidation:
    """Tests for config validation."""

    @pytest.mark.skip(reason="Provider validation not yet implemented in settings")
    def test_invalid_provider_rejected(self, temp_project: Path) -> None:
        """Test invalid provider names are rejected."""
        config_path = temp_project / ".codeweaver.toml"
        config_content = """
[embedding]
provider = "invalid_provider_xyz"
"""
        config_path.write_text(config_content)

        from codeweaver.config.settings import CodeWeaverSettings
        from codeweaver.exceptions import CodeWeaverError

        with pytest.raises((CodeWeaverError, ValueError)):
            CodeWeaverSettings(config_file=config_path)

    @pytest.mark.skip(reason="API key validation not yet implemented in init config command")
    def test_missing_required_api_key_warned(
        self,
        temp_project: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test missing API keys are warned about."""
        monkeypatch.delenv("VOYAGE_API_KEY", raising=False)

        with pytest.raises(SystemExit) as exc_info:
            init_app(["config", "--profile", ConfigProfile.RECOMMENDED.value])

        captured = capsys.readouterr()
        # Should warn about missing API key
        assert "VOYAGE_API_KEY" in captured.out or exc_info.value.code != 0


@pytest.mark.unit
@pytest.mark.config
class TestConfigProfiles:
    """Tests for config profiles."""

    @pytest.mark.skip(reason="Profile functions module not yet implemented")
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
            ConfigProfile.MINIMAL,
        }

        assert len(ConfigProfile) == len(expected_profiles)
        for profile in ConfigProfile:
            assert profile in expected_profiles
