# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for grammar types (NamedTuple API)."""

import sys

from pathlib import Path


# Add src to path to avoid circular imports during testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from codeweaver.semantic.grammar_types import AbstractTypeInfo, FieldInfo, NodeSemanticInfo


class TestFieldInfo:
    """Tests for FieldInfo NamedTuple."""

    def test_basic_properties(self):
        """Test basic FieldInfo properties."""
        field = FieldInfo(name="body", required=True, multiple=False, types=("block", "statement"))

        assert field.name == "body"
        assert field.is_required is True
        assert field.is_collection is False
        assert field.types == ("block", "statement")

    def test_type_names_cached_property(self):
        """Test type_names cached property."""
        field = FieldInfo(
            name="parameters", required=True, multiple=True, types=("parameter", "parameter_list")
        )

        type_names = field.type_names
        assert isinstance(type_names, frozenset)
        assert "parameter" in type_names
        assert "parameter_list" in type_names

        # Should return same object (cached)
        assert field.type_names is type_names

    def test_accepts_type(self):
        """Test accepts_type method."""
        field = FieldInfo(
            name="value", required=False, multiple=False, types=("expression", "literal")
        )

        assert field.accepts_type("expression") is True
        assert field.accepts_type("literal") is True
        assert field.accepts_type("statement") is False


class TestNodeSemanticInfo:
    """Tests for NodeSemanticInfo NamedTuple."""

    def test_basic_properties(self):
        """Test basic NodeSemanticInfo properties."""
        info = NodeSemanticInfo(
            node_type="function_definition",
            language="python",
            is_named=True,
            is_abstract=False,
            is_extra=False,
            is_root=False,
            abstract_category="statement",
            concrete_subtypes=(),
            fields=(
                FieldInfo("name", True, False, ("identifier",)),
                FieldInfo("body", True, False, ("block",)),
                FieldInfo("parameters", True, False, ("parameters",)),
            ),
            children_types=(),
        )

        assert info.node_type == "function_definition"
        assert info.language == "python"
        assert info.is_named is True
        assert info.has_fields is True
        assert info.has_children_constraints is False
        assert len(info.fields) == 3

    def test_field_map(self):
        """Test field_map cached property."""
        info = NodeSemanticInfo(
            node_type="class_definition",
            language="python",
            is_named=True,
            is_abstract=False,
            is_extra=False,
            is_root=False,
            abstract_category=None,
            concrete_subtypes=(),
            fields=(
                FieldInfo("name", True, False, ("identifier",)),
                FieldInfo("body", True, False, ("block",)),
            ),
            children_types=(),
        )

        field_map = info.field_map
        assert "name" in field_map
        assert "body" in field_map
        assert field_map["name"].required is True

        # Should be cached
        assert info.field_map is field_map

    def test_get_field(self):
        """Test get_field method."""
        info = NodeSemanticInfo(
            node_type="if_statement",
            language="python",
            is_named=True,
            is_abstract=False,
            is_extra=False,
            is_root=False,
            abstract_category=None,
            concrete_subtypes=(),
            fields=(
                FieldInfo("condition", True, False, ("expression",)),
                FieldInfo("consequence", True, False, ("block",)),
                FieldInfo("alternative", False, False, ("block",)),
            ),
            children_types=(),
        )

        condition = info.get_field("condition")
        assert condition is not None
        assert condition.name == "condition"
        assert condition.is_required is True

        nonexistent = info.get_field("nonexistent")
        assert nonexistent is None

    def test_has_field(self):
        """Test has_field method."""
        info = NodeSemanticInfo(
            node_type="for_statement",
            language="python",
            is_named=True,
            is_abstract=False,
            is_extra=False,
            is_root=False,
            abstract_category=None,
            concrete_subtypes=(),
            fields=(
                FieldInfo("left", True, False, ("identifier",)),
                FieldInfo("right", True, False, ("expression",)),
                FieldInfo("body", True, False, ("block",)),
            ),
            children_types=(),
        )

        assert info.has_field("left") is True
        assert info.has_field("right") is True
        assert info.has_field("body") is True
        assert info.has_field("nonexistent") is False

    def test_required_and_optional_field_names(self):
        """Test required_field_names and optional_field_names properties."""
        info = NodeSemanticInfo(
            node_type="function_definition",
            language="python",
            is_named=True,
            is_abstract=False,
            is_extra=False,
            is_root=False,
            abstract_category=None,
            concrete_subtypes=(),
            fields=(
                FieldInfo("name", True, False, ("identifier",)),
                FieldInfo("parameters", True, False, ("parameters",)),
                FieldInfo("body", True, False, ("block",)),
                FieldInfo("return_type", False, False, ("type",)),
            ),
            children_types=(),
        )

        required = info.required_field_names
        assert "name" in required
        assert "parameters" in required
        assert "body" in required
        assert "return_type" not in required

        optional = info.optional_field_names
        assert "return_type" in optional
        assert "name" not in optional

    def test_infer_semantic_category_callable(self):
        """Test semantic category inference for callable nodes."""
        # Function with parameters -> callable
        info = NodeSemanticInfo(
            node_type="function_definition",
            language="python",
            is_named=True,
            is_abstract=False,
            is_extra=False,
            is_root=False,
            abstract_category=None,
            concrete_subtypes=(),
            fields=(
                FieldInfo("name", True, False, ("identifier",)),
                FieldInfo("parameters", True, False, ("parameters",)),
                FieldInfo("body", True, False, ("block",)),
            ),
            children_types=(),
        )

        assert info.infer_semantic_category() == "callable"

    def test_infer_semantic_category_type_def(self):
        """Test semantic category inference for type definition nodes."""
        # Class with type_parameters -> type_def
        info = NodeSemanticInfo(
            node_type="class_definition",
            language="python",
            is_named=True,
            is_abstract=False,
            is_extra=False,
            is_root=False,
            abstract_category=None,
            concrete_subtypes=(),
            fields=(
                FieldInfo("name", True, False, ("identifier",)),
                FieldInfo("type_parameters", False, False, ("type_parameter_list",)),
                FieldInfo("body", True, False, ("block",)),
            ),
            children_types=(),
        )

        assert info.infer_semantic_category() == "type_def"

    def test_infer_semantic_category_control_flow(self):
        """Test semantic category inference for control flow nodes."""
        # If statement with condition -> control_flow
        info = NodeSemanticInfo(
            node_type="if_statement",
            language="python",
            is_named=True,
            is_abstract=False,
            is_extra=False,
            is_root=False,
            abstract_category=None,
            concrete_subtypes=(),
            fields=(
                FieldInfo("condition", True, False, ("expression",)),
                FieldInfo("consequence", True, False, ("block",)),
            ),
            children_types=(),
        )

        assert info.infer_semantic_category() == "control_flow"

    def test_infer_semantic_category_operation(self):
        """Test semantic category inference for operation nodes."""
        # Binary expression with operator -> operation
        info = NodeSemanticInfo(
            node_type="binary_expression",
            language="python",
            is_named=True,
            is_abstract=False,
            is_extra=False,
            is_root=False,
            abstract_category="expression",
            concrete_subtypes=(),
            fields=(
                FieldInfo("left", True, False, ("expression",)),
                FieldInfo("operator", True, False, ("+", "-", "*", "/")),
                FieldInfo("right", True, False, ("expression",)),
            ),
            children_types=(),
        )

        assert info.infer_semantic_category() == "operation"

    def test_infer_semantic_category_pattern_match(self):
        """Test semantic category inference for pattern matching nodes."""
        # Match statement with pattern -> pattern_match
        info = NodeSemanticInfo(
            node_type="match_statement",
            language="python",
            is_named=True,
            is_abstract=False,
            is_extra=False,
            is_root=False,
            abstract_category=None,
            concrete_subtypes=(),
            fields=(
                FieldInfo("pattern", True, False, ("pattern",)),
                FieldInfo("body", True, False, ("block",)),
            ),
            children_types=(),
        )

        assert info.infer_semantic_category() == "pattern_match"


