# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports
"""Tests for lazy import CLI."""

from __future__ import annotations

import pytest


class TestLazyImportsCLI:
    """Test suite for lazy imports CLI commands."""

    def test_cli_module_imports(self):
        """Test that CLI module can be imported."""
        from tools.lazy_imports.cli import app

        assert app is not None
        # Cyclopts apps have name as a tuple
        assert "lazy-imports" in app.name or app.name == ("lazy-imports",)

    def test_types_module_imports(self):
        """Test that types module can be imported."""
        from tools.lazy_imports.types import (
            CacheStatistics,
            ExportGenerationResult,
            ValidationReport,
        )

        assert CacheStatistics is not None
        assert ExportGenerationResult is not None
        assert ValidationReport is not None

    def test_cache_module_imports(self):
        """Test that cache module can be imported."""
        from tools.lazy_imports.common.cache import AnalysisCache

        assert AnalysisCache is not None

    def test_validator_module_imports(self):
        """Test that validator module can be imported."""
        from tools.lazy_imports.validator import ImportValidator

        assert ImportValidator is not None

    def test_export_manager_imports(self):
        """Test that export manager modules can be imported."""
        from tools.lazy_imports.export_manager import PropagationGraph, RuleEngine

        assert RuleEngine is not None
        assert PropagationGraph is not None

    def test_cache_initialization(self):
        """Test that cache can be initialized."""
        from tools.lazy_imports.common.cache import AnalysisCache

        cache = AnalysisCache()
        stats = cache.get_stats()

        assert stats.total_entries == 0
        assert stats.valid_entries == 0
        assert stats.hit_rate == 0.0

    def test_validator_initialization(self):
        """Test that validator can be initialized."""
        from tools.lazy_imports.common.cache import AnalysisCache
        from tools.lazy_imports.validator import LazyImportValidator

        cache = AnalysisCache()
        validator = LazyImportValidator(cache=cache)

        assert validator is not None

    def test_rule_engine_initialization(self):
        """Test that rule engine can be initialized."""
        from tools.lazy_imports.export_manager import RuleEngine

        engine = RuleEngine()
        assert engine is not None

    def test_propagation_graph_initialization(self):
        """Test that propagation graph can be initialized."""
        from tools.lazy_imports.export_manager import PropagationGraph, RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        assert graph is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
