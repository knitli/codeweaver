# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Contract test: validate version derivation from git state."""

import re
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def git_state():
    """Get current git state information."""
    project_root = Path(__file__).parent.parent.parent

    # Get latest tag
    tag_result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        capture_output=True,
        text=True,
        check=False,
        cwd=project_root,
    )
    latest_tag = tag_result.stdout.strip() if tag_result.returncode == 0 else None

    # Get commit distance
    if latest_tag:
        distance_result = subprocess.run(
            ["git", "rev-list", f"{latest_tag}..HEAD", "--count"],
            capture_output=True,
            text=True,
            check=False,
            cwd=project_root,
        )
        commit_distance = int(distance_result.stdout.strip()) if distance_result.returncode == 0 else 0
    else:
        commit_distance = 0

    # Get commit hash
    hash_result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        cwd=project_root,
    )
    commit_hash = hash_result.stdout.strip() if hash_result.returncode == 0 else ""

    # Check if working directory is clean
    status_result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
        cwd=project_root,
    )
    is_dirty = bool(status_result.stdout.strip()) if status_result.returncode == 0 else False

    return {
        "latest_tag": latest_tag,
        "commit_distance": commit_distance,
        "commit_hash": commit_hash,
        "is_dirty": is_dirty,
        "project_root": project_root,
    }


@pytest.mark.integration
def test_validate_version_derivation(git_state: dict):
    """
    Contract test for version derivation from git state.

    Validates version follows these patterns:
    - Tagged release: "0.1.0" (clean semantic version)
    - Pre-release: "0.1.0rc295+gfc4f90a" (with commit distance and hash)
    - Dirty working directory: appends ".dirty" suffix

    This test MUST FAIL initially (TDD) until implementation is complete.
    """
    project_root = git_state["project_root"]

    # Build to generate version
    import shutil
    dist_dir = project_root / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    result = subprocess.run(
        ["uv", "build"],
        capture_output=True,
        text=True,
        check=False,
        cwd=project_root,
    )

    if result.returncode != 0:
        pytest.fail(f"Build failed: {result.stderr}")

    # Get version from built artifacts
    artifacts = list(dist_dir.glob("*.whl"))
    if not artifacts:
        pytest.fail("No wheel artifact found")

    wheel_name = artifacts[0].name
    # Extract version from wheel filename: codeweaver_mcp-{version}-py3-none-any.whl
    match = re.match(r"codeweaver_mcp-(.+?)-py3-none-any\.whl", wheel_name)
    if not match:
        pytest.fail(f"Could not extract version from wheel: {wheel_name}")

    derived_version = match.group(1)

    # Validate version format based on git state
    if git_state["commit_distance"] == 0 and not git_state["is_dirty"]:
        # Tagged release: should be clean semantic version
        # Format: X.Y.Z or X.Y.Z.devN or X.Y.ZaN or X.Y.ZbN or X.Y.ZrcN
        assert re.match(r"^\d+\.\d+\.\d+", derived_version), \
            f"Tagged release should have semantic version, got: {derived_version}"
    else:
        # Pre-release or dirty: should include commit info
        # Format: X.Y.ZrcN+gHASH or X.Y.ZrcN+gHASH.dirty
        # or X.Y.Z.devN+gHASH or X.Y.Z.devN+gHASH.dirty
        if git_state["is_dirty"]:
            assert "dirty" in derived_version.lower(), \
                f"Dirty working directory should include 'dirty', got: {derived_version}"

        if git_state["commit_distance"] > 0:
            # Should include commit indicator (rc, dev, or similar)
            assert re.search(r"(rc|dev|\+g)", derived_version), \
                f"Pre-release should include commit indicator, got: {derived_version}"

    # Version must be PEP 440 compliant
    # Basic PEP 440 pattern check
    pep440_pattern = r"^\d+\.\d+\.\d+([a-zA-Z0-9\.\+\-]*)?$"
    assert re.match(pep440_pattern, derived_version), \
        f"Version must be PEP 440 compliant, got: {derived_version}"

    # Cleanup
    if dist_dir.exists():
        shutil.rmtree(dist_dir)


@pytest.mark.integration
def test_version_consistency():
    """Verify version is consistent across package metadata."""
    project_root = Path(__file__).parent.parent.parent

    # Build package
    import shutil
    dist_dir = project_root / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    result = subprocess.run(
        ["uv", "build"],
        capture_output=True,
        text=True,
        check=False,
        cwd=project_root,
    )

    if result.returncode != 0:
        pytest.skip(f"Build failed: {result.stderr}")

    # Extract version from wheel
    wheels = list(dist_dir.glob("*.whl"))
    sdists = list(dist_dir.glob("*.tar.gz"))

    if not wheels or not sdists:
        pytest.fail("Missing wheel or sdist artifact")

    wheel_name = wheels[0].name
    sdist_name = sdists[0].name

    # Extract versions
    wheel_match = re.match(r"codeweaver_mcp-(.+?)-py3-none-any\.whl", wheel_name)
    sdist_match = re.match(r"codeweaver_mcp-(.+?)\.tar\.gz", sdist_name)

    if not wheel_match or not sdist_match:
        pytest.fail(f"Could not extract versions from artifacts: {wheel_name}, {sdist_name}")

    wheel_version = wheel_match.group(1)
    sdist_version = sdist_match.group(1)

    # Versions must match
    assert wheel_version == sdist_version, \
        f"Version mismatch: wheel={wheel_version}, sdist={sdist_version}"

    # Cleanup
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
