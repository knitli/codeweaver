# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Contract test: validate package publishing and installation."""

import re
import subprocess
import tempfile
import urllib.error
import urllib.request

from pathlib import Path

import pytest


@pytest.fixture
def package_info():
    """Get version from import."""
    from codeweaver import __version__ as version

    package_name = "code-weaver"  # PyPI normalized name
    # to get the current package version, we need to read it from the source, but we'll probably have a dirty/non-release version so we need to adjust for that
    version_pattern = re.compile(
        r"^(?P<version>\d{1,3}\.\d{1,3}\.\d{1,3})(?P<pre_kind>[ab]|rc)?(?P<pre_release>\d*)\.?(dev\d+)?([+]g[\da-f]+)?$"
    )
    match = version_pattern.match(version)
    if not match:
        pytest.fail(f"Version '{version}' does not match expected pattern")
    # type checker doesn't understand we checked for None
    assert match

    # Extract the base version without dev/git parts
    base_version = match["version"]
    pre_kind = match["pre_kind"]
    pre_release = match["pre_release"]

    # Build the published version (without dev/git hash)
    published_version = base_version
    if pre_kind:
        published_version += pre_kind
        if pre_release:
            published_version += pre_release

    # Skip if this is a release candidate
    if pre_kind == "rc":
        pytest.skip("Release candidate version detected; skipping publish validation tests")

    # Check if this is a dev version (has dev or git hash parts)
    is_dev_version = "dev" in version or "+g" in version

    project_root = Path(__file__).parent.parent.parent
    dist_dir = project_root / "dist"

    return {
        "package_name": package_name,
        "version": version,
        "published_version": published_version,
        "is_dev_version": is_dev_version,
        "dist_dir": dist_dir,
        "project_root": project_root,
    }


@pytest.mark.integration
@pytest.mark.external_api
def test_validate_publish_output_testpypi(package_info: dict):
    """
    Contract test for TestPyPI publish validation.

    Validates that published package:
    - Is accessible on TestPyPI
    - Can be installed from TestPyPI
    - Is importable after installation
    - Has correct version

    This test MUST be run manually after TestPyPI publish.
    Skips if running from a development version (with dev/git parts).
    """
    package_name = package_info["package_name"]
    published_version = package_info["published_version"]
    is_dev_version = package_info["is_dev_version"]

    if is_dev_version:
        pytest.skip(
            f"Skipping TestPyPI validation for development version. "
            f"Published version would be: {published_version}"
        )

    # Verify package page exists on TestPyPI
    package_url = f"https://test.pypi.org/project/{package_name}/{published_version}/"

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
            f"{package_name}=={published_version}",
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
        assert installed_version == published_version, (
            f"Version mismatch: expected {published_version}, got {installed_version}"
        )


@pytest.mark.integration
@pytest.mark.external_api
def test_validate_publish_output_pypi(package_info: dict):
    """
    Contract test for PyPI publish validation.

    Validates that published package:
    - Is accessible on PyPI
    - Can be installed from PyPI
    - Is importable after installation
    - Has correct version

    Skips if running from a development version (with dev/git parts).
    """
    package_name = package_info["package_name"]
    published_version = package_info["published_version"]
    is_dev_version = package_info["is_dev_version"]

    if is_dev_version:
        pytest.skip(
            f"Skipping PyPI validation for development version. "
            f"Published version would be: {published_version}"
        )

    # Verify package page exists on PyPI
    package_url = f"https://pypi.org/project/{package_name}/{published_version}/"

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
        install_cmd = [str(pip), "install", f"{package_name}=={published_version}"]

        result = subprocess.run(install_cmd, capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"Installation failed: {result.stderr}"

        # Verify importable
        import_cmd = [str(python), "-c", "import codeweaver; print(codeweaver.__version__)"]
        result = subprocess.run(import_cmd, capture_output=True, text=True, check=False)
        assert result.returncode == 0, f"Import failed: {result.stderr}"

        # Verify installed version matches expected
        installed_version = result.stdout.strip()
        assert installed_version == published_version, (
            f"Version mismatch: expected {published_version}, got {installed_version}"
        )


@pytest.mark.slow
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
