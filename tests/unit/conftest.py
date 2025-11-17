# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit test fixtures."""

from __future__ import annotations

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
