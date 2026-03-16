import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
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

def test_is_path_text_exception_handling():
    # Arrange
    test_path = Path("some_nonexistent_or_protected_file.txt")

    # Act & Assert
    with patch("pathlib.Path.read_text", side_effect=PermissionError("Permission denied")):
        # We also need to mock is_path_binary to return False so it proceeds to read_text
        with patch.object(DiscoveredFile, 'is_path_binary', return_value=False):
            result = DiscoveredFile.is_path_text(test_path)
            assert result is False
