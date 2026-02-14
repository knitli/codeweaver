# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# ruff: noqa: S101, ANN201
# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports
"""Simple standalone tests for lazy import CLI (no pytest fixtures needed)."""

from __future__ import annotations


def test_cli_imports():
    """Test that all CLI modules can be imported."""
    print("Testing CLI module imports...")

    # Test main CLI app
    from tools.lazy_imports.cli import app

    assert app is not None
    assert "lazy-imports" in app.name or app.name == ("lazy-imports",)
    print("✓ CLI app imported")

    # Test types
    from tools.lazy_imports.types import CacheStatistics, ExportGenerationResult, ValidationReport

    assert CacheStatistics is not None
    assert ExportGenerationResult is not None
    assert ValidationReport is not None
    print("✓ Types imported")

    # Test cache
    from tools.lazy_imports.common.cache import AnalysisCache

    assert AnalysisCache is not None
    print("✓ Cache module imported")

    # Test validator
    from tools.lazy_imports.validator import ImportValidator

    assert ImportValidator is not None
    print("✓ Validator module imported")

    # Test export manager
    from tools.lazy_imports.export_manager import PropagationGraph, RuleEngine

    assert RuleEngine is not None
    assert PropagationGraph is not None
    print("✓ Export manager modules imported")


def test_component_initialization():
    """Test that components can be initialized."""
    print("\nTesting component initialization...")

    from tools.lazy_imports.common.cache import AnalysisCache

    cache = AnalysisCache()
    stats = cache.get_stats()

    assert stats.total_entries == 0
    assert stats.valid_entries == 0
    print("✓ Cache initialized")

    from tools.lazy_imports.validator import ImportValidator

    validator = ImportValidator(cache=cache)
    assert validator is not None
    print("✓ Validator initialized")

    from tools.lazy_imports.export_manager import PropagationGraph, RuleEngine

    engine = RuleEngine()
    assert engine is not None
    print("✓ Rule engine initialized")

    graph = PropagationGraph(rule_engine=engine)
    assert graph is not None
    print("✓ Propagation graph initialized")


def test_validation_placeholder():
    """Test that validator returns expected structure."""
    print("\nTesting validator behavior...")

    from tools.lazy_imports.common.cache import AnalysisCache
    from tools.lazy_imports.validator import ImportValidator

    cache = AnalysisCache()
    validator = ImportValidator(cache=cache)

    report = validator.validate()
    assert report.success is True
    assert len(report.errors) == 0
    assert len(report.warnings) == 0
    print("✓ Validator returns valid report structure")


if __name__ == "__main__":
    print("Running lazy imports CLI tests...\n")
    test_cli_imports()
    test_component_initialization()
    test_validation_placeholder()
    print("\n✅ All tests passed!")
