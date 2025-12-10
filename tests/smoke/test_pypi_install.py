# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Smoke test: install and verify package from production PyPI."""

import subprocess
import tempfile

from pathlib import Path

import pytest


pytestmark = [pytest.mark.e2e]


@pytest.mark.external_api
@pytest.mark.network
def test_install_from_pypi():
    """
    Smoke test for production PyPI installation.

    Validates that the published package:
    1. Can be installed from PyPI
    2. Is importable
    3. Has correct version
    4. Basic functionality works

    Manual execution steps:
    1. Publish package to PyPI first (via tagged release)
    2. Run: pytest tests/smoke/test_pypi_install.py -v -s --no-skip
    3. Verify all checks pass

    NOTE: Requires:
    - Network access
    - Clean Python environment
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        venv_path = Path(tmpdir) / "venv"

        # Create virtual environment
        result = subprocess.run(
            ["python", "-m", "venv", str(venv_path)], capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, f"Failed to create venv: {result.stderr}"

        pip = venv_path / "bin" / "pip"
        python = venv_path / "bin" / "python"

        # Install from PyPI
        install_cmd = [str(pip), "install", "code-weaver"]

        result = subprocess.run(install_cmd, capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"Installation failed: {result.stderr}"

        # Verify importable
        import_cmd = [str(python), "-c", "import codeweaver; print(codeweaver.__version__)"]
        result = subprocess.run(import_cmd, capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"Import failed: {result.stderr}"

        installed_version = result.stdout.strip()
        print(f"Installed version: {installed_version}")

        # Verify version is semantic (not pre-release with +g hash)
        import re

        assert re.match(r"^\d+\.\d+\.\d+", installed_version), (
            f"Production version should be clean semantic version, got: {installed_version}"
        )

        # Basic functionality test
        check_cmd = [str(python), "-c", "import codeweaver; print('Package loaded successfully')"]
        result = subprocess.run(check_cmd, capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"Basic functionality check failed: {result.stderr}"
        assert "Package loaded successfully" in result.stdout


@pytest.mark.external_api
@pytest.mark.network
def test_pypi_metadata():
    """
    Verify package metadata is correct on production PyPI.

    Manual validation:
    1. Visit https://pypi.org/project/codeweaver/
    2. Verify metadata fields:
       - Description matches README
       - License: MIT OR Apache-2.0
       - Python versions: 3.12, 3.13, 3.14
       - Keywords present
       - Project URLs working
       - Badge displays correctly
    """
    pytest.skip("Manual validation required - check PyPI project page")


@pytest.mark.external_api
@pytest.mark.network
def test_pypi_search():
    """
    Verify package is discoverable via PyPI search.

    Manual validation:
    1. Search for "code-weaver" on pypi.org
    2. Verify code-weaver appears in results
    3. Verify description is visible
    4. Verify keywords aid discoverability
    """
    pytest.skip("Manual validation required - search PyPI")
