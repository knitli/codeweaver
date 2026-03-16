from pathlib import Path
from unittest.mock import patch

from codeweaver.core.discovery import DiscoveredFile


def test_is_path_binary_exception_handling():
    # Arrange
    test_path = Path("some_nonexistent_or_protected_file.bin")

    # Act & Assert
    with patch("pathlib.Path.open", side_effect=PermissionError("Permission denied")):
        result = DiscoveredFile.is_path_binary(test_path)
        assert result is False

    with patch("pathlib.Path.open", side_effect=OSError("OS Error")):
        result = DiscoveredFile.is_path_binary(test_path)
        assert result is False
