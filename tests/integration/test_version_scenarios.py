# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Integration test: version derivation scenarios."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest


def get_version_from_build(project_root: Path) -> str:
    """Build package and extract version from artifacts."""
    dist_dir = project_root / "dist"

    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    result = subprocess.run(
        ["uv", "build"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Build failed: {result.stderr}")

    wheels = list(dist_dir.glob("*.whl"))
    if not wheels:
        raise RuntimeError("No wheel found")

    wheel_name = wheels[0].name
    match = re.match(r"codeweaver_mcp-(.+?)-py3-none-any\.whl", wheel_name)
    if not match:
        raise RuntimeError(f"Could not extract version from: {wheel_name}")

    return match.group(1)


@pytest.mark.integration
def test_version_scenarios():
    """
    Integration test for all version derivation scenarios.

    Tests three version scenarios:
    1. Tagged release: "0.1.0" (clean semantic version)
    2. Pre-release: "0.1.0rc295+gfc4f90a" (untagged commits)
    3. Dirty: "0.1.0rc295+gfc4f90a.dirty" (uncommitted changes)

    Since we cannot easily manipulate git state in tests,
    this test validates the current state matches expected patterns.
    """
    project_root = Path(__file__).parent.parent.parent

    # Get current git state
    tag_result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    has_tag = tag_result.returncode == 0

    # Get commit distance
    if has_tag:
        latest_tag = tag_result.stdout.strip()
        distance_result = subprocess.run(
            ["git", "rev-list", f"{latest_tag}..HEAD", "--count"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        commit_distance = int(distance_result.stdout.strip()) if distance_result.returncode == 0 else 0
    else:
        commit_distance = 1  # Assume not on tagged commit

    # Check if working directory is dirty
    status_result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    is_dirty = bool(status_result.stdout.strip())

    # Get version from build
    try:
        version = get_version_from_build(project_root)
    except RuntimeError as e:
        pytest.fail(str(e))

    # Validate version format based on git state
    if commit_distance == 0 and not is_dirty:
        # Scenario 1: Tagged release
        # Should be clean semantic version like "0.1.0"
        assert re.match(r"^\d+\.\d+\.\d+$", version) or re.match(r"^\d+\.\d+\.\d+(a|b|rc)\d+$", version), \
            f"Tagged release should have semantic version, got: {version}"
    else:
        # Scenario 2 or 3: Pre-release or dirty
        if is_dirty:
            # Scenario 3: Dirty working directory
            assert "dirty" in version.lower(), \
                f"Dirty working directory should include 'dirty', got: {version}"
        else:
            # Scenario 2: Pre-release (untagged commit)
            assert re.search(r"(rc|dev|\+g)", version), \
                f"Pre-release should include commit indicator, got: {version}"

    # All versions must be PEP 440 compliant
    pep440_pattern = r"^\d+\.\d+\.\d+([a-zA-Z0-9\.\+\-]*)?$"
    assert re.match(pep440_pattern, version), \
        f"Version must be PEP 440 compliant, got: {version}"

    # Cleanup
    dist_dir = project_root / "dist"
    if dist_dir.exists():
        shutil.rmtree(dist_dir)


@pytest.mark.integration
def test_version_consistency_across_formats():
    """Verify version is consistent across wheel and sdist."""
    project_root = Path(__file__).parent.parent.parent
    dist_dir = project_root / "dist"

    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    # Build
    result = subprocess.run(
        ["uv", "build"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"

    # Extract versions from both artifacts
    wheels = list(dist_dir.glob("*.whl"))
    sdists = list(dist_dir.glob("*.tar.gz"))

    assert len(wheels) == 1, "Missing wheel"
    assert len(sdists) == 1, "Missing sdist"

    wheel_match = re.match(r"codeweaver_mcp-(.+?)-py3-none-any\.whl", wheels[0].name)
    sdist_match = re.match(r"codeweaver_mcp-(.+?)\.tar\.gz", sdists[0].name)

    assert wheel_match, f"Could not extract wheel version from: {wheels[0].name}"
    assert sdist_match, f"Could not extract sdist version from: {sdists[0].name}"

    wheel_version = wheel_match.group(1)
    sdist_version = sdist_match.group(1)

    # Versions must match exactly
    assert wheel_version == sdist_version, \
        f"Version mismatch: wheel={wheel_version}, sdist={sdist_version}"

    # Cleanup
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
