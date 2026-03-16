import importlib.metadata
import shutil
import subprocess
import sys
from unittest.mock import MagicMock

from codeweaver import get_version

def test_get_version_from_version_file(monkeypatch):
    """Test getting version from codeweaver._version.__version__."""
    # We need to mock sys.modules to simulate codeweaver._version being importable
    mock_module = MagicMock()
    mock_module.__version__ = "1.2.3-file"
    monkeypatch.setitem(sys.modules, "codeweaver._version", mock_module)

    assert get_version() == "1.2.3-file"


def test_get_version_from_importlib_metadata(monkeypatch):
    """Test getting version from importlib.metadata."""
    # Mock codeweaver._version to not exist
    monkeypatch.delitem(sys.modules, "codeweaver._version", raising=False)

    # Mock importlib.metadata.version to return our version
    def mock_version(pkg_name):
        if pkg_name == "code-weaver":
            return "1.2.3-metadata"
        raise importlib.metadata.PackageNotFoundError("code-weaver")

    monkeypatch.setattr(importlib.metadata, "version", mock_version)

    assert get_version() == "1.2.3-metadata"


def test_get_version_from_git_success(monkeypatch):
    """Test getting version from git describe."""
    # Mock codeweaver._version to not exist
    monkeypatch.delitem(sys.modules, "codeweaver._version", raising=False)

    # Mock importlib.metadata.version to raise PackageNotFoundError
    def mock_version(pkg_name):
        raise importlib.metadata.PackageNotFoundError("code-weaver")
    monkeypatch.setattr(importlib.metadata, "version", mock_version)

    # Mock shutil.which to return a git path
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/git" if cmd == "git" else None)

    # Mock subprocess.run to return successful git describe
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "1.2.3-git\n"

    def mock_run(*args, **kwargs):
        if args[0][0] == "/usr/bin/git" and args[0][1] == "describe":
            return mock_result
        return MagicMock(returncode=1)

    monkeypatch.setattr(subprocess, "run", mock_run)

    assert get_version() == "1.2.3-git"


def test_get_version_from_git_failure(monkeypatch):
    """Test git describe fails and returns 0.0.0."""
    monkeypatch.delitem(sys.modules, "codeweaver._version", raising=False)
    def mock_version(pkg_name):
        raise importlib.metadata.PackageNotFoundError("code-weaver")
    monkeypatch.setattr(importlib.metadata, "version", mock_version)

    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/git" if cmd == "git" else None)

    # Mock subprocess.run to fail
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = ""

    def mock_run(*args, **kwargs):
        return mock_result

    monkeypatch.setattr(subprocess, "run", mock_run)

    assert get_version() == "0.0.0"


def test_get_version_no_git(monkeypatch):
    """Test git is not installed, returns 0.0.0."""
    monkeypatch.delitem(sys.modules, "codeweaver._version", raising=False)
    def mock_version(pkg_name):
        raise importlib.metadata.PackageNotFoundError("code-weaver")
    monkeypatch.setattr(importlib.metadata, "version", mock_version)

    # Mock shutil.which to return None
    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    assert get_version() == "0.0.0"


def test_get_version_exception(monkeypatch):
    """Test general exception in git block returns 0.0.0."""
    monkeypatch.delitem(sys.modules, "codeweaver._version", raising=False)
    def mock_version(pkg_name):
        raise importlib.metadata.PackageNotFoundError("code-weaver")
    monkeypatch.setattr(importlib.metadata, "version", mock_version)

    # Mock shutil.which to raise an exception
    def mock_which(cmd):
        raise RuntimeError("Something went wrong")
    monkeypatch.setattr(shutil, "which", mock_which)

    assert get_version() == "0.0.0"
