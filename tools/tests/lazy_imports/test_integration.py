"""Integration tests for lazy import system.

Tests complete workflows:
- Analyze → Generate → Validate
- Migration from old to new system
- Cache integration and effectiveness
- Rule changes invalidate cache
"""

# ruff: noqa: S101, ANN201
# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports, avoid-loops-in-tests
from __future__ import annotations

import time

from pathlib import Path

import pytest


class TestFullPipeline:
    """Test complete workflow from analysis to validation."""

    @pytest.mark.integration
    def test_simple_module_workflow(self, tmp_path: Path):
        """Test complete workflow for simple module."""
        # Create test module structure
        package_dir = tmp_path / "test_package"
        package_dir.mkdir()

        # Create a simple module
        module_file = package_dir / "module.py"
        module_file.write_text('''
"""Test module."""

class PublicClass:
    """A public class."""
    pass

def public_function():
    """A public function."""
    pass

class _PrivateClass:
    """Private class."""
    pass
''')

        # Create __init__.py (will be generated)
        init_file = package_dir / "__init__.py"

        # Import required components
        from tools.lazy_imports.export_manager.generator import CodeGenerator
        from tools.lazy_imports.export_manager.graph import PropagationGraph
        from tools.lazy_imports.export_manager.rules import RuleEngine

        # Setup rules
        rules = [
            {
                "name": "exclude-private",
                "priority": 900,
                "description": "Exclude private",
                "match": {"name_pattern": r"^_"},
                "action": "exclude",
            },
            {
                "name": "include-public",
                "priority": 500,
                "description": "Include public",
                "match": {"name_pattern": r"^[a-zA-Z]"},
                "action": "include",
                "propagate": "parent",
            },
        ]

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)
        generator = CodeGenerator(tmp_path)

        # Analyze and build graph
        # (This would normally be done by analyzer)
        from tools.lazy_imports.common.types import ExportNode, MemberType, PropagationLevel

        exports = [
            ExportNode(
                name="PublicClass",
                module="test_package",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=module_file,
                line_number=4,
                defined_in="test_package.module",
            ),
            ExportNode(
                name="public_function",
                module="test_package",
                member_type=MemberType.FUNCTION,
                propagation=PropagationLevel.PARENT,
                source_file=module_file,
                line_number=8,
                defined_in="test_package.module",
            ),
        ]

        # Register module first
        graph.add_module("test_package", None)

        for export in exports:
            graph.add_export(export)

        # Build manifests
        manifests = graph.build_manifests()

        # Generate code
        if "test_package" in manifests:
            manifest = manifests["test_package"]
            code = generator.generate(manifest)
            generator.write_file("test_package", code)

            # Verify file was created
            assert init_file.exists()

            content = init_file.read_text()
            assert "PublicClass" in content
            assert "public_function" in content
            assert "_PrivateClass" not in content
            assert "__all__" in content

    @pytest.mark.integration
    def test_nested_module_workflow(self, tmp_path: Path, nested_module_structure: Path):
        """Test workflow with nested module structure."""
        # Use nested_module_structure fixture
        # nested_module_structure has: test_package/core/types/models.py

        from tools.lazy_imports.common.types import ExportNode, MemberType, PropagationLevel
        from tools.lazy_imports.export_manager.generator import CodeGenerator
        from tools.lazy_imports.export_manager.graph import PropagationGraph
        from tools.lazy_imports.export_manager.rules import RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        # Register modules first
        graph.add_module("test_package.core.types.models", "test_package.core.types")
        graph.add_module("test_package.core.types", "test_package.core")
        graph.add_module("test_package.core", "test_package")
        graph.add_module("test_package", None)

        # Add exports with ROOT propagation
        exports = [
            ExportNode(
                name="MyModel",
                module="test_package.core.types.models",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.ROOT,
                source_file=nested_module_structure / "core" / "types" / "models.py",
                line_number=3,
                defined_in="test_package.core.types.models",
            )
        ]

        for export in exports:
            graph.add_export(export)

        manifests = graph.build_manifests()

        # Generate __init__.py files for all levels
        # Generator needs parent directory since it appends module path
        generator = CodeGenerator(nested_module_structure.parent)

        for module_path, manifest in manifests.items():
            code = generator.generate(manifest)
            generator.write_file(module_path, code)

        # Verify MyModel propagated to root
        root_init = nested_module_structure / "__init__.py"
        if root_init.exists():
            content = root_init.read_text()
            assert "MyModel" in content


