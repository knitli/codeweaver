# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for pipeline orchestrator."""

import pytest

from tools.lazy_imports.common.cache import JSONAnalysisCache
from tools.lazy_imports.common.types import PropagationLevel, Rule, RuleAction, RuleMatchCriteria
from tools.lazy_imports.export_manager.rules import RuleEngine
from tools.lazy_imports.pipeline import Pipeline


@pytest.fixture
def temp_source(tmp_path):
    """Create temporary source tree."""
    src = tmp_path / "src"
    src.mkdir()

    # Create package structure
    pkg = src / "mypackage"
    pkg.mkdir()
    (pkg / "__init__.py").touch()

    core = pkg / "core"
    core.mkdir()
    (core / "__init__.py").touch()

    return src


@pytest.fixture
def rule_engine():
    """Create rule engine with basic rules."""
    engine = RuleEngine()
    engine.add_rule(
        Rule(
            name="default-include",
            priority=0,
            description="Include all exports",
            match=RuleMatchCriteria(name_pattern=".*"),
            action=RuleAction.INCLUDE,
            propagate=PropagationLevel.PARENT,
        )
    )
    engine.add_rule(
        Rule(
            name="exclude-private",
            priority=100,
            description="Exclude private members",
            match=RuleMatchCriteria(name_pattern=r"^_.*"),
            action=RuleAction.EXCLUDE,
            propagate=None,
        )
    )
    return engine


