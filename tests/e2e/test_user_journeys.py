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
from typing import TYPE_CHECKING

import pytest
import tomli

from cyclopts.testing import CliRunner

from codeweaver.cli.commands.config import app as config_app
from codeweaver.cli.commands.doctor import app as doctor_app
from codeweaver.cli.commands.init import app as init_app
from codeweaver.cli.commands.list import app as list_app


if TYPE_CHECKING:
    from pytest import MonkeyPatch


runner = CliRunner()


@pytest.fixture
def user_environment(tmp_path: Path, monkeypatch: MonkeyPatch) -> dict[str, Path]:
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
        self,
        user_environment: dict[str, Path],
        monkeypatch: MonkeyPatch
    ) -> None:
        """Test complete quick start journey for new user."""
        project = user_environment["project"]
        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")

        # Step 1: Quick init
        init_result = runner.invoke(
            init_app,
            ["--quick", "--client", "claude_code"]
        )

        assert init_result.exit_code == 0
        assert "complete" in init_result.output.lower() or \
               "success" in init_result.output.lower()

        # Step 2: Verify config created
        config_path = project / "codeweaver.toml"
        assert config_path.exists()

        config = tomli.loads(config_path.read_text())
        assert "embedding" in config
        assert config["embedding"]["provider"] == "voyage"

        # Step 3: Check doctor (should pass)
        doctor_result = runner.invoke(doctor_app)

        assert doctor_result.exit_code == 0
        output_lower = doctor_result.output.lower()

        # Should mention API key
        assert "voyage" in output_lower or "api_key" in output_lower

    def test_quick_start_with_config_show(
        self,
        user_environment: dict[str, Path],
        monkeypatch: MonkeyPatch
    ) -> None:
        """Test quick start followed by viewing configuration."""
        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")

        # Init
        init_result = runner.invoke(init_app, ["--quick", "--config-only"])
        assert init_result.exit_code == 0

        # Show config
        config_result = runner.invoke(config_app, ["show"])
        assert config_result.exit_code == 0
        assert "voyage" in config_result.output.lower()

    def test_quick_start_list_capabilities(
        self,
        user_environment: dict[str, Path],
        monkeypatch: MonkeyPatch
    ) -> None:
        """Test quick start followed by listing capabilities."""
        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")

        # Init
        runner.invoke(init_app, ["--quick", "--config-only"])

        # List providers
        list_result = runner.invoke(list_app, ["providers"])
        assert list_result.exit_code == 0
        assert "voyage" in list_result.output.lower()

        # List models
        models_result = runner.invoke(
            list_app,
            ["models", "--provider", "voyage"]
        )
        assert models_result.exit_code == 0


@pytest.mark.e2e
@pytest.mark.slow
class TestOfflineDeveloperWorkflow:
    """Test: Developer wants offline-capable setup."""

    def test_offline_developer_workflow(
        self,
        user_environment: dict[str, Path],
        monkeypatch: MonkeyPatch
    ) -> None:
        """Test complete offline developer workflow."""
        project = user_environment["project"]

        # Step 1: Local-only profile
        init_result = runner.invoke(
            init_app,
            ["--profile", "local-only", "--config-only"]
        )

        # Should succeed even without API keys
        assert init_result.exit_code == 0

        # Step 2: Verify no API keys needed
        config = tomli.loads((project / "codeweaver.toml").read_text())
        assert config["embedding"]["provider"] == "fastembed"

        # Step 3: Doctor should not warn about API keys
        doctor_result = runner.invoke(doctor_app)
        assert doctor_result.exit_code == 0

        output_lower = doctor_result.output.lower()
        # Should not have API key warnings for local providers
        if "api_key" in output_lower:
            assert "not required" in output_lower or \
                   "optional" in output_lower

    def test_offline_list_local_providers(
        self,
        user_environment: dict[str, Path],
        monkeypatch: MonkeyPatch
    ) -> None:
        """Test listing local providers in offline mode."""
        # Init with local-only
        runner.invoke(
            init_app,
            ["--profile", "local-only", "--config-only"]
        )

        # List local providers
        list_result = runner.invoke(list_app, ["providers"])
        assert list_result.exit_code == 0

        # Should show fastembed
        assert "fastembed" in list_result.output.lower()

    def test_offline_config_modifications(
        self,
        user_environment: dict[str, Path],
        monkeypatch: MonkeyPatch
    ) -> None:
        """Test modifying config in offline mode."""
        project = user_environment["project"]

        # Init
        runner.invoke(
            init_app,
            ["--profile", "local-only", "--config-only"]
        )

        # Modify config
        config_path = project / "codeweaver.toml"
        config = tomli.loads(config_path.read_text())
        config["max_results"] = 20

        import tomli_w
        config_path.write_text(tomli_w.dumps(config))

        # Show modified config
        show_result = runner.invoke(config_app, ["show"])
        assert show_result.exit_code == 0
        assert "20" in show_result.output


