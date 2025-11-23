# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for IndexerSettings and FilteredPaths."""

import tempfile

from pathlib import Path

import pytest

from codeweaver.config.indexer import FilteredPaths, IndexerSettings


pytestmark = [pytest.mark.unit]


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)

        # Create directory structure matching the codeweaver.toml excludes
        (project_path / "tests" / "fixtures").mkdir(parents=True, exist_ok=True)
        (project_path / "data").mkdir(parents=True, exist_ok=True)
        (project_path / "specs").mkdir(parents=True, exist_ok=True)
        (project_path / "plans").mkdir(parents=True, exist_ok=True)
        (project_path / "src").mkdir(parents=True, exist_ok=True)

        # Create test files
        (project_path / "tests" / "fixtures" / "deep_nesting.py").write_text("# test file")
        (project_path / "tests" / "fixtures" / "malformed.py").write_text("# malformed")
        (project_path / "tests" / "fixtures" / "sample.go").write_text("// sample")
        (project_path / "data" / "example.txt").write_text("data file")
        (project_path / "specs" / "spec.md").write_text("# Spec")
        (project_path / "plans" / "plan.md").write_text("# Plan")
        (project_path / "src" / "main.py").write_text("# main file")

        yield project_path


@pytest.mark.asyncio
async def test_excludes_are_respected(temp_project_dir):
    """Test that excludes from IndexerSettings are properly applied."""
    # Create IndexerSettings with excludes similar to codeweaver.toml
    settings = IndexerSettings(
        excludes=frozenset([
            "tests/fixtures/deep_nesting.py",
            "tests/fixtures/malformed.py",
            "tests/fixtures/sample.go",
            "data/**",
            "specs/**",
            "plans/**",
        ])
    )

    # Get filtered paths - this calls FilteredPaths.from_settings
    filtered = await FilteredPaths.from_settings(settings, temp_project_dir)

    # Verify that excluded files are in the excludes set
    excluded_paths = {str(p.relative_to(temp_project_dir)) for p in filtered.excludes}

    # These files should be in the excludes
    assert "tests/fixtures/deep_nesting.py" in excluded_paths or any(
        "deep_nesting.py" in str(p) for p in filtered.excludes
    )
    assert "tests/fixtures/malformed.py" in excluded_paths or any(
        "malformed.py" in str(p) for p in filtered.excludes
    )
    assert "tests/fixtures/sample.go" in excluded_paths or any(
        "sample.go" in str(p) for p in filtered.excludes
    )

    # Files in data/**, specs/**, plans/** should also be excluded
    assert any("data" in str(p) for p in filtered.excludes)
    assert any("specs" in str(p) for p in filtered.excludes)
    assert any("plans" in str(p) for p in filtered.excludes)


@pytest.mark.asyncio
async def test_excludes_field_exists(temp_project_dir):
    """Test that excludes field exists and is properly used in FilteredPaths.from_settings."""
    settings = IndexerSettings(excludes=frozenset(["data/**", "specs/**"]))

    # Dump settings to verify the field name
    settings_dict = settings.model_dump(mode="python")

    # The field should be called "excludes", not "excluded_files"
    assert "excludes" in settings_dict
    assert "excluded_files" not in settings_dict

    # Verify the excludes are set correctly
    assert settings_dict["excludes"] == frozenset(["data/**", "specs/**"])


@pytest.mark.asyncio
async def test_empty_excludes(temp_project_dir):
    """Test that empty excludes don't cause issues."""
    settings = IndexerSettings(excludes=frozenset())

    filtered = await FilteredPaths.from_settings(settings, temp_project_dir)

    # With no excludes, only default patterns should apply
    assert isinstance(filtered.excludes, frozenset)


@pytest.mark.asyncio
async def test_glob_pattern_excludes(temp_project_dir):
    """Test that glob patterns in excludes work correctly."""
    settings = IndexerSettings(excludes=frozenset(["data/**", "**/*.go"]))

    filtered = await FilteredPaths.from_settings(settings, temp_project_dir)

    # Files matching glob patterns should be excluded
    excluded_paths_str = {str(p) for p in filtered.excludes}

    # Check that data directory files are excluded
    assert any("data" in p for p in excluded_paths_str)

    # Check that .go files are excluded
    assert any(p.endswith(".go") for p in excluded_paths_str)