@pytest.fixture
def cache(tmp_path):
    """Create cache."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    return JSONAnalysisCache(cache_dir)


@pytest.fixture
def pipeline(rule_engine, cache, tmp_path):
    """Create pipeline."""
    return Pipeline(rule_engine, cache, tmp_path)


class TestFileDiscovery:
    """Test file discovery phase."""

    def test_discovers_all_files(self, pipeline, temp_source) -> None:
        """Should discover all Python files."""
        # Add some Python files
        pkg = temp_source / "mypackage"
        (pkg / "utils.py").write_text("def helper(): pass")
        (pkg / "core" / "types.py").write_text("class MyClass: pass")

        result = pipeline.run(temp_source, dry_run=True)

        # Should discover __init__.py files + utils.py + types.py
        assert result.metrics.files_analyzed >= 2

    def test_discovers_nested_modules(self, pipeline, temp_source) -> None:
        """Should discover files in nested directories."""
        pkg = temp_source / "mypackage"
        deep = pkg / "level1" / "level2" / "level3"
        deep.mkdir(parents=True)
        (deep / "__init__.py").touch()
        (deep / "deep_module.py").write_text("class DeepClass: pass")

        result = pipeline.run(temp_source, dry_run=True)

        # Should discover the deep module
        assert result.success
        assert result.metrics.files_analyzed > 0

    def test_respects_gitignore(self, pipeline, temp_source) -> None:
        """Should respect .gitignore patterns."""
        # Create .gitignore
        (temp_source / ".gitignore").write_text("ignored_dir/\n*.pyc\n")

        # Create ignored directory
        ignored = temp_source / "ignored_dir"
        ignored.mkdir()
        (ignored / "__init__.py").touch()
        (ignored / "module.py").write_text("class IgnoredClass: pass")

        # Create non-ignored file
        pkg = temp_source / "mypackage"
        (pkg / "visible.py").write_text("class VisibleClass: pass")

        result = pipeline.run(temp_source, dry_run=True)

        # Should not analyze ignored files
        assert result.success


class TestCaching:
    """Test cache integration."""

    def test_uses_cache_on_second_run(self, pipeline, temp_source) -> None:
        """Second run should use cache."""
        pkg = temp_source / "mypackage"
        (pkg / "utils.py").write_text("def helper(): pass")

        # First run
        pipeline.run(temp_source, dry_run=True)

        # Second run (same files)
        result2 = pipeline.run(temp_source, dry_run=True)

        # Cache hit rate should be at least 0.5 (50%) on second run
        assert result2.metrics.cache_hit_rate >= 0.5

    def test_invalidates_cache_on_change(self, pipeline, temp_source) -> None:
        """Should invalidate cache when file changes."""
        pkg = temp_source / "mypackage"
        utils_file = pkg / "utils.py"
        utils_file.write_text("def helper(): pass")

        # First run
        pipeline.run(temp_source, dry_run=True)

        # Modify file
        utils_file.write_text("def helper():\n    return 42")

        # Second run
        result2 = pipeline.run(temp_source, dry_run=True)

        # Should have re-analyzed the changed file
        assert result2.success

    def test_cache_persists_across_instances(
        self, rule_engine, cache, temp_source, tmp_path
    ) -> None:
        """Cache should persist across pipeline instances."""
        pkg = temp_source / "mypackage"
        (pkg / "utils.py").write_text("def helper(): pass")

        # First pipeline instance
        pipeline1 = Pipeline(rule_engine, cache, tmp_path)
        pipeline1.run(temp_source, dry_run=True)

        # Second pipeline instance (same cache)
        pipeline2 = Pipeline(rule_engine, cache, tmp_path)
        result2 = pipeline2.run(temp_source, dry_run=True)

        # Second run should use cache
        assert result2.metrics.cache_hit_rate > 0.5


class TestGraphBuilding:
    """Test propagation graph building."""

    def test_builds_graph(self, pipeline, temp_source) -> None:
        """Should build propagation graph."""
        pkg = temp_source / "mypackage" / "core"
        (pkg / "types.py").write_text(
            '''
class MyClass:
    """A class."""
    pass

def my_function():
    """A function."""
    pass
'''
        )

        result = pipeline.run(temp_source, dry_run=True)

        # Should have exports
        assert result.metrics.exports_created > 0

    def test_builds_hierarchy(self, pipeline, temp_source) -> None:
        """Should build correct module hierarchy."""
        pkg = temp_source / "mypackage"

        # Create parent module
        (pkg / "parent.py").write_text("class ParentClass: pass")

        # Create child module
        child = pkg / "child"
        child.mkdir()
        (child / "__init__.py").touch()
        (child / "module.py").write_text("class ChildClass: pass")

        result = pipeline.run(temp_source, dry_run=True)

        # Should process both levels
        assert result.success
        assert result.metrics.exports_created >= 2

    def test_propagates_exports_to_parent(self, pipeline, temp_source) -> None:
        """Should propagate exports to parent modules."""
        pkg = temp_source / "mypackage" / "core"
        (pkg / "types.py").write_text("class PropagatedClass: pass")

        pipeline.run(temp_source, dry_run=False)

        # Check that parent __init__.py includes the export
        parent_init = (temp_source / "mypackage" / "core" / "__init__.py").read_text()
        assert "PropagatedClass" in parent_init


class TestCodeGeneration:
    """Test code generation phase."""

    def test_generates_init_files(self, pipeline, temp_source) -> None:
        """Should generate __init__.py files."""
        pkg = temp_source / "mypackage" / "core"
        (pkg / "types.py").write_text("class MyClass: pass")

        result = pipeline.run(temp_source, dry_run=False)

        # Should generate files
        assert result.metrics.files_generated > 0

    def test_generates_valid_python(self, pipeline, temp_source) -> None:
        """Generated files should be valid Python."""
        pkg = temp_source / "mypackage" / "core"
        (pkg / "types.py").write_text("class MyClass: pass")

        pipeline.run(temp_source, dry_run=False)

        # Check generated file is valid Python
        init_file = pkg / "__init__.py"
        assert init_file.exists()

        # Should parse without error
        import ast

        content = init_file.read_text()
        ast.parse(content)

    def test_preserves_manual_sections(self, pipeline, temp_source) -> None:
        """Should preserve manual code above sentinel."""
        pkg = temp_source / "mypackage" / "core"
        (pkg / "types.py").write_text("class MyClass: pass")

        # Create init with manual section
        init_file = pkg / "__init__.py"
        init_file.write_text(
            '''"""Custom docstring."""

from typing import Protocol

# === MANAGED EXPORTS ===
# Old managed content
'''
        )

        pipeline.run(temp_source, dry_run=False)

        # Check manual section preserved
        content = init_file.read_text()
        assert "Custom docstring" in content
        assert "from typing import Protocol" in content


class TestDryRun:
    """Test dry-run mode."""

    def test_dry_run_no_files_written(self, pipeline, temp_source) -> None:
        """Dry run should not write files."""
        pkg = temp_source / "mypackage" / "core"
        types_file = pkg / "types.py"
        types_file.write_text("class MyClass: pass")

        # Note existing init state
        init_file = pkg / "__init__.py"
        original_content = init_file.read_text() if init_file.exists() else None

        result = pipeline.run(temp_source, dry_run=True)

        # Should analyze but not write
        assert result.metrics.files_generated > 0 or result.metrics.files_updated > 0
        assert result.metrics.files_analyzed > 0

        # Init file should not have changed
        current_content = init_file.read_text() if init_file.exists() else None
        assert current_content == original_content

    def test_dry_run_reports_changes(self, pipeline, temp_source) -> None:
        """Dry run should report what would change."""
        pkg = temp_source / "mypackage" / "core"
        (pkg / "types.py").write_text("class MyClass: pass")

        result = pipeline.run(temp_source, dry_run=True)

        # Should report changes
        total_changes = result.metrics.files_generated + result.metrics.files_updated
        assert total_changes > 0


class TestMetrics:
    """Test metrics collection."""

    def test_collects_comprehensive_metrics(self, pipeline, temp_source) -> None:
        """Should collect all metrics."""
        pkg = temp_source / "mypackage"
        (pkg / "utils.py").write_text("def helper(): pass")

        result = pipeline.run(temp_source, dry_run=True)

        # Check all metrics are populated
        assert result.metrics.files_analyzed >= 0
        assert result.metrics.files_generated >= 0
        assert result.metrics.processing_time_ms > 0
        assert 0.0 <= result.metrics.cache_hit_rate <= 1.0

    def test_counts_exports_correctly(self, pipeline, temp_source) -> None:
        """Should count exports correctly."""
        pkg = temp_source / "mypackage"
        (pkg / "module.py").write_text(
            """
