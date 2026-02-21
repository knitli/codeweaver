#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Propagation graph for managing export hierarchy.

This module implements the bottom-up propagation graph that determines which
exports should propagate to parent modules based on their propagation level
and the module hierarchy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Literal

import textcase

from tools.lazy_imports.common.types import (
    ExportDecision,
    ExportManifest,
    LazyExport,
    PropagationLevel,
    RuleAction,
)


if TYPE_CHECKING:
    from tools.lazy_imports.export_manager.rules import RuleEngine


class CircularDependencyIndicator(IntEnum):
    """Indicator for circular dependencies in export propagation."""

    UNVISITED = 0
    VISITING = 1  # (in current path)
    VISITED = 2  # (fully processed)


@dataclass
class ExportEntry:
    """Internal graph representation of an export."""

    decision: ExportDecision
    propagates_to: set[str] = field(default_factory=set)


@dataclass
class ModuleNode:
    """A node in the module hierarchy graph."""

    module_path: str
    parent: str | None
    children: set[str] = field(default_factory=set)

    # Exports defined in this module
    own_exports: dict[str, ExportEntry] = field(default_factory=dict)

    # Exports propagated from child modules
    propagated_exports: dict[str, ExportEntry] = field(default_factory=dict)


def export_sort_key(name: str) -> tuple[Literal[0, 1, 2], str]:
    """Sort key: SCREAMING_SNAKE (0), PascalCase (1), snake_case (2)."""
    if textcase.constant.match(name):
        group = 0  # SCREAMING_SNAKE_CASE
    elif textcase.pascal.match(name):
        group = 1  # PascalCase
    else:
        group = 2  # snake_case
    return (group, name.lower())