@pytest.mark.e2e
@pytest.mark.slow
class TestProductionDeploymentWorkflow:
    """Test: Team deploying to production with Qdrant Cloud."""

    def test_production_deployment_workflow(
        self,
        user_environment: dict[str, Path],
        monkeypatch: MonkeyPatch
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

        # Step 2: Doctor should detect cloud deployment
        doctor_result = runner.invoke(doctor_app)

        assert doctor_result.exit_code == 0
        output_lower = doctor_result.output.lower()

        # Should detect cloud
        assert "cloud" in output_lower or "qdrant" in output_lower

        # Should check API keys
        assert "api_key" in output_lower or "voyage" in output_lower

    def test_production_env_var_override(
        self,
        user_environment: dict[str, Path],
        monkeypatch: MonkeyPatch
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
        show_result = runner.invoke(config_app, ["show"])
        assert show_result.exit_code == 0
        assert "voyage" in show_result.output.lower()

    def test_production_multiple_environments(
        self,
        user_environment: dict[str, Path],
        monkeypatch: MonkeyPatch
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
            "dev": {
                "VOYAGE_API_KEY": "dev-key",
                "QDRANT_URL": "http://localhost:6333",
            },
            "staging": {
                "VOYAGE_API_KEY": "staging-key",
                "QDRANT_URL": "https://staging.cloud.qdrant.io",
            },
            "prod": {
                "VOYAGE_API_KEY": "prod-key",
                "QDRANT_URL": "https://prod.cloud.qdrant.io",
            },
        }

        for env_name, env_vars in environments.items():
            # Set environment
            for key, value in env_vars.items():
                monkeypatch.setenv(key, value)

            # Doctor should pass for each environment
            doctor_result = runner.invoke(doctor_app)
            assert doctor_result.exit_code == 0


@pytest.mark.e2e
@pytest.mark.slow
class TestCompleteUserJourneys:
    """Test complete end-to-end user journeys."""

    def test_first_time_user_complete_journey(
        self,
        user_environment: dict[str, Path],
        monkeypatch: MonkeyPatch
    ) -> None:
        """Test: First-time user from install to working setup."""
        project = user_environment["project"]
        home = user_environment["home"]

        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")

        # 1. Init (quick setup)
        init_result = runner.invoke(
            init_app,
            ["--quick", "--client", "claude_code"]
        )
        assert init_result.exit_code == 0

        # 2. Verify both configs created
        assert (project / "codeweaver.toml").exists()
        mcp_config = home / ".config" / "claude" / "claude_code_config.json"
        assert mcp_config.exists()

        # 3. Check health
        doctor_result = runner.invoke(doctor_app)
        assert doctor_result.exit_code == 0

        # 4. List capabilities
        list_result = runner.invoke(list_app, ["providers"])
        assert list_result.exit_code == 0

        # 5. View configuration
        config_result = runner.invoke(config_app, ["show"])
        assert config_result.exit_code == 0

    def test_power_user_custom_setup(
        self,
        user_environment: dict[str, Path],
        monkeypatch: MonkeyPatch
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
        show_result = runner.invoke(config_app, ["show"])
        assert show_result.exit_code == 0

        # 4. Check health
        doctor_result = runner.invoke(doctor_app)
        assert doctor_result.exit_code == 0

        # 5. List available models
        models_result = runner.invoke(
            list_app,
            ["models", "--provider", "voyage"]
        )
        assert models_result.exit_code == 0

    def test_team_collaboration_workflow(
        self,
        user_environment: dict[str, Path],
        monkeypatch: MonkeyPatch
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
        show_result = runner.invoke(config_app, ["show"])
        assert show_result.exit_code == 0
        assert "voyage" in show_result.output.lower()

        # 4. Doctor validates setup
        doctor_result = runner.invoke(doctor_app)
        assert doctor_result.exit_code == 0
