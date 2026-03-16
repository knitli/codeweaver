from pathlib import Path
from unittest.mock import patch

from codeweaver.core.discovery import DiscoveredFile


def test_absolute_path_filenotfound() -> None:
    """Test that absolute_path falls back to returning self.path if get_project_path raises FileNotFoundError."""
    # Setup our discovered file
    file = DiscoveredFile(
        path=Path("some/file.py"),
        project_path=None
    )

    # We want to mock get_project_path to raise FileNotFoundError
    with patch("codeweaver.core.utils.get_project_path", side_effect=FileNotFoundError):
        # We expect absolute_path to fall back to returning self.path
        assert file.absolute_path == Path("some/file.py")