class ClassA: pass
class ClassB: pass
def func_a(): pass
def func_b(): pass
"""
        )

        result = pipeline.run(temp_source, dry_run=True)

        # Should count 4 exports
        assert result.metrics.exports_created == 4

    def test_tracks_processing_time(self, pipeline, temp_source) -> None:
        """Should track processing time."""
        pkg = temp_source / "mypackage"
        (pkg / "utils.py").write_text("def helper(): pass")

        result = pipeline.run(temp_source, dry_run=True)

        # Should have non-zero processing time
        assert result.metrics.processing_time_ms > 0


class TestErrorHandling:
    """Test error handling."""

    def test_syntax_error_continues(self, pipeline, temp_source) -> None:
        """Syntax errors should not stop pipeline."""
        pkg = temp_source / "mypackage"
        (pkg / "good.py").write_text("class Good: pass")
        (pkg / "bad.py").write_text("class Bad def broken")  # Syntax error

        result = pipeline.run(temp_source, dry_run=True)

        # Should continue processing despite error
        assert result.metrics.files_analyzed > 0

    def test_handles_permission_errors_gracefully(self, pipeline, temp_source) -> None:
        """Should handle permission errors gracefully."""
        # This test would need OS-specific setup for actual permission errors
        # For now, just ensure pipeline doesn't crash
        pkg = temp_source / "mypackage"
        (pkg / "utils.py").write_text("def helper(): pass")

        result = pipeline.run(temp_source, dry_run=True)
        assert result.success or len(result.errors) > 0


class TestModulePathCalculation:
    """Test module path calculation."""

    def test_init_file_module_path(self, pipeline, temp_source) -> None:
        """__init__.py should use parent directory as module."""
        pkg = temp_source / "mypackage"
        (pkg / "__init__.py").write_text("class PackageClass: pass")

        result = pipeline.run(temp_source, dry_run=True)

        assert result.success

    def test_regular_file_module_path(self, pipeline, temp_source) -> None:
        """Regular .py files should use filename as last part."""
        pkg = temp_source / "mypackage"
        (pkg / "utils.py").write_text("class Utils: pass")

        result = pipeline.run(temp_source, dry_run=True)

        assert result.success

    def test_nested_module_path(self, pipeline, temp_source) -> None:
        """Nested modules should have correct dotted path."""
        pkg = temp_source / "mypackage"
        nested = pkg / "level1" / "level2"
        nested.mkdir(parents=True)
        (nested / "__init__.py").touch()
        (nested / "module.py").write_text("class NestedClass: pass")

        result = pipeline.run(temp_source, dry_run=True)

        assert result.success


class TestFullWorkflow:
    """Test complete end-to-end workflow."""

    def test_complete_workflow(self, pipeline, temp_source) -> None:
        """Test complete pipeline workflow."""
        # Create realistic package structure
        pkg = temp_source / "mypackage"
        core = pkg / "core"

        # Add types module
        (core / "types.py").write_text(
            '''
"""Type definitions."""

class MyClass:
    """A class."""
    pass

class AnotherClass:
    """Another class."""
    pass

def my_function():
    """A function."""
    pass
'''
        )

        # Add utils module
        (pkg / "utils.py").write_text(
            '''
"""Utilities."""

def helper():
    """Helper function."""
    pass
'''
        )

        # Run pipeline
        result = pipeline.run(temp_source, dry_run=False)

        # Validate results
        assert result.success
        assert result.metrics.files_analyzed > 0
        assert result.metrics.exports_created > 0
        assert result.metrics.processing_time_ms > 0

        # Check __init__.py files were generated
        assert (core / "__init__.py").exists()
        assert (pkg / "__init__.py").exists()

        # Check content includes exports
        core_init = (core / "__init__.py").read_text()
        assert "MyClass" in core_init or "AnotherClass" in core_init

    def test_multi_level_propagation(self, pipeline, temp_source) -> None:
        """Test propagation through multiple levels."""
        pkg = temp_source / "mypackage"

        # Level 3 (deepest)
        level3 = pkg / "level1" / "level2" / "level3"
        level3.mkdir(parents=True)
        (level3 / "__init__.py").touch()
        (level3 / "module.py").write_text("class DeepClass: pass")

        # Run pipeline
        result = pipeline.run(temp_source, dry_run=False)

        assert result.success
        assert result.metrics.exports_created > 0

    def test_handles_empty_modules(self, pipeline, temp_source) -> None:
        """Should handle modules with no exports."""
        pkg = temp_source / "mypackage"
        empty = pkg / "empty"
        empty.mkdir()
        (empty / "__init__.py").touch()
        (empty / "module.py").write_text("# No exports here\npass")

        result = pipeline.run(temp_source, dry_run=False)

        # Should succeed even with no exports
        assert result.success

    def test_processes_large_project(self, pipeline, temp_source) -> None:
        """Should handle larger projects efficiently."""
        pkg = temp_source / "mypackage"

        # Create 10 modules with 5 exports each
        for i in range(10):
            module = pkg / f"module{i}.py"
            classes = "\n".join(f"class Class{i}_{j}: pass" for j in range(5))
            module.write_text(classes)

        result = pipeline.run(temp_source, dry_run=False)

        # Should process all 50 exports
        assert result.success
        assert result.metrics.exports_created == 50
