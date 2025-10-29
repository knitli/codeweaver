# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Contract test: validate package publishing and installation."""

import subprocess
import tempfile
import urllib.error
import urllib.request

from pathlib import Path

import pytest


@pytest.fixture
def package_info():
    """Get package name and version from build."""
    project_root = Path(__file__).parent.parent.parent

    # Build package
    import shutil

    dist_dir = project_root / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    result = subprocess.run(
        ["uv", "build"], capture_output=True, text=True, check=False, cwd=project_root
    )

    if result.returncode != 0:
        pytest.skip(f"Build failed: {result.stderr}")

    # Extract package info from wheel
    wheels = list(dist_dir.glob("*.whl"))
    if not wheels:
        pytest.skip("No wheel found")

    wheel_name = wheels[0].name
    # Format: codeweaver_mcp-{version}-py3-none-any.whl
    parts = wheel_name.split("-")
    package_name = "codeweaver-mcp"  # PyPI normalized name
    version = parts[1] if len(parts) > 1 else ""

    return {
        "package_name": package_name,
        "version": version,
        "dist_dir": dist_dir,
        "project_root": project_root,
    }


@pytest.mark.integration
@pytest.mark.external_api
@pytest.mark.skip(reason="Requires actual TestPyPI/PyPI publish - run manually after publish")
def test_validate_publish_output_testpypi(package_info: dict):
    """
    Contract test for TestPyPI publish validation.

    Validates that published package:
    - Is accessible on TestPyPI
    - Can be installed from TestPyPI
    - Is importable after installation
    - Has correct version

    This test MUST be run manually after TestPyPI publish.
    """
    package_name = package_info["package_name"]
    version = package_info["version"]

    # Verify package page exists on TestPyPI
    package_url = f"https://test.pypi.org/project/{package_name}/{version}/"

    try:
        response = urllib.request.urlopen(package_url)
        assert response.status == 200, f"Package page not found: {package_url}"
    except urllib.error.HTTPError as e:
        pytest.fail(f"Package not accessible on TestPyPI: {e}")

    # Verify package installable in clean environment
    with tempfile.TemporaryDirectory() as tmpdir:
        venv_path = Path(tmpdir) / "venv"

        # Create virtual environment
        result = subprocess.run(
            ["python", "-m", "venv", str(venv_path)], capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, f"Failed to create venv: {result.stderr}"

        pip = venv_path / "bin" / "pip"
        python = venv_path / "bin" / "python"

        # Install from TestPyPI
        install_cmd = [
            str(pip),
            "install",
            f"{package_name}=={version}",
            "--index-url",
            "https://test.pypi.org/simple/",
            "--extra-index-url",
            "https://pypi.org/simple/",
        ]

        result = subprocess.run(install_cmd, capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"Installation failed: {result.stderr}"

        # Verify importable
        import_cmd = [str(python), "-c", "import codeweaver; print(codeweaver.__version__)"]
        result = subprocess.run(import_cmd, capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"Import failed: {result.stderr}"

        # Verify installed version matches expected
        installed_version = result.stdout.strip()
        assert installed_version == version, (
            f"Version mismatch: expected {version}, got {installed_version}"
        )


@pytest.mark.integration
@pytest.mark.external_api
@pytest.mark.skip(reason="Requires actual PyPI publish - run manually after production publish")
def test_validate_publish_output_pypi(package_info: dict):
    """
    Contract test for PyPI publish validation.

    Validates that published package:
    - Is accessible on PyPI
    - Can be installed from PyPI
    - Is importable after installation
    - Has correct version

    This test MUST be run manually after PyPI publish.
    """
    package_name = package_info["package_name"]
    version = package_info["version"]

    # Verify package page exists on PyPI
    package_url = f"https://pypi.org/project/{package_name}/{version}/"

    try:
        response = urllib.request.urlopen(package_url)
        assert response.status == 200, f"Package page not found: {package_url}"
    except urllib.error.HTTPError as e:
        pytest.fail(f"Package not accessible on PyPI: {e}")

    # Verify package installable in clean environment
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
        install_cmd = [str(pip), "install", f"{package_name}=={version}"]

        result = subprocess.run(install_cmd, capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"Installation failed: {result.stderr}"

        # Verify importable
        import_cmd = [str(python), "-c", "import codeweaver; print(codeweaver.__version__)"]
        result = subprocess.run(import_cmd, capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"Import failed: {result.stderr}"

        # Verify installed version matches expected
        installed_version = result.stdout.strip()
        assert installed_version == version, (
            f"Version mismatch: expected {version}, got {installed_version}"
        )


@pytest.mark.integration
def test_local_installation():
    """Verify package can be installed locally from built artifacts."""
    project_root = Path(__file__).parent.parent.parent

    # Build package
    import shutil

    dist_dir = project_root / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    result = subprocess.run(
        ["uv", "build"], capture_output=True, text=True, check=False, cwd=project_root
    )

    if result.returncode != 0:
        pytest.fail(f"Build failed: {result.stderr}")

    # Find wheel
    wheels = list(dist_dir.glob("*.whl"))
    if not wheels:
        pytest.fail("No wheel found")

    wheel_path = wheels[0]

    # Test installation in temporary venv
    with tempfile.TemporaryDirectory() as tmpdir:
        venv_path = Path(tmpdir) / "venv"

        # Create virtual environment
        result = subprocess.run(
            ["python", "-m", "venv", str(venv_path)], capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, f"Failed to create venv: {result.stderr}"

        pip = venv_path / "bin" / "pip"
        python = venv_path / "bin" / "python"

        # Install from local wheel
        result = subprocess.run(
            [str(pip), "install", str(wheel_path)], capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, f"Installation failed: {result.stderr}"

        # Verify importable
        result = subprocess.run(
            [str(python), "-c", "import codeweaver; print('OK')"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"Import failed: {result.stderr}"
        assert "OK" in result.stdout, "Package not properly imported"

    # Cleanup
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
