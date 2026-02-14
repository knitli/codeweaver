"""Tests for Propagation Graph."""

# ruff: noqa: S101, ANN201
# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports, avoid-loops-in-tests
from __future__ import annotations

from pathlib import Path

from tools.lazy_imports.common.types import ExportNode, MemberType, PropagationLevel
from tools.lazy_imports.export_manager.graph import PropagationGraph


class TestPropagationGraph:
    """Test suite for propagation graph."""

    def test_simple_propagation_to_parent(self):
        """Exports with PARENT propagation should appear in parent __all__."""
        from tools.lazy_imports.export_manager.rules import RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        # Register modules first
        graph.add_module("codeweaver.core.types", "codeweaver.core")
        graph.add_module("codeweaver.core", "codeweaver")
        graph.add_module("codeweaver", None)

        # Add export from child module
        node = ExportNode(
            name="MyClass",
            module="codeweaver.core.types",
            member_type=MemberType.CLASS,
            propagation=PropagationLevel.PARENT,
            source_file=Path("codeweaver/core/types.py"),
            line_number=10,
            defined_in="codeweaver.core.types",
        )
        graph.add_export(node)

        # Build manifests
        manifests = graph.build_manifests()

        # Check parent includes child export
        assert "codeweaver.core" in manifests
        parent_manifest = manifests["codeweaver.core"]
        assert "MyClass" in parent_manifest.export_names

    def test_propagation_to_root(self):
        """Exports with ROOT propagation should reach top-level package."""
        from tools.lazy_imports.export_manager.rules import RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        # Register all modules in hierarchy
        graph.add_module("codeweaver.core.deep.nested.types", "codeweaver.core.deep.nested")
        graph.add_module("codeweaver.core.deep.nested", "codeweaver.core.deep")
        graph.add_module("codeweaver.core.deep", "codeweaver.core")
        graph.add_module("codeweaver.core", "codeweaver")
        graph.add_module("codeweaver", None)

        # Add export deep in hierarchy
        node = ExportNode(
            name="TopLevelType",
            module="codeweaver.core.deep.nested.types",
            member_type=MemberType.CLASS,
            propagation=PropagationLevel.ROOT,
            source_file=Path("codeweaver/core/deep/nested/types.py"),
            line_number=10,
            defined_in="codeweaver.core.deep.nested.types",
        )
        graph.add_export(node)

        manifests = graph.build_manifests()

        # Check all levels up to root
        assert "TopLevelType" in manifests["codeweaver.core.deep.nested.types"].export_names
        assert "TopLevelType" in manifests["codeweaver.core.deep.nested"].export_names
        assert "TopLevelType" in manifests["codeweaver.core.deep"].export_names
        assert "TopLevelType" in manifests["codeweaver.core"].export_names
        assert "TopLevelType" in manifests["codeweaver"].export_names

    def test_no_propagation(self):
        """Exports with NONE propagation should not propagate."""
        from tools.lazy_imports.export_manager.rules import RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        # Register modules
        graph.add_module("codeweaver.core.internal", "codeweaver.core")
        graph.add_module("codeweaver.core", "codeweaver")
        graph.add_module("codeweaver", None)

        node = ExportNode(
            name="InternalClass",
            module="codeweaver.core.internal",
            member_type=MemberType.CLASS,
            propagation=PropagationLevel.NONE,
            source_file=Path("codeweaver/core/internal.py"),
            line_number=10,
            defined_in="codeweaver.core.internal",
        )
        graph.add_export(node)

        manifests = graph.build_manifests()

        # Should exist in own module
        assert "InternalClass" in manifests["codeweaver.core.internal"].export_names

        # Should NOT propagate to parent
        parent_exports = manifests["codeweaver.core"].export_names
        assert "InternalClass" not in parent_exports

    def test_multiple_exports_same_module(self):
        """Multiple exports from same module should all be tracked."""
        from tools.lazy_imports.export_manager.rules import RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        # Register modules
        graph.add_module("test.module", "test")
        graph.add_module("test", None)

        exports = [
            ExportNode(
                name="Class1",
                module="test.module",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=Path("test/module.py"),
                line_number=10,
                defined_in="test.module",
            ),
            ExportNode(
                name="Class2",
                module="test.module",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=Path("test/module.py"),
                line_number=20,
                defined_in="test.module",
            ),
        ]

        for export in exports:
            graph.add_export(export)

        manifests = graph.build_manifests()

        # Both should be in module
        assert "Class1" in manifests["test.module"].export_names
        assert "Class2" in manifests["test.module"].export_names

        # Both should propagate to parent
        assert "Class1" in manifests["test"].export_names
        assert "Class2" in manifests["test"].export_names

    def test_deduplication_same_name_different_modules(self):
        """Same export name from different modules handled correctly."""
        from tools.lazy_imports.export_manager.rules import RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        # Register all modules
        graph.add_module("codeweaver.core.config", "codeweaver.core")
        graph.add_module("codeweaver.utils.config", "codeweaver.utils")
        graph.add_module("codeweaver.core", "codeweaver")
        graph.add_module("codeweaver.utils", "codeweaver")
        graph.add_module("codeweaver", None)

        # Two modules export "Config" to parent
        graph.add_export(
            ExportNode(
                name="Config",
                module="codeweaver.core.config",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=Path("codeweaver/core/config.py"),
                line_number=10,
                defined_in="codeweaver.core.config",
            )
        )

        graph.add_export(
            ExportNode(
                name="Config",
                module="codeweaver.utils.config",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=Path("codeweaver/utils/config.py"),
                line_number=10,
                defined_in="codeweaver.utils.config",
            )
        )

        manifests = graph.build_manifests()

        # Both submodules should have their own Config
        assert "Config" in manifests["codeweaver.core.config"].export_names
        assert "Config" in manifests["codeweaver.utils.config"].export_names

        # Top level should have Config from one or both (implementation dependent)
        # The important thing is no crash/error
        assert "codeweaver" in manifests

    def test_topological_ordering(self):
        """Modules should be processed in correct dependency order."""
        from tools.lazy_imports.export_manager.rules import RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        # Register modules
        graph.add_module("pkg.sub.deep", "pkg.sub")
        graph.add_module("pkg.sub", "pkg")
        graph.add_module("pkg", None)

        # Add exports in non-topological order
        graph.add_export(
            ExportNode(
                name="A",
                module="pkg.sub.deep",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.ROOT,
                source_file=Path("pkg/sub/deep.py"),
                line_number=1,
                defined_in="pkg.sub.deep",
            )
        )

        graph.add_export(
            ExportNode(
                name="B",
                module="pkg.sub",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=Path("pkg/sub.py"),
                line_number=1,
                defined_in="pkg.sub",
            )
        )

        # Should not crash - builds in correct order
        manifests = graph.build_manifests()

        assert len(manifests) > 0

    def test_empty_graph(self):
        """Empty graph should build without errors."""
        from tools.lazy_imports.export_manager.rules import RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        manifests = graph.build_manifests()

        assert manifests == {}

    def test_single_module_no_parents(self):
        """Single top-level module with no parents."""
        from tools.lazy_imports.export_manager.rules import RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        # Register module
        graph.add_module("toplevel", None)

        node = ExportNode(
            name="TopLevel",
            module="toplevel",
            member_type=MemberType.CLASS,
            propagation=PropagationLevel.PARENT,
            source_file=Path("toplevel.py"),
            line_number=1,
            defined_in="toplevel",
        )
        graph.add_export(node)

        manifests = graph.build_manifests()

        # Should have manifest for toplevel
        assert "toplevel" in manifests
        assert "TopLevel" in manifests["toplevel"].export_names

    def test_propagation_stops_at_root(self):
        """ROOT propagation should not go beyond package root."""
        from tools.lazy_imports.export_manager.rules import RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        # Register modules
        graph.add_module("pkg.core.types", "pkg.core")
        graph.add_module("pkg.core", "pkg")
        graph.add_module("pkg", None)

        node = ExportNode(
            name="Type",
            module="pkg.core.types",
            member_type=MemberType.CLASS,
            propagation=PropagationLevel.ROOT,
            source_file=Path("pkg/core/types.py"),
            line_number=1,
            defined_in="pkg.core.types",
        )
        graph.add_export(node)

        manifests = graph.build_manifests()

        # Should propagate to pkg (root of package)
        assert "Type" in manifests["pkg"].export_names

        # Should not create manifests beyond package root
        assert "" not in manifests  # Empty string = root

    def test_mixed_propagation_levels(self):
        """Mix of NONE, PARENT, ROOT propagation levels."""
        from tools.lazy_imports.export_manager.rules import RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        # Register modules
        graph.add_module("pkg.mod", "pkg")
        graph.add_module("pkg", None)

        exports = [
            ExportNode(
                name="NoProp",
                module="pkg.mod",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.NONE,
                source_file=Path("pkg/mod.py"),
                line_number=1,
                defined_in="pkg.mod",
            ),
            ExportNode(
                name="ParentProp",
                module="pkg.mod",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=Path("pkg/mod.py"),
                line_number=2,
                defined_in="pkg.mod",
            ),
            ExportNode(
                name="RootProp",
                module="pkg.mod",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.ROOT,
                source_file=Path("pkg/mod.py"),
                line_number=3,
                defined_in="pkg.mod",
            ),
        ]

        for export in exports:
            graph.add_export(export)

        manifests = graph.build_manifests()

        # Module should have all three
        mod_exports = manifests["pkg.mod"].export_names
        assert "NoProp" in mod_exports
        assert "ParentProp" in mod_exports
        assert "RootProp" in mod_exports

        # Parent should have ParentProp and RootProp
        parent_exports = manifests["pkg"].export_names
        assert "NoProp" not in parent_exports
        assert "ParentProp" in parent_exports
        assert "RootProp" in parent_exports

    def test_manifest_has_own_and_propagated_separated(self):
        """Manifest should separate own exports from propagated."""
        from tools.lazy_imports.export_manager.rules import RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        # Register modules
        graph.add_module("pkg.core.types", "pkg.core")
        graph.add_module("pkg.core", "pkg")
        graph.add_module("pkg", None)

        # Own export
        graph.add_export(
            ExportNode(
                name="OwnClass",
                module="pkg.core",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=Path("pkg/core/__init__.py"),
                line_number=1,
                defined_in="pkg.core",
            )
        )

        # Export from child that propagates
        graph.add_export(
            ExportNode(
                name="ChildClass",
                module="pkg.core.types",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=Path("pkg/core/types.py"),
                line_number=1,
                defined_in="pkg.core.types",
            )
        )

        manifests = graph.build_manifests()

        parent = manifests["pkg.core"]

        # Should have both in all_exports
        assert "OwnClass" in parent.export_names
        assert "ChildClass" in parent.export_names

        # Should separate own vs propagated
        own_names = [e.name for e in parent.own_exports]
        propagated_names = [e.name for e in parent.propagated_exports]

        assert "OwnClass" in own_names
        assert "OwnClass" not in propagated_names

        assert "ChildClass" in propagated_names
        assert "ChildClass" not in own_names

    def test_exports_sorted_alphabetically(self):
        """Export names should be sorted alphabetically."""
        from tools.lazy_imports.export_manager.rules import RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        # Register module
        graph.add_module("test", None)

        names = ["Zebra", "Apple", "Mango", "Banana"]
        for name in names:
            graph.add_export(
                ExportNode(
                    name=name,
                    module="test",
                    member_type=MemberType.CLASS,
                    propagation=PropagationLevel.NONE,
                    source_file=Path("test.py"),
                    line_number=1,
                    defined_in="test",
                )
            )

        manifests = graph.build_manifests()

        export_names = manifests["test"].export_names
        assert export_names == ["Apple", "Banana", "Mango", "Zebra"]
