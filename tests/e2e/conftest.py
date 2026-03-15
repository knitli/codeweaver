# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""E2E test fixtures."""

from __future__ import annotations

import os

from unittest.mock import MagicMock

import pytest


# Enable test mode for settings loading
os.environ["CODEWEAVER_TEST_MODE"] = "true"


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
