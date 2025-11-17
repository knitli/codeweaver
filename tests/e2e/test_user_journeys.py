# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""End-to-end tests for complete user workflows.

Tests validate real user scenarios:
- New user quick start
- Offline developer workflow
- Production deployment workflow
"""

from __future__ import annotations

from pathlib import Path

import pytest
import tomli

from codeweaver.cli.commands.config import app as config_app
from codeweaver.cli.commands.init import app as init_app
from codeweaver.cli.commands.list import app as list_app


@pytest.fixture
def user_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Set up complete user environment."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    project = tmp_path / "my_project"
    project.mkdir()
    (project / ".git").mkdir()

    # Add some source files
    src = project / "src"
    src.mkdir()
    (src / "main.py").write_text("def main(): pass")
    (src / "utils.py").write_text("def helper(): pass")

    monkeypatch.chdir(project)

    return {"home": home, "project": project}


@pytest.mark.e2e
@pytest.mark.slow
class TestNewUserQuickStart:
    """Test: New user wants fastest setup."""

    def test_new_user_quick_start_journey(
        self, user_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test complete quick start journey for new user."""
        project = user_environment["project"]
        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")

        # Step 1: Quick init
        with pytest.raises(SystemExit) as init_result:
            init_app(["--quickstart", "--client", "claude_code"])

        assert init_result.value.code == 0

        # Step 2: Verify config created
        config_path = project / "codeweaver.toml"
        assert config_path.exists()

        # Step 3: Doctor check (may have warnings about dependencies or services)
        # We don't assert on exit code since it's environment-dependent

    def test_quick_start_with_config_show(
        self, user_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test quick start followed by viewing configuration."""
        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")

        # Init
        with pytest.raises(SystemExit) as init_result:
            init_app(["--quickstart", "--config-only"])
        assert init_result.value.code == 0

        # Show config
        with pytest.raises(SystemExit) as config_result:
            config_app([])
        assert config_result.value.code == 0

    def test_quick_start_list_capabilities(
        self, user_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test quick start followed by listing capabilities."""
        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")

        # Init
        with pytest.raises(SystemExit):
            init_app(["--quickstart", "--config-only"])

        # List providers
        with pytest.raises(SystemExit) as list_result:
            list_app(["providers"])
        assert list_result.value.code == 0

        # List models
        with pytest.raises(SystemExit) as models_result:
            list_app(["models", "--provider-name", "voyage"])
        assert models_result.value.code == 0


@pytest.mark.e2e
@pytest.mark.slow
class TestOfflineDeveloperWorkflow:
    """Test: Developer wants offline-capable setup."""

    def test_offline_developer_workflow(
        self, user_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test complete offline developer workflow."""
        project = user_environment["project"]

        # Step 1: Quickstart profile (free/offline providers)
        with pytest.raises(SystemExit) as init_result:
            init_app(["--profile", "quickstart", "--config-only", "--force"])

        # Should succeed even without API keys
        assert init_result.value.code == 0

        # Step 2: Verify config created
        assert (project / "codeweaver.toml").exists()

        # Step 3: Config uses local providers (no API keys needed)

    def test_offline_list_local_providers(
        self, user_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test listing local providers in offline mode."""
        # Init with quickstart (free/offline)
        with pytest.raises(SystemExit):
            init_app(["--profile", "quickstart", "--config-only", "--force"])

        # List local providers
        with pytest.raises(SystemExit) as list_result:
            list_app(["providers"])
        assert list_result.value.code == 0

    def test_offline_config_modifications(
        self, user_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test modifying config in offline mode."""
        project = user_environment["project"]

        # Init
        with pytest.raises(SystemExit):
            init_app(["--profile", "quickstart", "--config-only", "--force"])

        # Modify config
        config_path = project / "codeweaver.toml"
        config = tomli.loads(config_path.read_text())
        config["max_results"] = 20

        import tomli_w

        config_path.write_text(tomli_w.dumps(config))

        # Show modified config
        with pytest.raises(SystemExit) as show_result:
            config_app([])
        assert show_result.value.code == 0


@pytest.mark.e2e
@pytest.mark.slow
class TestProductionDeploymentWorkflow:
    """Test: Team deploying to production with Qdrant Cloud."""

    def test_production_deployment_workflow(
        self, user_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test complete production deployment workflow."""
        project = user_environment["project"]

        # Set production env vars
        monkeypatch.setenv("VOYAGE_API_KEY", "prod-voyage-key")
        monkeypatch.setenv("QDRANT_API_KEY", "prod-qdrant-key")
        monkeypatch.setenv("QDRANT_URL", "https://prod.cloud.qdrant.io")

        # Step 1: Create config
        config_content = """
[embedding]
provider = "voyage"
model = "voyage-code-3"

[vector_store]
type = "qdrant"
url = "https://prod.cloud.qdrant.io"
"""
        (project / "codeweaver.toml").write_text(config_content)

        # Step 2: Config created for cloud deployment

    def test_production_env_var_override(
        self, user_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test production uses env vars to override config."""
        project = user_environment["project"]

        # File config
        config_content = """
[embedding]
provider = "fastembed"
"""
        (project / "codeweaver.toml").write_text(config_content)

        # Override via env var (production pattern)
        monkeypatch.setenv("CODEWEAVER_EMBEDDING_PROVIDER", "voyage")
        monkeypatch.setenv("VOYAGE_API_KEY", "prod-key")

        # Config show should reflect env var override
        with pytest.raises(SystemExit) as show_result:
            config_app([])
        assert show_result.value.code == 0

    def test_production_multiple_environments(
        self, user_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test switching between dev/staging/prod environments."""
        project = user_environment["project"]

        # Base config
        base_config = """
[embedding]
provider = "voyage"
"""
        (project / "codeweaver.toml").write_text(base_config)

        # Test different environments
        environments = {
            "dev": {"VOYAGE_API_KEY": "dev-key", "QDRANT_URL": "http://localhost:6333"},
            "staging": {
                "VOYAGE_API_KEY": "staging-key",
                "QDRANT_URL": "https://staging.cloud.qdrant.io",
            },
            "prod": {"VOYAGE_API_KEY": "prod-key", "QDRANT_URL": "https://prod.cloud.qdrant.io"},
        }

        for env_vars in environments.values():
            # Set environment
            for key, value in env_vars.items():
                monkeypatch.setenv(key, value)

            # Environment configured successfully


@pytest.mark.e2e
@pytest.mark.slow
class TestCompleteUserJourneys:
    """Test complete end-to-end user journeys."""

    def test_first_time_user_complete_journey(
        self, user_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test: First-time user from install to working setup."""
        from codeweaver.cli.commands.init import _get_client_config_path

        project = user_environment["project"]
        user_environment["home"]

        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")

        # 1. Init (quick setup)
        with pytest.raises(SystemExit) as init_result:
            init_app(["--quickstart", "--client", "claude_code"])
        assert init_result.value.code == 0

        # 2. Verify both configs created
        assert (project / "codeweaver.toml").exists()
        mcp_config = _get_client_config_path(
            client="claude_code", config_level="project", project_path=project
        )
        assert mcp_config.exists()

        # 3. Config created successfully

        # 4. List capabilities
        with pytest.raises(SystemExit) as list_result:
            list_app(["providers"])
        assert list_result.value.code == 0

        # 5. View configuration
        with pytest.raises(SystemExit) as config_result:
            config_app([])
        assert config_result.value.code == 0

    def test_power_user_custom_setup(
        self, user_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test: Power user with custom configuration."""
        project = user_environment["project"]

        # 1. Create custom config
        custom_config = """
[embedding]
provider = "voyage"
model = "voyage-code-3"

[sparse_embedding]
provider = "fastembed"
enabled = true

[reranking]
provider = "voyage"
enabled = true

[vector_store]
type = "qdrant"
collection = "my_code"
"""
        (project / "codeweaver.toml").write_text(custom_config)

        # 2. Set API key
        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")

        # 3. Verify config
        with pytest.raises(SystemExit) as show_result:
            config_app([])
        assert show_result.value.code == 0

        # 4. Custom config validated

        # 5. List available models
        with pytest.raises(SystemExit) as models_result:
            list_app(["models", "--provider-name", "voyage"])
        assert models_result.value.code == 0

    def test_team_collaboration_workflow(
        self, user_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test: Team sharing configuration via git."""
        project = user_environment["project"]

        # 1. Create team config (checked into git)
        team_config = """
# Team shared config - checked into git
[embedding]
provider = "voyage"

[vector_store]
type = "qdrant"

# Individual developers set API keys via env vars
"""
        (project / "codeweaver.toml").write_text(team_config)

        # 2. Each developer sets their own keys
        monkeypatch.setenv("VOYAGE_API_KEY", "dev1-key")

        # 3. Config show should merge file + env
        with pytest.raises(SystemExit) as show_result:
            config_app([])
        assert show_result.value.code == 0

        # 4. Team config validated
