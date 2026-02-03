# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CLI test fixtures with mocked dependencies."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest


if TYPE_CHECKING:
    pass


@pytest.fixture(autouse=True)
def mock_settings_dependency(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Mock the settings dependency for CLI commands.

    This prevents DependsPlaceholder errors by providing a minimal mock
    settings object that satisfies basic CLI command needs without requiring
    full DI container initialization.

    Applied automatically to all CLI unit tests.
    """
    # Create a minimal mock settings object
    mock_settings = MagicMock()

    # Set up basic attributes that CLI commands typically access
    mock_settings.project_path = tmp_path / "test_project"
    mock_settings.project_name = "test-project"
    mock_settings.token_limit = 30000
    mock_settings.config_file = None

    # Mock save_to_file to actually create a minimal config file
    def mock_save_to_file(path: Path, **kwargs):
        """Create a minimal valid config file for testing."""
        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        # Determine provider based on filename (quickstart vs recommended)
        # This is a simple heuristic for testing
        embedding_provider = "fastembed" if "quickstart" in str(path).lower() else "voyage"

        # Write minimal valid TOML config
        minimal_config = f"""# CodeWeaver Test Configuration
[project]
name = "test-project"

[[embedding]]
provider = "{embedding_provider}"

[vector_store]
provider = "qdrant"
"""
        path.write_text(minimal_config)
        return path

    mock_settings.save_to_file = mock_save_to_file

    # Mock the view property (used by config command)
    mock_settings.view = {}

    # Patch the _get_settings function in init command
    def mock_get_settings(*args, **kwargs):
        return mock_settings

    # Patch all locations where _get_settings might be called
    monkeypatch.setattr("codeweaver.cli.commands.init._get_settings", mock_get_settings)
    monkeypatch.setattr("codeweaver.cli.commands.config._settings", mock_get_settings)

    return mock_settings
