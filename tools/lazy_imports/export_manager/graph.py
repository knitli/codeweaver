#!/usr/bin/env python3
"""Propagation graph for managing export hierarchy.

This module implements the bottom-up propagation graph that determines which
exports should propagate to parent modules based on their propagation level
and the module hierarchy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from tools.lazy_imports.common.types import ExportManifest, ExportNode, PropagationLevel


if TYPE_CHECKING:
    from .rules import RuleEngine


@dataclass
class ModuleNode:
    """A node in the module hierarchy graph.

    Each node represents a Python module and tracks its position in the
    package hierarchy, exports defined at this level, and exports propagated
    from child modules.
    """

    module_path: str  # e.g., "codeweaver.core.types"
    parent: str | None  # Parent module path
    children: set[str] = field(default_factory=set)

    # Exports defined in this module
    own_exports: dict[str, ExportNode] = field(default_factory=dict)

    # Exports propagated from child modules
    propagated_exports: dict[str, ExportNode] = field(default_factory=dict)


class PropagationGraph:
    """Manages export propagation through module hierarchy.

    The propagation graph builds a bottom-up model of how exports flow through
    the package hierarchy. It uses topological sorting to process modules in
    the correct order (leaves first) and implements cycle detection to prevent
    infinite propagation loops.

    Key responsibilities:
    - Build module hierarchy from package structure
    - Add exports and compute propagation paths
    - Detect and fail on circular dependencies
    - Generate export manifests for each module

    Implementation notes:
    - Modules are processed bottom-up (leaves → root)
    - Topological sort ensures correct processing order
    - Cycle detection uses DFS with state tracking
    - Deduplication uses priority-based conflict resolution
    """

    def __init__(self, rule_engine: RuleEngine):
        """Initialize propagation graph.

        Args:
            rule_engine: Rule engine for conflict resolution
        """
        self.rule_engine = rule_engine
        self.modules: dict[str, ModuleNode] = {}
        self.roots: set[str] = set()  # Top-level modules

    def add_module(self, module_path: str, parent: str | None) -> None:
        """Add module to hierarchy.

        Creates a new module node and establishes parent-child relationships.
        If parent doesn't exist, it's created recursively.

        Args:
            module_path: Fully qualified module name (e.g., "codeweaver.core.types")
            parent: Parent module path or None for root modules
        """
        if module_path in self.modules:
            return  # Already exists

        # Create node
        node = ModuleNode(module_path=module_path, parent=parent)
        self.modules[module_path] = node

        # Establish parent-child relationship
        if parent:
            if parent not in self.modules:
                # Recursively create parent
                grandparent = self._get_parent_module(parent)
                self.add_module(parent, grandparent)

            self.modules[parent].children.add(module_path)
        else:
            self.roots.add(module_path)

    def add_export(self, export: ExportNode) -> None:
        """Add export to graph.

        Adds an export to its source module and computes which parent modules
        it should propagate to based on its propagation level.

        Args:
            export: Export node to add

        Raises:
            ValueError: If export's module doesn't exist in graph
        """
        if export.module not in self.modules:
            raise ValueError(
                f"Cannot add export to unknown module: {export.module}\n"
                f"Call add_module() first to register the module."
            )

        # Add to module's own exports
        node = self.modules[export.module]
        node.own_exports[export.name] = export

        # Compute propagation targets
        self._compute_propagation(export)

    def build_manifests(self) -> dict[str, ExportManifest]:
        """Build export manifests for all modules (bottom-up).

        Processes modules in topological order (leaves first) to build
        complete export manifests that include both own exports and
        exports propagated from children.

        Returns:
            Dictionary mapping module path to its ExportManifest

        Raises:
            ValueError: If circular dependencies are detected
        """
        # Detect cycles first
        cycles = self.detect_cycles()
        if cycles:
            cycle_paths = "\n".join(f"  {' → '.join(cycle)} → {cycle[0]}" for cycle in cycles)
            raise ValueError(
                f"❌ Error: Circular propagation detected\n\n"
                f"Cycle path(s):\n{cycle_paths}\n\n"
                f"This indicates conflicting propagation rules.\n\n"
                f"Suggestions:\n"
                f"- Review rules affecting these modules\n"
                f"- Ensure propagation is strictly hierarchical\n"
                f"- Use `mise run lazy-imports export debug <symbol>` "
                f"to trace propagation"
            )

        # Get processing order (bottom-up)
        ordered = self._topological_sort()

        # Build propagated exports for each module
        for module_path in ordered:
            self._propagate_to_module(module_path)

        # Generate manifests
        manifests = {}
        for module_path, node in self.modules.items():
            all_exports = list(node.own_exports.values()) + list(node.propagated_exports.values())

            manifests[module_path] = ExportManifest(
                module_path=module_path,
                own_exports=list(node.own_exports.values()),
                propagated_exports=list(node.propagated_exports.values()),
                all_exports=all_exports,
            )

        return manifests

    def detect_cycles(self) -> list[list[str]]:
        """Detect circular dependencies in module hierarchy.

        Uses depth-first search with state tracking to detect cycles in the
        parent-child relationships. This ensures we fail fast if rules create
        circular propagation paths.

        Returns:
            List of cycles, where each cycle is a list of module paths.
            Empty list if no cycles detected.

        Implementation:
        - WHITE: Not visited
        - GRAY: Currently being processed (on stack)
        - BLACK: Finished processing

        A cycle exists if we encounter a GRAY node during traversal.
        """
        WHITE = 0  # noqa: N806
        GRAY = 1  # noqa: N806
        BLACK = 2  # noqa: N806

        color: dict[str, int] = dict.fromkeys(self.modules, WHITE)
        cycles: list[list[str]] = []
        current_path: list[str] = []

        def visit(module: str) -> None:
            """DFS visit function."""
            if color[module] == BLACK:
                return  # Already processed

            if color[module] == GRAY:
                # Cycle detected!
                cycle_start = current_path.index(module)
                cycle = current_path[cycle_start:]
                cycles.append(cycle)
                return

            # Mark as being processed
            color[module] = GRAY
            current_path.append(module)

            # Visit children
            node = self.modules[module]
            for child in node.children:
                visit(child)

            # Mark as finished
            current_path.pop()
            color[module] = BLACK

        # Visit all modules
        for module in self.modules:
            if color[module] == WHITE:
                visit(module)

        return cycles

    def _compute_propagation(self, export: ExportNode) -> None:
        """Compute which modules this export should propagate to.

        Based on the export's propagation level, determines the parent
        modules that should receive this export.

        Args:
            export: Export node with propagation level set
        """
        if export.propagation == PropagationLevel.NONE:
            return

        current = export.module

        if export.propagation == PropagationLevel.PARENT:
            # Propagate one level up
            if current in self.modules:
                node = self.modules[current]
                if node.parent:
                    export.propagates_to.add(node.parent)

        elif export.propagation == PropagationLevel.ROOT:
            # Propagate all the way up to root
            while current in self.modules:
                node = self.modules[current]
                if not node.parent:
                    break
                export.propagates_to.add(node.parent)
                current = node.parent

        # CUSTOM propagation would be handled here in future

    def _propagate_to_module(self, module_path: str) -> None:
        """Propagate exports to a module from its children.

        Collects all exports from child modules that should propagate to
        this module and adds them to propagated_exports with deduplication.

        Args:
            module_path: Target module to propagate exports to
        """
        node = self.modules[module_path]

        # Collect exports from children that propagate here
        for child_path in node.children:
            child = self.modules[child_path]

            # Add child's own exports that propagate here
            for export in child.own_exports.values():
                if module_path in export.propagates_to:
                    self._add_propagated_export(node, export)

            # Add child's propagated exports that continue propagating
            for export in child.propagated_exports.values():
                if module_path in export.propagates_to:
                    self._add_propagated_export(node, export)

    def _add_propagated_export(self, node: ModuleNode, export: ExportNode) -> None:
        """Add a propagated export with conflict resolution.

        When the same export name appears from multiple sources, uses
        rule priority to determine which one wins.

        Args:
            node: Target module node
            export: Export to add

        Implementation:
        - If name doesn't exist: add it
        - If name exists: re-evaluate both exports and keep higher priority
        - Same priority: keep first occurrence (defined_in alphabetically)
        """
        if export.name in node.propagated_exports:
            # Conflict! Use rule priority to resolve
            existing = node.propagated_exports[export.name]

            # Re-evaluate both exports to get their priorities
            new_result = self.rule_engine.evaluate(
                export.name, export.defined_in, export.member_type
            )

            existing_result = self.rule_engine.evaluate(
                existing.name, existing.defined_in, existing.member_type
            )

            # Compare priorities
            new_priority = new_result.matched_rule.priority if new_result.matched_rule else 0
            existing_priority = (
                existing_result.matched_rule.priority if existing_result.matched_rule else 0
            )

            if (
                new_priority <= existing_priority
                and new_priority == existing_priority
                and export.defined_in < existing.defined_in
            ) or new_priority > existing_priority:
                node.propagated_exports[export.name] = export
                # Otherwise keep existing (higher priority or alphabetically first)

        else:
            # No conflict, add it
            node.propagated_exports[export.name] = export

    def _topological_sort(self) -> list[str]:
        """Return modules in topological order (leaves first).

        Uses depth-first search to produce a processing order where all
        children are processed before their parents.

        Returns:
            List of module paths in bottom-up order
        """
        visited = set()
        result = []

        def visit(module_path: str) -> None:
            """DFS visit function."""
            if module_path in visited:
                return
            visited.add(module_path)

            node = self.modules[module_path]

            # Visit children first (depth-first)
            for child in node.children:
                visit(child)

            # Add this module after all children
            result.append(module_path)

        # Start from roots and traverse
        for root in self.roots:
            visit(root)

        return result

    def _get_parent_module(self, module_path: str) -> str | None:
        """Get parent module path from a module path.

        Args:
            module_path: Full module path (e.g., "codeweaver.core.types")

        Returns:
            Parent module path (e.g., "codeweaver.core") or None if root
        """
        parts = module_path.split(".")
        if len(parts) <= 1:
            return None
        return ".".join(parts[:-1])

    def get_module_exports(self, module_path: str) -> dict[str, ExportNode]:
        """Get all exports for a module (own + propagated).

        Args:
            module_path: Module to get exports for

        Returns:
            Dictionary mapping export name to ExportNode

        Raises:
            KeyError: If module doesn't exist in graph
        """
        if module_path not in self.modules:
            raise KeyError(f"Module not found in graph: {module_path}")

        node = self.modules[module_path]
        return {**node.own_exports, **node.propagated_exports}

    def get_propagation_path(self, export: ExportNode) -> list[str]:
        """Get the propagation path for an export.

        Returns the list of modules this export propagates to, in order
        from child to parent.

        Args:
            export: Export to trace

        Returns:
            List of module paths this export propagates to
        """
        return sorted(export.propagates_to)

    def debug_export(self, name: str) -> str:
        """Generate debug information for an export.

        Finds all occurrences of an export across the graph and shows
        where it's defined, where it propagates to, and any conflicts.

        Args:
            name: Export name to debug

        Returns:
            Human-readable debug information
        """
        lines = [f"Debug information for export: {name!r}\n"]

        # Find all modules that have this export
        definitions = []
        propagations = []

        for module_path, node in self.modules.items():
            if name in node.own_exports:
                export = node.own_exports[name]
                definitions.append(
                    f"  Defined in: {module_path}\n"
                    f"    Type: {export.member_type.value}\n"
                    f"    Propagation: {export.propagation.value}\n"
                    f"    Source: {export.source_file}:{export.line_number}\n"
                    f"    Propagates to: {sorted(export.propagates_to)}"
                )

            if name in node.propagated_exports:
                export = node.propagated_exports[name]
                propagations.append(
                    f"  Propagated to: {module_path}\n"
                    f"    From: {export.defined_in}\n"
                    f"    Type: {export.member_type.value}"
                )

        if definitions:
            lines.append("Definitions:")
            lines.extend(definitions)

        if propagations:
            lines.append("\nPropagations:")
            lines.extend(propagations)

        if not definitions and not propagations:
            lines.append(f"  No export named {name!r} found in graph")

        return "\n".join(lines)
