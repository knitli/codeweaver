# SPDX-License-Identifier: Apache-2.0
"""Unit tests for file discovery functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from codeweaver.core.discovery import DiscoveredFile

pytestmark = [pytest.mark.unit]


def test_absolute_path_filenotfound(tmp_path: Path) -> None:
    """Test that absolute_path falls back to returning self.path if get_project_path raises FileNotFoundError."""
    # Setup our discovered file
    discovered_file = DiscoveredFile(
        path=Path("some/file.py"),
        project_path=tmp_path
    )

    # We want to mock get_project_path to raise FileNotFoundError
    with patch("codeweaver.core.utils.get_project_path", side_effect=FileNotFoundError):
        # We expect absolute_path to fall back to returning self.path
        assert discovered_file.absolute_path == Path("some/file.py")