class PropagationGraph:
    """Manages export propagation through module hierarchy."""

    def __init__(self, rule_engine: RuleEngine):
        """Initialize propagation graph."""
        self.rule_engine = rule_engine
        self.modules: dict[str, ModuleNode] = {}
        self.roots: set[str] = set()

    def add_module(self, module_path: str, parent: str | None) -> None:
        """Add module to hierarchy."""
        if module_path in self.modules:
            return

        node = ModuleNode(module_path=module_path, parent=parent)
        self.modules[module_path] = node

        if parent:
            if parent not in self.modules:
                grandparent = self._get_parent_module(parent)
                self.add_module(parent, grandparent)
            self.modules[parent].children.add(module_path)
        else:
            self.roots.add(module_path)

    def add_export(self, decision: ExportDecision) -> None:
        """Add export decision to graph."""
        if decision.action in (RuleAction.EXCLUDE, RuleAction.NO_DECISION):
            return

        module = decision.module_path
        if module not in self.modules:
            raise ValueError(
                f"Cannot add export to unknown module: {module}\n"
                f"Call add_module() first to register the module."
            )

        entry = ExportEntry(decision=decision)
        self.modules[module].own_exports[decision.export_name] = entry

        # Calculate propagation paths
        self._compute_propagation(entry)

    def build_manifests(self) -> dict[str, ExportManifest]:
        """Build export manifests for all modules (bottom-up)."""
        if cycles := self.detect_cycles():
            cycle_paths = "\n".join(f"  {' → '.join(cycle)} → {cycle[0]}" for cycle in cycles)
            raise ValueError(f"❌ Error: Circular propagation detected\n\n{cycle_paths}")

        # Validate no duplicate exports in same module
        self._validate_no_duplicates()

        # Get processing order (bottom-up)
        ordered = self._topological_sort()

        # Build propagated exports
        for module_path in ordered:
            self._propagate_to_module(module_path)

        # Validate all propagated exports have valid sources
        self._validate_propagation_sources()

        # Generate manifests
        manifests = {}
        for module_path, node in self.modules.items():
            own_lazy = [self._to_lazy_export(entry) for entry in node.own_exports.values()]
            prop_lazy = [self._to_lazy_export(entry) for entry in node.propagated_exports.values()]
            all_lazy = own_lazy + prop_lazy

            # Sort using export_sort_key for consistency
            own_lazy.sort(key=lambda x: export_sort_key(x.public_name))
            prop_lazy.sort(key=lambda x: export_sort_key(x.public_name))
            all_lazy.sort(key=lambda x: export_sort_key(x.public_name))

            manifests[module_path] = ExportManifest(
                module_path=module_path,
                own_exports=own_lazy,
                propagated_exports=prop_lazy,
                all_exports=all_lazy,
            )

        return manifests

    def detect_cycles(self) -> list[list[str]]:
        """Detect circular dependencies in module hierarchy."""
        color: dict[str, CircularDependencyIndicator] = dict.fromkeys(
            self.modules, CircularDependencyIndicator.UNVISITED
        )
        cycles: list[list[str]] = []
        current_path: list[str] = []

        def visit(module: str) -> None:
            if color[module] == CircularDependencyIndicator.VISITED:
                return
            if color[module] == CircularDependencyIndicator.VISITING:
                cycle_start = current_path.index(module)
                cycles.append(current_path[cycle_start:])
                return

            color[module] = CircularDependencyIndicator.VISITING
            current_path.append(module)

            for child in self.modules[module].children:
                visit(child)

            current_path.pop()
            color[module] = CircularDependencyIndicator.VISITED

        for module in self.modules:
            if color[module] == CircularDependencyIndicator.UNVISITED:
                visit(module)
        return cycles

    def _compute_propagation(self, entry: ExportEntry) -> None:
        """Compute which modules this export should propagate to."""
        decision = entry.decision
        if decision.propagation == PropagationLevel.NONE:
            return

        current = decision.module_path

        if decision.propagation == PropagationLevel.PARENT:
            if current in self.modules:
                node = self.modules[current]
                if node.parent:
                    entry.propagates_to.add(node.parent)

        elif decision.propagation == PropagationLevel.ROOT:
            while current in self.modules:
                node = self.modules[current]
                if not node.parent:
                    break
                entry.propagates_to.add(node.parent)
                current = node.parent

    def _propagate_to_module(self, module_path: str) -> None:
        """Propagate exports to a module from its children."""
        node = self.modules[module_path]

        for child_path in node.children:
            child = self.modules[child_path]

            # Helper to check if entry propagates to this module
            def check_and_add(entries: dict[str, ExportEntry]) -> None:
                """Check entries and add to propagated_exports if they propagate to this module."""
                for entry in entries.values():
                    if module_path in entry.propagates_to:
                        self._add_propagated_export(node, entry)

            check_and_add(child.own_exports)
            check_and_add(child.propagated_exports)

    def _add_propagated_export(self, node: ModuleNode, entry: ExportEntry) -> None:
        """Add a propagated export with conflict detection and resolution."""
        name = entry.decision.export_name

        if name in node.propagated_exports:
            existing = node.propagated_exports[name]

            # Conflict resolution: higher priority wins
            new_prio = entry.decision.priority
            old_prio = existing.decision.priority

            if new_prio > old_prio:
                # New entry wins (higher priority)
                node.propagated_exports[name] = entry
            elif new_prio == old_prio:
                # Same priority - this is a conflict
                new_module = entry.decision.module_path
                old_module = existing.decision.module_path

                # If from different modules, raise conflict error
                if new_module != old_module:
                    raise ValueError(
                        f"❌ Error: Export conflict detected\n\n"
                        f"  Export name: {name!r}\n"
                        f"  Target module: {node.module_path}\n"
                        f"  Conflicting sources:\n"
                        f"    • {old_module} (priority {old_prio})\n"
                        f"    • {new_module} (priority {new_prio})\n\n"
                        f"  Resolution: Assign different priorities to resolve the conflict."
                    )

                # Same module - use alphabetical tie-breaker for stability
                if new_module < old_module:
                    node.propagated_exports[name] = entry
        else:
            node.propagated_exports[name] = entry

    def _validate_no_duplicates(self) -> None:
        """Validate no duplicate exports in same module."""
        for module_path, node in self.modules.items():
            # Check for duplicates in own_exports
            export_names = list(node.own_exports.keys())
            if len(export_names) != len(set(export_names)):
                duplicates = [name for name in export_names if export_names.count(name) > 1]
                raise ValueError(
                    f"❌ Error: Duplicate exports in module {module_path}\n\n"
                    f"  Duplicates: {', '.join(set(duplicates))}"
                )

    def _validate_propagation_sources(self) -> None:
        """Validate all propagated exports have valid source modules."""
        for module_path, node in self.modules.items():
            for name, entry in node.propagated_exports.items():
                source_module = entry.decision.module_path
                if source_module not in self.modules:
                    raise ValueError(
                        f"❌ Error: Invalid propagation source\n\n"
                        f"  Export: {name!r}\n"
                        f"  Target module: {module_path}\n"
                        f"  Source module: {source_module} (not found in module graph)"
                    )

    def _topological_sort(self) -> list[str]:
        """Return modules in topological order (leaves first)."""
        visited = set()
        result = []

        def visit(module_path: str) -> None:
            if module_path in visited:
                return
            visited.add(module_path)

            for child in self.modules[module_path].children:
                visit(child)

            result.append(module_path)

        for root in self.roots:
            visit(root)

        return result

    def _get_parent_module(self, module_path: str) -> str | None:
        parts = module_path.split(".")
        return ".".join(parts[:-1]) if len(parts) > 1 else None

    def _to_lazy_export(self, entry: ExportEntry) -> LazyExport:
        """Convert an graph entry to a final LazyExport."""
        decision = entry.decision
        return LazyExport(
            public_name=decision.export_name,
            target_module=decision.module_path,
            target_object=decision.source_symbol.name,
            is_type_only=decision.source_symbol.member_type == "type_alias",  # Simple check for now
        )

    def debug_export(self, name: str) -> str:
        """Generate debug information for an export."""
        lines = [f"Debug information for export: {name!r}\n"]

        definitions = []
        propagations = []

        for module_path, node in self.modules.items():
            if name in node.own_exports:
                entry = node.own_exports[name]
                d = entry.decision
                definitions.append(
                    f"  Defined in: {module_path}\n"
                    f"    Type: {d.source_symbol.member_type}\n"
                    f"    Propagation: {d.propagation}\n"
                    f"    Source: {d.source_symbol.location}\n"
                    f"    Propagates to: {sorted(entry.propagates_to)}"
                )

            if name in node.propagated_exports:
                entry = node.propagated_exports[name]
                propagations.append(
                    f"  Propagated to: {module_path}\n"
                    f"    From: {entry.decision.module_path}\n"
                    f"    Priority: {entry.decision.priority}"
                )

        if definitions:
            lines.append("Definitions:")
            lines.extend(definitions)

        if propagations:
            lines.append("\nPropagations:")
            lines.extend(propagations)

        return "\n".join(lines)
