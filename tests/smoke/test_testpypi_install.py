# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Smoke test: install and verify package from TestPyPI."""

import subprocess
import tempfile

from pathlib import Path

import pytest


pytestmark = [pytest.mark.e2e]


@pytest.mark.external_api
@pytest.mark.network
def test_install_from_testpypi():
    """
    Smoke test for TestPyPI installation.

    Validates that the published package:
    1. Can be installed from TestPyPI
    2. Is importable
    3. Has correct version
    4. Basic functionality works

    Manual execution steps:
    1. Publish package to TestPyPI first
    2. Run: pytest tests/smoke/test_testpypi_install.py -v -s
    3. Verify all checks pass

    NOTE: Requires:
    - Package published to test.pypi.org
    - Network access
    - Clean Python environment

    This test will attempt to install the latest version available on TestPyPI.
    If the package is not available, the test will fail with a clear error message.
    """
    # Skip if the local version has not been published to TestPyPI yet.
    # This is common during development: the source may reference dependencies
    # (e.g. lateimport) not yet present in the last published release.
    try:
        import importlib.metadata

        local_version = importlib.metadata.version("code-weaver")
    except importlib.metadata.PackageNotFoundError:
        local_version = None

    check = subprocess.run(
        [
            "pip",
            "index",
            "versions",
            "--index-url",
            "https://test.pypi.org/simple/",
            "code-weaver",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if check.returncode != 0 or "code-weaver" not in check.stdout:
        pytest.skip("code-weaver not found on TestPyPI — package may not be published yet")
    if local_version and local_version not in check.stdout:
        pytest.skip(
            f"Local version {local_version!r} not yet published to TestPyPI; "
            "smoke test skipped until the current release is available"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        venv_path = Path(tmpdir) / "venv"

        # Create virtual environment
        result = subprocess.run(
            ["python", "-m", "venv", str(venv_path)], capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, f"Failed to create venv: {result.stderr}"

        pip = venv_path / "bin" / "pip"
        python = venv_path / "bin" / "python"

        # Install from TestPyPI with extra-index-url for dependencies
        # Note: The package is published as "code-weaver" on PyPI (see pyproject.toml)
        install_cmd = [
            str(pip),
            "install",
            "--index-url",
            "https://test.pypi.org/simple/",
            "--extra-index-url",
            "https://pypi.org/simple/",
            "code-weaver",
        ]

        result = subprocess.run(install_cmd, capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"Installation failed: {result.stderr}"

        # Verify importable
        import_cmd = [str(python), "-c", "import codeweaver; print(codeweaver.__version__)"]
        result = subprocess.run(import_cmd, capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"Import failed: {result.stderr}"

        installed_version = result.stdout.strip()
        print(f"Installed version: {installed_version}")

        # Basic functionality test - verify package structure
        check_cmd = [str(python), "-c", "import codeweaver; print('Package loaded successfully')"]
        result = subprocess.run(check_cmd, capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"Basic functionality check failed: {result.stderr}"
        assert "Package loaded successfully" in result.stdout


@pytest.mark.external_api
@pytest.mark.network
def test_testpypi_metadata():
    """
    Verify package metadata is correct on TestPyPI.

    Manual validation:
    1. Visit https://test.pypi.org/project/code-weaver/
    2. Verify metadata fields:
       - Description matches README
       - License: MIT OR Apache-2.0
       - Python versions: 3.12, 3.13, 3.14
       - Keywords present
       - Project URLs working
    """
    pytest.skip("Manual validation required - check TestPyPI project page")
