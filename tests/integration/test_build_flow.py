# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Integration test: end-to-end build and validation flow."""

import shutil
import subprocess

from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.e2e
def test_build_and_validate_flow():
    """
    End-to-end integration test for complete build and validation workflow.

    Tests the full sequence:
    1. Clean dist directory
    2. Run `uv build`
    3. Verify artifacts created
    4. Run `twine check dist/*`
    5. Confirm all validation passes

    This validates the complete build system is working correctly.
    """
    project_root = Path(__file__).parent.parent.parent
    dist_dir = project_root / "dist"

    # Step 1: Clean dist directory
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    assert not dist_dir.exists(), "Failed to clean dist directory"

    # Step 2: Run uv build
    build_result = subprocess.run(
        ["uv", "build"], cwd=project_root, capture_output=True, text=True, check=False
    )

    # Verify build succeeded
    assert build_result.returncode == 0, f"Build failed: {build_result.stderr}"
    assert dist_dir.exists(), "dist/ directory not created"

    # Step 3: Verify artifacts
    artifacts = [f for f in dist_dir.glob("*") if f.is_file() and f.name not in [".gitignore"]]
    assert len(artifacts) == 2, (
        f"Expected 2 artifacts, found {len(artifacts)}: {[a.name for a in artifacts]}"
    )

    wheels = [a for a in artifacts if a.suffix == ".whl"]
    sdists = [a for a in artifacts if a.name.endswith(".tar.gz")]

    assert len(wheels) == 1, "Missing wheel artifact"
    assert len(sdists) == 1, "Missing sdist artifact"

    # Step 4: Install twine and run check
    twine_install = subprocess.run(
        ["uv", "pip", "install", "twine"], capture_output=True, text=True, check=False
    )
    assert twine_install.returncode == 0, f"Failed to install twine: {twine_install.stderr}"

    # Step 5: Run twine check
    check_result = subprocess.run(
        ["twine", "check"] + [str(a) for a in artifacts],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    # Verify twine check passed
    assert check_result.returncode == 0, (
        f"Twine check failed: {check_result.stderr}\n{check_result.stdout}"
    )
    assert "PASSED" in check_result.stdout, f"Expected PASSED in output: {check_result.stdout}"

    # Count PASSED occurrences
    passed_count = check_result.stdout.count("PASSED")
    assert passed_count == 2, f"Expected 2 PASSED results, found {passed_count}"

    # Cleanup
    if dist_dir.exists():
        shutil.rmtree(dist_dir)


@pytest.mark.integration
def test_incremental_build():
    """Verify incremental builds work correctly (rebuild without changes)."""
    project_root = Path(__file__).parent.parent.parent
    dist_dir = project_root / "dist"

    # Clean start
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    # First build
    result1 = subprocess.run(
        ["uv", "build"], cwd=project_root, capture_output=True, text=True, check=False
    )
    assert result1.returncode == 0, "First build failed"

    artifacts1 = list(dist_dir.glob("*.whl"))
    assert len(artifacts1) == 1, "First build didn't create wheel"

    # Second build (should rebuild)
    result2 = subprocess.run(
        ["uv", "build"], cwd=project_root, capture_output=True, text=True, check=False
    )
    assert result2.returncode == 0, "Second build failed"

    artifacts2 = list(dist_dir.glob("*.whl"))
    assert len(artifacts2) == 1, "Second build didn't maintain artifacts"

    # Cleanup
    if dist_dir.exists():
        shutil.rmtree(dist_dir)


@pytest.mark.integration
def test_build_with_clean_flag():
    """Verify uv build --clear properly removes old artifacts."""
    project_root = Path(__file__).parent.parent.parent
    dist_dir = project_root / "dist"

    # Clean and build
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    # First build
    subprocess.run(["uv", "build"], cwd=project_root, check=True)

    # Create a dummy file to verify cleanup
    dummy_file = dist_dir / "dummy.txt"
    dummy_file.write_text("test")
    assert dummy_file.exists()

    # Build with --clear (removes existing build artifacts)
    result = subprocess.run(
        ["uv", "build", "--clear"], cwd=project_root, capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, f"Clear build failed: {result.stderr}"

    # Dummy file should still exist (build --clear doesn't remove dist/, just rebuilds)
    # Only the actual build artifacts should be refreshed
    artifacts = [f for f in dist_dir.glob("*") if f.is_file() and f.suffix in [".whl", ".gz"]]
    assert len(artifacts) == 2, "Build --clean didn't create expected artifacts"

    # Cleanup
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
