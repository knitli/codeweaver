import importlib.metadata
import shutil
import subprocess
import sys
from unittest.mock import MagicMock

import pytest

from codeweaver import get_version

# Store the original version function to fall back to it for other packages
_original_version = importlib.metadata.version

def test_get_version_from_version_file(monkeypatch):
    """Test getting version from codeweaver._version.__version__."""
    mock_module = MagicMock()
    mock_module.__version__ = "1.2.3-file"
    monkeypatch.setitem(sys.modules, "codeweaver._version", mock_module)

    assert get_version() == "1.2.3-file"

def test_get_version_from_importlib_metadata(monkeypatch):
    """Test getting version from importlib.metadata."""
    monkeypatch.setitem(sys.modules, "codeweaver._version", None)

    def mock_version(pkg_name):
        if pkg_name == "code-weaver":
            return "1.2.3-metadata"
        return _original_version(pkg_name)

    monkeypatch.setattr(importlib.metadata, "version", mock_version)

    assert get_version() == "1.2.3-metadata"

def test_get_version_from_git_success(monkeypatch):
    """Test getting version from git describe."""
    monkeypatch.setitem(sys.modules, "codeweaver._version", None)

    def mock_version(pkg_name):
        if pkg_name == "code-weaver":
            raise importlib.metadata.PackageNotFoundError("code-weaver")
        return _original_version(pkg_name)
    monkeypatch.setattr(importlib.metadata, "version", mock_version)

    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/git" if cmd == "git" else None)

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "1.2.3-git\n"

    def mock_run(*args, **kwargs):
        return mock_result

    monkeypatch.setattr(subprocess, "run", mock_run)

    assert get_version() == "1.2.3-git"

def test_get_version_from_git_failure(monkeypatch):
    """Test git describe fails and returns 0.0.0."""
    monkeypatch.setitem(sys.modules, "codeweaver._version", None)

    def mock_version(pkg_name):
        if pkg_name == "code-weaver":
            raise importlib.metadata.PackageNotFoundError("code-weaver")
        return _original_version(pkg_name)
    monkeypatch.setattr(importlib.metadata, "version", mock_version)

    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/git" if cmd == "git" else None)

    mock_result = MagicMock()
    mock_result.returncode = 1

    def mock_run(*args, **kwargs):
        return mock_result

    monkeypatch.setattr(subprocess, "run", mock_run)

    assert get_version() == "0.0.0"

def test_get_version_no_git(monkeypatch):
    """Test git is not installed, returns 0.0.0."""
    monkeypatch.setitem(sys.modules, "codeweaver._version", None)

    def mock_version(pkg_name):
        if pkg_name == "code-weaver":
            raise importlib.metadata.PackageNotFoundError("code-weaver")
        return _original_version(pkg_name)
    monkeypatch.setattr(importlib.metadata, "version", mock_version)

    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    assert get_version() == "0.0.0"

def test_get_version_exception(monkeypatch):
    """Test general exception in git block returns 0.0.0."""
    monkeypatch.setitem(sys.modules, "codeweaver._version", None)

    def mock_version(pkg_name):
        if pkg_name == "code-weaver":
            raise importlib.metadata.PackageNotFoundError("code-weaver")
        return _original_version(pkg_name)
    monkeypatch.setattr(importlib.metadata, "version", mock_version)

    def mock_which(cmd):
        raise RuntimeError("Something went wrong")
    monkeypatch.setattr(shutil, "which", mock_which)

    assert get_version() == "0.0.0"
