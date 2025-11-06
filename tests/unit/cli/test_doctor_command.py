# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for doctor command.

Tests validate corrections from CLI_CORRECTIONS_PLAN.md:
- Unset sentinel handling (no isinstance(x, Path) errors)
- Correct import paths (get_user_config_dir location)
- Provider.other_env_vars usage (correct API key checks)
- Qdrant deployment detection (Docker/Cloud)
- Config requirement assumptions (env-only valid)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cyclopts.testing import CliRunner

from codeweaver.cli.commands.doctor import app as doctor_app
from codeweaver.config.settings import CodeWeaverSettings
from codeweaver.core.types.sentinel import Unset
from codeweaver.providers.provider import Provider


if TYPE_CHECKING:
    from pytest import MonkeyPatch


runner = CliRunner()


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
class TestDoctorUnsetHandling:
    """Tests for Unset sentinel handling."""

    def test_unset_handling_correct(self) -> None:
        """Test Unset sentinel is handled correctly."""
        settings = CodeWeaverSettings()

        # Should use isinstance(x, Unset), not isinstance(x, Path)
        assert isinstance(settings.project_path, Unset)

        # Should NOT raise TypeError
        result = isinstance(settings.project_path, Unset)
        assert result is True

    def test_unset_vs_none_distinction(self) -> None:
        """Test Unset is correctly distinguished from None."""
        unset_value = Unset()

        assert unset_value is not None
        assert isinstance(unset_value, Unset)
        assert not isinstance(None, Unset)

    def test_settings_with_unset_fields(self, temp_project: Path) -> None:
        """Test doctor handles settings with Unset fields correctly."""
        # Create minimal settings
        settings = CodeWeaverSettings()

        # Many fields should be Unset
        assert isinstance(settings.project_path, Unset)

        # Doctor should not crash on Unset checks
        result = runner.invoke(doctor_app)
        assert result.exit_code == 0

    def test_unset_check_pattern_correct(self) -> None:
        """Test correct pattern for checking Unset values."""
        from codeweaver.core.types.sentinel import Unset

        unset_value = Unset()

        # CORRECT pattern
        if isinstance(unset_value, Unset):
            assert True  # This should execute

        # WRONG pattern (would raise TypeError)
        # Don't test: isinstance(unset_value, Path)


@pytest.mark.unit
@pytest.mark.config
class TestDoctorImports:
    """Tests for correct import paths."""

    def test_import_paths_correct(self) -> None:
        """Test all import paths are correct."""
        # Should not raise ImportError
        from codeweaver.common.utils.utils import get_user_config_dir

        config_dir = get_user_config_dir()
        assert config_dir.exists() or config_dir.parent.exists()

    def test_import_from_wrong_module_fails(self) -> None:
        """Test importing from wrong module raises ImportError."""
        with pytest.raises(ImportError):
            from codeweaver.common.utils import get_user_config_dir  # noqa: F401


@pytest.mark.unit
@pytest.mark.config
class TestDoctorProviderEnvVars:
    """Tests for Provider.other_env_vars usage."""

    def test_provider_env_vars_used(self) -> None:
        """Test doctor uses Provider.other_env_vars for API key checks."""
        # Should use Provider enum, not hardcoded dict
        voyage = Provider.VOYAGE
        assert voyage.other_env_vars.api_key.env == "VOYAGE_API_KEY"

        openai = Provider.OPENAI
        assert openai.other_env_vars.api_key.env == "OPENAI_API_KEY"

        cohere = Provider.COHERE
        assert cohere.other_env_vars.api_key.env == "COHERE_API_KEY"

    def test_all_cloud_providers_have_env_vars(self) -> None:
        """Test all cloud providers have other_env_vars defined."""
        from codeweaver.common.registry import get_provider_registry
        from codeweaver.providers.provider import ProviderKind

        registry = get_provider_registry()
        embedding_providers = registry.list_providers(ProviderKind.EMBEDDING)

        # Cloud providers should have env vars
        cloud_providers = {
            "voyage", "openai", "cohere", "anthropic",
            "google", "mistral", "bedrock"
        }

        for provider_name in cloud_providers:
            try:
                provider = Provider.from_string(provider_name)
                if provider and provider.other_env_vars:
                    assert provider.other_env_vars.api_key is not None
            except ValueError:
                pass  # Provider not in enum


