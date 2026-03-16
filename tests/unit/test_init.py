import importlib.metadata
import shutil
import subprocess
import sys
from unittest.mock import MagicMock

import pytest

import codeweaver

_original_version = importlib.metadata.version

@pytest.fixture
def mock_no_version_file(monkeypatch):
    """Remove _version module from sys.modules and codeweaver module."""
    monkeypatch.delitem(sys.modules, "codeweaver._version", raising=False)
    if hasattr(codeweaver, "_version"):
        monkeypatch.delattr(codeweaver, "_version", raising=False)

    # We must also clear the internal import mechanisms tracking caching!
    # A cleaner approach is simply to re-import get_version explicitly so it bounds to the current env
    import importlib
    importlib.reload(codeweaver)
    return codeweaver.get_version

@pytest.fixture
def mock_no_metadata(monkeypatch, mock_no_version_file):
    """Mock importlib.metadata to raise PackageNotFoundError for code-weaver."""
    def mock_version(pkg_name):
        if pkg_name == "code-weaver":
            raise importlib.metadata.PackageNotFoundError("code-weaver")
        return _original_version(pkg_name)
    monkeypatch.setattr(importlib.metadata, "version", mock_version)
    return mock_no_version_file

def test_get_version_from_version_file(monkeypatch, mock_no_version_file):
    """Test getting version from codeweaver._version.__version__."""
    mock_module = MagicMock()
    mock_module.__version__ = "1.2.3-file"
    monkeypatch.setitem(sys.modules, "codeweaver._version", mock_module)

    # Need to reload codeweaver because we just changed sys.modules
    import importlib
    importlib.reload(codeweaver)

    assert codeweaver.get_version() == "1.2.3-file"

def test_get_version_from_importlib_metadata(monkeypatch, mock_no_version_file):
    """Test getting version from importlib.metadata."""
    get_version = mock_no_version_file
    def mock_version(pkg_name):
        if pkg_name == "code-weaver":
            return "1.2.3-metadata"
        return _original_version(pkg_name)

    monkeypatch.setattr(importlib.metadata, "version", mock_version)

    assert get_version() == "1.2.3-metadata"

def test_get_version_from_git_success(monkeypatch, mock_no_metadata):
    """Test getting version from git describe."""
    get_version = mock_no_metadata
    monkeypatch.setattr(shutil, "which", lambda cmd: "git" if cmd == "git" else None)

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "1.2.3-git\n"

    def mock_run(*args, **kwargs):
        return mock_result

    monkeypatch.setattr(subprocess, "run", mock_run)

    assert get_version() == "1.2.3-git"

def test_get_version_from_git_failure(monkeypatch, mock_no_metadata):
    """Test git describe fails and returns 0.0.0."""
    get_version = mock_no_metadata
    monkeypatch.setattr(shutil, "which", lambda cmd: "git" if cmd == "git" else None)

    mock_result = MagicMock()
    mock_result.returncode = 1

    def mock_run(*args, **kwargs):
        return mock_result

    monkeypatch.setattr(subprocess, "run", mock_run)

    assert get_version() == "0.0.0"

def test_get_version_no_git(monkeypatch, mock_no_metadata):
    """Test git is not installed, returns 0.0.0."""
    get_version = mock_no_metadata
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    assert get_version() == "0.0.0"

def test_get_version_exception(monkeypatch, mock_no_metadata):
    """Test general exception in git block returns 0.0.0."""
    get_version = mock_no_metadata
    def mock_which(cmd):
        raise RuntimeError("Something went wrong")
    monkeypatch.setattr(shutil, "which", mock_which)

    assert get_version() == "0.0.0"
