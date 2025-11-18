# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit test fixtures."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_confirm(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock rich.prompt.Confirm for CLI tests.

    Returns a mock Confirm object that automatically returns True for all confirmations.
    Tests can override by setting mock_confirm.ask.return_value to False.

    Patches module-level imports of Confirm to avoid stdin access issues during testing
    when pytest captures output. Only patches locations where Confirm is imported at
    module level, not inside functions.
    """
    mock = MagicMock()
    mock.ask.return_value = True

    # Patch the module-level import in init.py (imported at line 27)
    monkeypatch.setattr("codeweaver.cli.commands.init.Confirm", mock)
    # Also patch the base location to catch any other imports
    monkeypatch.setattr("rich.prompt.Confirm", mock)

    return mock


@pytest.fixture(autouse=True)
def isolated_test_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure all tests run in isolated environment.

    This autouse fixture prevents tests from touching real user configs by:
    - Setting a temporary HOME directory
    - Setting CODEWEAVER_TEST_MODE environment variable
    - Resetting CodeWeaver settings between tests

    Applied automatically to all unit tests.
    """
    from codeweaver.config.settings import reset_settings

    # Create isolated HOME directory
    fake_home = tmp_path / "home"
    fake_home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(fake_home))

    # Enable test mode for CodeWeaver settings
    monkeypatch.setenv("CODEWEAVER_TEST_MODE", "1")

    # Reset settings to prevent cross-test contamination
    reset_settings()

    yield

    # Cleanup after test
    reset_settings()