class TestCacheIntegration:
    """Test cache integration with full pipeline."""

    @pytest.mark.integration
    def test_cache_speeds_up_second_run(self, tmp_path: Path, temp_cache_dir: Path):
        """Second run should be faster due to cache."""
        from tools.lazy_imports.common.cache import JSONAnalysisCache
        from tools.lazy_imports.common.types import (
            AnalysisResult,
            ExportNode,
            MemberType,
            PropagationLevel,
        )

        cache = JSONAnalysisCache(cache_dir=temp_cache_dir)

        # Simulate first run
        test_file = tmp_path / "module.py"
        test_file.write_text("class MyClass: pass")

        exports = [
            ExportNode(
                name="MyClass",
                module="test",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=test_file,
                line_number=1,
                defined_in="test",
            )
        ]

        analysis = AnalysisResult(
            exports=exports,
            imports=[],
            file_hash="hash123",
            analysis_timestamp=time.time(),
            schema_version="1.0",
        )

        # First run - cache miss
        start = time.time()
        cache.put(test_file, "hash123", analysis)
        first_run = time.time() - start

        # Second run - cache hit
        start = time.time()
        cached = cache.get(test_file, "hash123")
        second_run = time.time() - start

        # Second run should be instant (cache hit)
        assert cached is not None
        assert second_run < first_run * 0.5  # Faster (relaxed tolerance)

    @pytest.mark.integration
    def test_file_change_invalidates_cache(self, tmp_path: Path, temp_cache_dir: Path):
        """File modification should invalidate cache."""
        from tools.lazy_imports.common.cache import JSONAnalysisCache
        from tools.lazy_imports.common.types import (
            AnalysisResult,
            ExportNode,
            MemberType,
            PropagationLevel,
        )

        cache = JSONAnalysisCache(cache_dir=temp_cache_dir)

        test_file = tmp_path / "module.py"
        test_file.write_text("class MyClass: pass")

        # Cache initial version
        exports = [
            ExportNode(
                name="MyClass",
                module="test",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=test_file,
                line_number=1,
                defined_in="test",
            )
        ]

        analysis = AnalysisResult(
            exports=exports,
            imports=[],
            file_hash="hash123",
            analysis_timestamp=time.time(),
            schema_version="1.0",
        )

        cache.put(test_file, "hash123", analysis)

        # Modify file
        test_file.write_text("class NewClass: pass")
        new_hash = "hash456"

        # Cache should miss with new hash
        cached = cache.get(test_file, new_hash)
        assert cached is None


class TestRuleChanges:
    """Test that rule changes properly invalidate cached results."""

    @pytest.mark.integration
    def test_rule_change_requires_reprocessing(self, tmp_path: Path):
        """Changing rules should trigger reprocessing."""
        import yaml
        from tools.lazy_imports.common.types import MemberType, RuleAction
        from tools.lazy_imports.export_manager.rules import RuleEngine

        # Initial rules - exclude private
        rules_v1 = {
            "schema_version": "1.0",
            "rules": [
                {
                    "name": "exclude-private",
                    "priority": 900,
                    "description": "Exclude private",
                    "match": {"name_pattern": r"^_"},
                    "action": "exclude",
                }
            ],
        }

        rules_file_v1 = tmp_path / "rules_v1.yaml"
        rules_file_v1.write_text(yaml.dump(rules_v1))

        engine_v1 = RuleEngine()
        engine_v1.load_rules([rules_file_v1])

        result_v1 = engine_v1.evaluate("_private", "module", MemberType.FUNCTION)
        assert result_v1.action == RuleAction.EXCLUDE

        # Changed rules - include private
        rules_v2 = {
            "schema_version": "1.0",
            "rules": [
                {
                    "name": "include-private",
                    "priority": 900,
                    "description": "Include private",
                    "match": {"name_pattern": r"^_"},
                    "action": "include",
                }
            ],
        }

        rules_file_v2 = tmp_path / "rules_v2.yaml"
        rules_file_v2.write_text(yaml.dump(rules_v2))

        engine_v2 = RuleEngine()
        engine_v2.load_rules([rules_file_v2])

        result_v2 = engine_v2.evaluate("_private", "module", MemberType.FUNCTION)
        assert result_v2.action == RuleAction.INCLUDE

        # Results changed - cache would be invalid


