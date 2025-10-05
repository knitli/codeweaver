# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Enhanced type definitions for grammar-based semantic analysis.

This module provides NamedTuple-based types with computed properties and helper
methods for working with tree-sitter grammar structures. These types complement
the existing TypedDict definitions and provide a more user-friendly API.

Design Philosophy:
- NamedTuples for immutable data with helper methods
- Cached properties for expensive operations
- Clean, self-documenting API
"""

from __future__ import annotations

from functools import cached_property
from typing import NamedTuple


class FieldInfo(NamedTuple):
    """Information about a field in a node type.

    Fields are named structural relationships in tree-sitter grammars that group
    related child nodes or represent unique named components of a parent node.

    Attributes:
        name: Field name (e.g., "name", "body", "parameters")
        required: Whether this field must be present
        multiple: Whether field can have multiple values
        types: Tuple of allowed node type names for this field
    """

    name: str
    required: bool
    multiple: bool
    types: tuple[str, ...]

    @property
    def is_required(self) -> bool:
        """Check if field is required."""
        return self.required

    @property
    def is_collection(self) -> bool:
        """Check if field can have multiple values."""
        return self.multiple

    @cached_property
    def type_names(self) -> frozenset[str]:
        """Get set of type names for fast lookup."""
        return frozenset(self.types)

    def accepts_type(self, type_name: str) -> bool:
        """Check if this field accepts a given type.

        Args:
            type_name: Node type name to check

        Returns:
            True if this field can contain nodes of the given type
        """
        return type_name in self.type_names


class NodeSemanticInfo(NamedTuple):
    """Semantic information extracted from grammar for a node type.

    This is the primary data structure for grammar-based classification,
    containing all structural and semantic information available from
    the tree-sitter grammar.

    Attributes:
        node_type: The node type name (e.g., "function_definition")
        language: Programming language name
        is_named: Whether node has a defined rule name in grammar
        is_abstract: Whether node has subtypes (abstract category)
        is_extra: Whether node can appear anywhere (no constraints)
        is_root: Whether node is a root node (entry point)
        abstract_category: Supertype if this is a concrete type
        concrete_subtypes: If this is abstract, tuple of concrete implementations
        fields: Named fields with structural relationships
        children_types: Allowed child types (positional constraints)
    """

    node_type: str
    language: str
    is_named: bool
    is_abstract: bool
    is_extra: bool
    is_root: bool
    abstract_category: str | None
    concrete_subtypes: tuple[str, ...]
    fields: tuple[FieldInfo, ...]
    children_types: tuple[str, ...]

    @property
    def has_fields(self) -> bool:
        """Check if node has named fields."""
        return len(self.fields) > 0

    @property
    def has_children_constraints(self) -> bool:
        """Check if node has children constraints."""
        return len(self.children_types) > 0

    @cached_property
    def required_field_names(self) -> frozenset[str]:
        """Get set of required field names."""
        return frozenset(f.name for f in self.fields if f.is_required)

    @cached_property
    def optional_field_names(self) -> frozenset[str]:
        """Get set of optional field names."""
        return frozenset(f.name for f in self.fields if not f.is_required)

    @cached_property
    def field_map(self) -> dict[str, FieldInfo]:
        """Get mapping from field name to field info."""
        return {f.name: f for f in self.fields}

    def get_field(self, name: str) -> FieldInfo | None:
        """Get field info by name.

        Args:
            name: Field name to look up

        Returns:
            FieldInfo if found, None otherwise
        """
        return self.field_map.get(name)

    def has_field(self, name: str) -> bool:
        """Check if node has a specific field.

        Args:
            name: Field name to check

        Returns:
            True if field exists
        """
        return name in self.field_map

    def infer_semantic_category(self) -> str:
        """Infer semantic category from grammar structure.

        Uses field names to infer the most likely semantic category based on
        empirical patterns from grammar analysis.

        Returns:
            Semantic category string: "callable", "type_def", "control_flow",
            "operation", or "unknown"
        """
        field_names = {f.name for f in self.fields}

        # Check for callable signatures
        if self._is_callable(field_names):
            return "callable"

        # Check for type definitions
        if self._is_type_def(field_names):
            return "type_def"

        # Check for control flow
        if "condition" in field_names or "consequence" in field_names:
            return "control_flow"

        # Check for operations
        if "operator" in field_names:
            return "operation"

        # Check for pattern matching
        if "pattern" in field_names or "patterns" in field_names:
            return "pattern_match"

        # Use abstract category as fallback
        if self.is_abstract and self.abstract_category:
            return self.abstract_category

        return "unknown"

    def _is_callable(self, field_names: set[str]) -> bool:
        """Check if node appears to be a callable."""
        if "parameters" in field_names:
            return True

        # Has name and body but not type-related fields
        if "name" in field_names and "body" in field_names:
            return not ("type_parameters" in field_names or "type" in field_names)

        return False

    def _is_type_def(self, field_names: set[str]) -> bool:
        """Check if node appears to be a type definition."""
        if "type_parameters" in field_names:
            return True

        # Definition/declaration with type field
        return (
            self.node_type.endswith(("_definition", "_declaration"))
            and "type" in field_names
        )


class AbstractTypeInfo(NamedTuple):
    """Information about an abstract type and its subtypes.

    Abstract types are defined via the 'subtypes' field in tree-sitter grammars
    and represent polymorphic categories that don't appear directly in syntax trees.

    Attributes:
        abstract_type: The abstract type name (e.g., "expression", "statement")
        language: Programming language name
        concrete_subtypes: Tuple of concrete node types that implement this abstract type
    """

    abstract_type: str
    language: str
    concrete_subtypes: tuple[str, ...]

    @cached_property
    def subtype_set(self) -> frozenset[str]:
        """Get set of subtypes for fast lookup."""
        return frozenset(self.concrete_subtypes)

    def is_subtype(self, type_name: str) -> bool:
        """Check if a type is a subtype of this abstract type.

        Args:
            type_name: Node type name to check

        Returns:
            True if type_name is a concrete subtype of this abstract type
        """
        return type_name in self.subtype_set

    @property
    def subtype_count(self) -> int:
        """Get number of concrete subtypes."""
        return len(self.concrete_subtypes)


# Type aliases for convenience
FieldInfoTuple = tuple[FieldInfo, ...]
AbstractTypeMap = dict[str, dict[str, AbstractTypeInfo]]