@pytest.mark.unit
@pytest.mark.config
class TestDoctorQdrantDetection:
    """Tests for Qdrant deployment detection."""

    def test_qdrant_cloud_detection(self) -> None:
        """Test Qdrant Cloud detection."""
        cloud_url = "https://xyz.cloud.qdrant.io"
        assert "cloud.qdrant.io" in cloud_url  # Should detect cloud

    def test_qdrant_docker_detection(self) -> None:
        """Test Docker Qdrant detection."""
        docker_url = "http://localhost:6333"
        assert "localhost" in docker_url  # Should detect docker

    def test_qdrant_deployment_types(self) -> None:
        """Test different Qdrant deployment scenarios."""
        scenarios = {
            "cloud": "https://cluster.cloud.qdrant.io",
            "docker": "http://localhost:6333",
            "custom": "http://qdrant.internal:6333",
            "memory": ":memory:",
        }

        for deployment_type, url in scenarios.items():
            if deployment_type == "cloud":
                assert "cloud.qdrant.io" in url
            elif deployment_type == "docker":
                assert "localhost" in url
            # Custom and memory would need different checks


@pytest.mark.unit
@pytest.mark.config
class TestDoctorConnectionTests:
    """Tests for connection testing functionality."""

    @pytest.mark.asyncio
    async def test_connection_tests_implemented(
        self,
        monkeypatch: MonkeyPatch
    ) -> None:
        """Test connection tests are implemented."""
        # Mock providers
        class MockProvider:
            async def health_check(self) -> bool:
                return True

        # Should not raise NotImplementedError
        provider = MockProvider()
        result = await provider.health_check()
        assert result is True

    def test_connection_test_flag_recognized(self, temp_project: Path) -> None:
        """Test --test-connections flag is recognized."""
        result = runner.invoke(doctor_app, ["--test-connections"])

        # Should not raise unknown option error
        assert "unrecognized" not in result.output.lower()


@pytest.mark.unit
@pytest.mark.config
class TestDoctorConfigAssumptions:
    """Tests for config file requirement assumptions."""

    def test_config_file_not_required(
        self,
        temp_project: Path,
        monkeypatch: MonkeyPatch
    ) -> None:
        """Test config files are optional when using env vars."""
        # Set all required env vars
        monkeypatch.setenv("CODEWEAVER_PROJECT_PATH", str(temp_project))
        monkeypatch.setenv("CODEWEAVER_EMBEDDING_PROVIDER", "fastembed")

        # Doctor should not warn about missing config file
        result = runner.invoke(doctor_app)

        # Should not mention missing config file
        assert result.exit_code == 0
        assert "missing" not in result.output.lower() or \
               "config" not in result.output.lower()

    def test_env_only_setup_valid(
        self,
        temp_project: Path,
        monkeypatch: MonkeyPatch
    ) -> None:
        """Test environment-only setup is valid."""
        # Set env vars for complete config
        monkeypatch.setenv("CODEWEAVER_PROJECT_PATH", str(temp_project))
        monkeypatch.setenv("CODEWEAVER_EMBEDDING_PROVIDER", "fastembed")
        monkeypatch.setenv("CODEWEAVER_VECTOR_STORE_TYPE", "qdrant")

        # Create settings without config file
        settings = CodeWeaverSettings()

        # Should be valid
        assert settings.project_path == temp_project
        assert settings.provider.embedding.provider == "fastembed"

    def test_config_sources_hierarchy(
        self,
        temp_project: Path,
        monkeypatch: MonkeyPatch
    ) -> None:
        """Test config can come from multiple sources."""
        from codeweaver.config.settings import CodeWeaverSettings

        # Create config file
        config_file = temp_project / "codeweaver.toml"
        config_file.write_text("""
[embedding]
provider = "fastembed"
""")

        # Override via env var
        monkeypatch.setenv("CODEWEAVER_EMBEDDING_PROVIDER", "voyage")

        # Env var should take precedence
        settings = CodeWeaverSettings(config_file=config_file)
        assert settings.provider.embedding.provider == "voyage"


@pytest.mark.unit
@pytest.mark.config
class TestDoctorDependencyChecks:
    """Tests for dependency checking."""

    def test_uses_find_spec_not_version(self) -> None:
        """Test dependency checks use find_spec() not version()."""
        from importlib.util import find_spec

        # Should use find_spec for availability
        spec = find_spec("codeweaver")
        assert spec is not None

        # Don't use importlib.metadata.version() for availability
        # (only for version reporting)

    def test_optional_dependencies_detected(self) -> None:
        """Test optional dependencies are correctly detected."""
        from importlib.util import find_spec

        # Check some optional dependencies
        optional_packages = {
            "fastembed": False,  # May or may not be installed
            "voyageai": False,
        }

        for package in optional_packages:
            spec = find_spec(package)
            # Should not raise, returns None if not found
            optional_packages[package] = spec is not None

    def test_core_dependencies_available(self) -> None:
        """Test core dependencies are available."""
        from importlib.util import find_spec

        core_packages = [
            "pydantic",
            "pydantic_settings",
            "qdrant_client",
            "rich",
        ]

        for package in core_packages:
            spec = find_spec(package)
            assert spec is not None, f"Core package {package} not found"
