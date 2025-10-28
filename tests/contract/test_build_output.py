# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Contract test: validate build output artifacts."""

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def clean_dist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Clean dist directory and change to temporary project directory."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(exist_ok=True)

    # Change to project root for build
    project_root = Path(__file__).parent.parent.parent
    monkeypatch.chdir(project_root)

    # Clean existing dist
    import shutil
    if (project_root / "dist").exists():
        shutil.rmtree(project_root / "dist")

    yield project_root / "dist"

    # Cleanup
    if (project_root / "dist").exists():
        shutil.rmtree(project_root / "dist")


@pytest.mark.integration
def test_validate_build_output(clean_dist: Path):
    """
    Contract test for build command output.

    Validates that `uv build` creates exactly 2 artifacts:
    - One wheel (.whl) with correct naming convention
    - One source distribution (.tar.gz) with correct naming convention
    - Both artifacts are non-empty
    - Versions match across artifacts

    This test MUST FAIL initially (TDD) until implementation is complete.
    """
    dist_dir = clean_dist

    # Run build command
    result = subprocess.run(
        ["uv", "build"],
        capture_output=True,
        text=True,
        check=False,
    )

    # Build should succeed
    assert result.returncode == 0, f"Build failed: {result.stderr}"

    # Verify artifacts created (filter out .gitignore and other non-artifacts)
    all_files = list(dist_dir.glob("*"))
    artifacts = [a for a in all_files if a.is_file() and a.name not in [".gitignore", ".DS_Store"]]
    assert len(artifacts) == 2, f"Expected 2 artifacts, found {len(artifacts)}: {[a.name for a in artifacts]}"

    # Must include one wheel and one sdist
    wheels = [a for a in artifacts if a.suffix == ".whl"]
    sdists = [a for a in artifacts if a.name.endswith(".tar.gz")]

    assert len(wheels) == 1, f"Expected exactly 1 wheel, found {len(wheels)}"
    assert len(sdists) == 1, f"Expected exactly 1 sdist, found {len(sdists)}"

    wheel = wheels[0]
    sdist = sdists[0]

    # Filenames must follow conventions
    assert wheel.name.startswith("codeweaver_mcp-"), f"Wheel name must start with package name, got: {wheel.name}"
    assert "-py3-none-any.whl" in wheel.name, f"Wheel must be pure Python, got: {wheel.name}"

    assert sdist.name.startswith("codeweaver_mcp-"), f"Sdist name must start with package name, got: {sdist.name}"
    assert sdist.name.endswith(".tar.gz"), f"Sdist must be .tar.gz, got: {sdist.name}"

    # Artifacts must be non-empty
    assert wheel.stat().st_size > 0, "Wheel must be non-empty"
    assert sdist.stat().st_size > 0, "Sdist must be non-empty"

    # Version must be consistent across artifacts
    # Extract version from both filenames and verify they match
    # Format: codeweaver_mcp-{version}-py3-none-any.whl
    # Format: codeweaver_mcp-{version}.tar.gz
    wheel_parts = wheel.name.split("-")
    wheel_version = wheel_parts[1] if len(wheel_parts) > 1 else ""

    sdist_parts = sdist.name.replace(".tar.gz", "").split("-")
    sdist_version = sdist_parts[1] if len(sdist_parts) > 1 else ""

    assert wheel_version == sdist_version, f"Version mismatch: wheel={wheel_version}, sdist={sdist_version}"
    assert wheel_version != "", "Version must not be empty"


@pytest.mark.integration
def test_build_command_success():
    """Verify uv build command succeeds with expected output."""
    result = subprocess.run(
        ["uv", "build", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    # At minimum, uv build command should be available
    assert result.returncode == 0, "uv build command not available"
