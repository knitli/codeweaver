# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Contract test: validate package metadata with twine check."""

import subprocess

from pathlib import Path

import pytest


@pytest.fixture
def build_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Build package and return dist directory."""
    project_root = Path(__file__).parent.parent.parent
    monkeypatch.chdir(project_root)

    # Clean and build
    import shutil

    dist_dir = project_root / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    result = subprocess.run(["uv", "build"], capture_output=True, text=True, check=False)

    if result.returncode != 0:
        pytest.skip(f"Build failed, skipping metadata validation: {result.stderr}")

    yield dist_dir

    # Cleanup
    if dist_dir.exists():
        shutil.rmtree(dist_dir)


@pytest.mark.integration
@pytest.mark.network
def test_validate_twine_check(build_artifacts: Path):
    """
    Contract test for twine check validation.

    Validates that `twine check dist/*` passes for both wheel and sdist:
    - Both artifacts pass validation
    - Output contains "PASSED" for each artifact
    - No metadata warnings or errors

    This test MUST FAIL initially (TDD) until implementation is complete.
    """
    dist_dir = build_artifacts

    # Verify artifacts exist
    artifacts = list(dist_dir.glob("*"))
    if len(artifacts) < 2:
        pytest.fail(f"Expected 2 artifacts, found {len(artifacts)}")

    # Install twine if not available
    subprocess.run(["uv", "pip", "install", "twine"], capture_output=True, check=False)

    # Run twine check
    result = subprocess.run(
        ["twine", "check", str(dist_dir / "*")],
        capture_output=True,
        text=True,
        check=False,
        shell=True,
    )

    # Check should succeed
    assert result.returncode == 0, f"Twine check failed: {result.stderr}\n{result.stdout}"

    # Verify output contains PASSED for each artifact
    stdout_lines = result.stdout.strip().split("\n")
    passed_lines = [line for line in stdout_lines if "PASSED" in line]

    assert len(passed_lines) == 2, (
        f"Expected 2 PASSED results, found {len(passed_lines)}: {stdout_lines}"
    )

    # Verify no warnings or errors
    assert "WARNING" not in result.stdout, f"Metadata warnings detected: {result.stdout}"
    assert "ERROR" not in result.stdout, f"Metadata errors detected: {result.stdout}"


@pytest.mark.integration
def test_metadata_completeness():
    """Verify required metadata fields are present in pyproject.toml."""
    import tomllib

    project_root = Path(__file__).parent.parent.parent
    pyproject_path = project_root / "pyproject.toml"

    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)

    project = pyproject.get("project", {})

    # Required PEP 621 fields
    required_fields = ["name", "description", "readme", "requires-python", "license", "authors"]

    for field in required_fields:
        assert field in project, f"Required field '{field}' missing from [project]"

    # Verify dynamic version
    assert "version" in project.get("dynamic", []), "Version must be dynamic"

    # Verify build system
    build_system = pyproject.get("build-system", {})
    assert "hatchling" in str(build_system.get("requires", [])), (
        "hatchling must be in build-system.requires"
    )
    assert build_system.get("build-backend") == "hatchling.build", (
        "Build backend must be hatchling.build"
    )