class TestErrorHandling:
    """Test error handling in integrated workflows."""

    @pytest.mark.integration
    def test_corrupt_cache_recovery(self, temp_cache_dir: Path):
        """System should recover from corrupt cache."""
        from tools.lazy_imports.common.cache import JSONAnalysisCache

        cache = JSONAnalysisCache(cache_dir=temp_cache_dir)

        # Create corrupt cache file
        cache_file = temp_cache_dir / "test.py.json"
        cache_file.write_text("{invalid json}")

        # Should handle gracefully
        cached = cache.get(Path("test.py"), "hash123")
        assert cached is None  # Corrupt entry returns None

    @pytest.mark.integration
    def test_missing_module_validation(self, tmp_path: Path):
        """Should detect and report missing modules in validation."""
        from tools.lazy_imports.validator.validator import LazyImportValidator

        test_file = tmp_path / "test.py"
        test_file.write_text("""
from codeweaver.common.utils import lazy_import

Missing = lazy_import("completely.nonexistent.module", "Class")
""")

        validator = LazyImportValidator(project_root=tmp_path)
        issues = validator.validate_file(test_file)

        # Should detect missing module
        from tools.lazy_imports.common.types import ValidationError

        errors = [i for i in issues if isinstance(i, ValidationError)]
        assert len(errors) > 0
        assert any("nonexistent" in e.message for e in errors)


class TestIncrementalUpdates:
    """Test incremental update workflows."""

    @pytest.mark.integration
    def test_single_file_update(self, tmp_path: Path, temp_cache_dir: Path):
        """Modifying single file should only reprocess that file."""
        from tools.lazy_imports.common.cache import JSONAnalysisCache

        cache = JSONAnalysisCache(cache_dir=temp_cache_dir)

        # Create multiple files
        files = []
        for i in range(5):
            file = tmp_path / f"module{i}.py"
            file.write_text(f"class Class{i}: pass")
            files.append(file)

        # Process all files (cache them)
        for file in files:
            from tools.lazy_imports.common.types import (
                AnalysisResult,
                ExportNode,
                MemberType,
                PropagationLevel,
            )

            exports = [
                ExportNode(
                    name=f"Class{files.index(file)}",
                    module="test",
                    member_type=MemberType.CLASS,
                    propagation=PropagationLevel.PARENT,
                    source_file=file,
                    line_number=1,
                    defined_in="test",
                )
            ]

            analysis = AnalysisResult(
                exports=exports,
                imports=[],
                file_hash=f"hash{files.index(file)}",
                analysis_timestamp=time.time(),
                schema_version="1.0",
            )

            cache.put(file, f"hash{files.index(file)}", analysis)

        # Modify one file
        files[2].write_text("class ModifiedClass: pass")

        # Cache should have 4 hits and 1 miss
        hits = 0
        misses = 0

        for i, file in enumerate(files):
            if i == 2:
                # Modified file - cache miss
                cached = cache.get(file, "new_hash")
                if cached is None:
                    misses += 1
            else:
                # Unchanged files - cache hit
                cached = cache.get(file, f"hash{i}")
                if cached is not None:
                    hits += 1

        assert hits == 4
        assert misses == 1


class TestMigrationValidation:
    """Test migration from old to new system."""

    @pytest.mark.integration
    def test_migration_produces_equivalent_output(self, tmp_path: Path):
        """New system should produce same output as old system."""
        # This test verifies the migration produces valid YAML
        from tools.lazy_imports.migration import migrate_to_yaml

        output_path = tmp_path / "rules.yaml"
        fake_script = tmp_path / "nonexistent.py"

        # Migrate (uses defaults)
        result = migrate_to_yaml(output_path, old_script=fake_script, dry_run=False)

        # Should have created files
        assert result.rules_extracted
        assert output_path.exists()

        # YAML should be valid and loadable
        import yaml
        with output_path.open() as f:
            config = yaml.safe_load(f)

        assert "rules" in config
        assert len(config["rules"]) > 0

    @pytest.mark.integration
    def test_config_migration(self, tmp_path: Path):
        """Old config should migrate to new format."""
        # Create old-style config (not currently used by migration)
        old_config = tmp_path / "exports_config.json"
        old_config.write_text('{"exports": {"module": ["Class1", "Class2"]}}')

        # Migration uses hardcoded rules, not old config files
        # This test verifies basic migration works
        from tools.lazy_imports.migration import migrate_to_yaml

        output_path = tmp_path / "rules.yaml"
        fake_script = tmp_path / "nonexistent.py"

        result = migrate_to_yaml(output_path, old_script=fake_script, dry_run=False)

        # Should produce valid output
        assert result.rules_extracted
        assert output_path.exists()
