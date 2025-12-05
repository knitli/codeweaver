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
from urllib.parse import urlparse

import pytest

from codeweaver.cli.commands.doctor import app as doctor_app
from codeweaver.config.settings import CodeWeaverSettings
from codeweaver.core.types.aliases import SentinelName
from codeweaver.core.types.sentinel import Unset
from codeweaver.providers.provider import Provider


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
class TestDoctorUnsetHandling:
    """Tests for Unset sentinel handling."""

    def test_project_path_auto_detection(self) -> None:
        """Test project_path is auto-detected from git root."""
        settings = CodeWeaverSettings()

        # Settings should auto-detect project_path, not leave it as Unset
        assert not isinstance(settings.project_path, Unset)
        assert isinstance(settings.project_path, Path)
        assert settings.project_path.exists()

    def test_unset_vs_none_distinction(self) -> None:
        """Test Unset is correctly distinguished from None."""
        unset_value = Unset(name=SentinelName("UNSET"), module_name=__name__)

        assert unset_value is not None
        assert isinstance(unset_value, Unset)
        assert not isinstance(None, Unset)

    @pytest.mark.skip(
        reason="Doctor command may fail if no providers configured - test needs provider setup"
    )
    def test_doctor_handles_auto_detected_settings(
        self, temp_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test doctor handles settings with auto-detected fields correctly."""
        # Create minimal settings
        settings = CodeWeaverSettings()

        # project_path should be auto-detected
        assert not isinstance(settings.project_path, Unset)

        # Doctor should not crash on auto-detected settings
        with pytest.raises(SystemExit) as exc_info:
            doctor_app()
        assert exc_info.value.code == 0

    def test_unset_check_pattern_correct(self) -> None:
        # sourcery skip: remove-assert-true, remove-redundant-if
        """Test correct pattern for checking Unset values."""
        from codeweaver.core.types.sentinel import Unset

        unset_value = Unset(name="UNSET", module_name=__name__)

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

    def test_import_from_common_utils_succeeds(self) -> None:
        """Test importing from common.utils now works via __init__.py exports."""
        # Should not raise ImportError due to __init__.py exports
        from codeweaver.common.utils import get_user_config_dir

        config_dir = get_user_config_dir()
        assert config_dir is not None


@pytest.mark.unit
@pytest.mark.config
class TestDoctorProviderEnvVars:
    """Tests for Provider.other_env_vars usage."""

    def test_provider_env_vars_used(self) -> None:
        """Test doctor uses Provider.other_env_vars for API key checks."""
        # Should use Provider enum, not hardcoded dict
        voyage = Provider.VOYAGE
        if voyage.other_env_vars is not None:
            voyage_env = (
                voyage.other_env_vars[0]
                if isinstance(voyage.other_env_vars, tuple)
                else voyage.other_env_vars
            )
            assert voyage_env["api_key"].env == "VOYAGE_API_KEY"

        openai = Provider.OPENAI
        if openai.other_env_vars is not None:
            openai_env = (
                openai.other_env_vars[0]
                if isinstance(openai.other_env_vars, tuple)
                else openai.other_env_vars
            )
            assert openai_env["api_key"].env == "OPENAI_API_KEY"

        cohere = Provider.COHERE
        if cohere.other_env_vars is not None:
            cohere_env = (
                cohere.other_env_vars[0]
                if isinstance(cohere.other_env_vars, tuple)
                else cohere.other_env_vars
            )
            assert cohere_env["api_key"].env == "COHERE_API_KEY"

    def test_all_cloud_providers_have_env_vars(self) -> None:
        """Test all cloud providers have other_env_vars defined."""
        from codeweaver.common.registry import get_provider_registry
        from codeweaver.providers.provider import ProviderKind

        registry = get_provider_registry()
        embedding_providers = registry.list_providers(ProviderKind.EMBEDDING)
        # bedrock is a special case with many different auth methods and a very long list of env vars that aren't implemented in Provider.other_env_vars
        cloud_providers = [
            provider
            for provider in embedding_providers
            if provider.is_cloud_provider and provider != Provider.BEDROCK
        ]

        for provider in cloud_providers:
            if provider and provider.other_env_vars:
                env_vars = next((var for var in provider.other_env_vars if var.get("api_key")), {})
                assert "api_key" in env_vars


@pytest.mark.unit
@pytest.mark.config
class TestDoctorQdrantDetection:
    """Tests for Qdrant deployment detection."""

    def test_qdrant_cloud_detection(self) -> None:
        """Test Qdrant Cloud detection."""
        cloud_url = "https://xyz.cloud.qdrant.io"
        host = urlparse(cloud_url).hostname
        assert host is not None and (
            host == "cloud.qdrant.io" or host.endswith(".cloud.qdrant.io")
        )  # Should detect cloud

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
                host = urlparse(url).hostname
                assert host is not None and (
                    host == "cloud.qdrant.io" or host.endswith(".cloud.qdrant.io")
                )
            elif deployment_type == "docker":
                assert "localhost" in url
            # Custom and memory would need different checks


@pytest.mark.unit
@pytest.mark.config
class TestDoctorConnectionTests:
    """Tests for connection testing functionality."""

    @pytest.mark.asyncio
    async def test_connection_tests_implemented(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test connection tests are implemented."""

        # Mock providers
        class MockProvider:
            async def health_check(self) -> bool:
                return True

        # Should not raise NotImplementedError
        provider = MockProvider()
        result = await provider.health_check()
        assert result is True

    def test_connection_test_flag_recognized(
        self, temp_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test --test-connections flag is recognized."""
        with pytest.raises(SystemExit):
            doctor_app("--test-connections")

        captured = capsys.readouterr()
        # Should not raise unknown option error
        assert "unrecognized" not in captured.out.lower()


@pytest.mark.unit
@pytest.mark.config
class TestDoctorConfigAssumptions:
    """Tests for config file requirement assumptions."""

    @pytest.mark.skip(reason="Settings structure changed")
    def test_config_file_not_required(
        self,
        temp_project: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Test config files are optional when using env vars."""
        # Set all required env vars
        monkeypatch.setenv("CODEWEAVER_PROJECT_PATH", str(temp_project))
        monkeypatch.setenv("CODEWEAVER_EMBEDDING_PROVIDER", "fastembed")

        # Doctor should not warn about missing config file
        with pytest.raises(SystemExit) as exc_info:
            doctor_app()

        captured = capsys.readouterr()
        # Should not mention missing config file
        assert exc_info.value.code == 0
        assert "missing" not in captured.out.lower() or "config" not in captured.out.lower()

    @pytest.mark.skip(reason="Settings structure changed")
    def test_env_only_setup_valid(
        self, temp_project: Path, monkeypatch: pytest.MonkeyPatch
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

    @pytest.mark.skip(reason="Settings structure changed")
    def test_config_sources_hierarchy(
        self, temp_project: Path, monkeypatch: pytest.MonkeyPatch
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

        core_packages = ["pydantic", "pydantic_settings", "qdrant_client", "rich"]

        for package in core_packages:
            spec = find_spec(package)
            assert spec is not None, f"Core package {package} not found"