class TestAbstractTypeInfo:
    """Tests for AbstractTypeInfo NamedTuple."""

    def test_basic_properties(self):
        """Test basic AbstractTypeInfo properties."""
        info = AbstractTypeInfo(
            abstract_type="expression",
            language="python",
            concrete_subtypes=("binary_expression", "unary_expression", "call"),
        )

        assert info.abstract_type == "expression"
        assert info.language == "python"
        assert len(info.concrete_subtypes) == 3
        assert info.subtype_count == 3

    def test_subtype_set(self):
        """Test subtype_set cached property."""
        info = AbstractTypeInfo(
            abstract_type="statement",
            language="python",
            concrete_subtypes=("if_statement", "while_statement", "for_statement"),
        )

        subtype_set = info.subtype_set
        assert isinstance(subtype_set, frozenset)
        assert "if_statement" in subtype_set
        assert "while_statement" in subtype_set

        # Should be cached
        assert info.subtype_set is subtype_set

    def test_is_subtype(self):
        """Test is_subtype method."""
        info = AbstractTypeInfo(
            abstract_type="expression",
            language="python",
            concrete_subtypes=("binary_expression", "unary_expression", "call", "list"),
        )

        assert info.is_subtype("binary_expression") is True
        assert info.is_subtype("call") is True
        assert info.is_subtype("if_statement") is False
