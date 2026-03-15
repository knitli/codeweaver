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
def mock_confirm(clean_container) -> MagicMock:
    """Mock UserInteraction for CLI tests.

    Returns a mock Interaction object that automatically returns True for all confirmations.
    Tests can override by setting mock_confirm.confirm.return_value to False.
    """
    from codeweaver.cli.ui import UserInteraction

    mock = MagicMock()
    mock.confirm.return_value = True

    # Override in DI container
    clean_container.override(UserInteraction, mock)

    return mock


@pytest.fixture(autouse=True)
def isolated_test_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure all tests run in isolated environment.

    This autouse fixture prevents tests from touching real user configs by:
    - Setting a temporary HOME directory
    - Setting CODEWEAVER_TEST_MODE environment variable
    - Resetting CodeWeaver settings between tests

    Applied automatically to all unit tests.

    Note: Settings are now managed through DI container, which is reset
    by the reset_di_container fixture in the root conftest.py.
    """
    # Create isolated HOME directory
    fake_home = tmp_path / "home"
    fake_home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(fake_home))

    # Enable test mode for CodeWeaver settings
    monkeypatch.setenv("CODEWEAVER_TEST_MODE", "1")

    return
