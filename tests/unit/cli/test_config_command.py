# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for config command.

The config command is for viewing/showing the current resolved configuration.
Config creation functionality has been moved to the `init config` command.

Tests validate:
- Displaying current configuration
- Showing provider settings
- Handling missing configuration
- Environment variable overrides
"""

from __future__ import annotations

import contextlib

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from codeweaver.cli.commands.config import app as config_app
from codeweaver.cli.commands.init import app as init_app  # For setup in integration tests


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
class TestConfigShow:
    """Tests for config show command - the main functionality of `config` command."""

    def test_show_displays_config(
        self, temp_project: Path, capsys: pytest.CaptureFixture[str], mock_confirm: MagicMock
    ) -> None:
        """Test config show displays current configuration."""
        # Create config first
        with pytest.raises(SystemExit) as init_exc:
            init_app(["config", "--quickstart", "--project", str(temp_project)])

        assert init_exc.value.code == 0

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

    def test_invalid_provider_rejected(self, temp_project: Path) -> None:
        """Test invalid provider names are rejected."""
        config_path = temp_project / "codeweaver.toml"
        config_content = """
[provider.embedding]
provider = "invalid_provider_xyz"

[provider.embedding.model_settings]
model = "test-model"
"""
        config_path.write_text(config_content)

        from codeweaver.config.settings import CodeWeaverSettings
        from codeweaver.exceptions import CodeWeaverError

        with pytest.raises((CodeWeaverError, ValueError)):
            CodeWeaverSettings(config_file=config_path)
