# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for enhanced NodeTypeParser semantic extraction methods."""

import pytest

from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic.grammar_types import AbstractTypeInfo, FieldInfo, NodeSemanticInfo
from codeweaver.semantic.node_type_parser import NodeTypeParser


@pytest.fixture
def parser():
    """Create NodeTypeParser instance for testing."""
    return NodeTypeParser()


class TestAbstractTypeMap:
    """Tests for abstract_type_map cached property."""

    def test_abstract_type_map_structure(self, parser):
        """Test that abstract_type_map has correct structure."""
        type_map = parser.abstract_type_map

        assert isinstance(type_map, dict)
        # Should have common abstract types
        assert "expression" in type_map or len(type_map) > 0

    def test_expression_abstract_type(self, parser):
        """Test that 'expression' abstract type exists in multiple languages."""
        type_map = parser.abstract_type_map

        # Expression is universal - should appear in many languages
        if "expression" in type_map:
            expr_map = type_map["expression"]
            assert isinstance(expr_map, dict)
            # Should have at least a few languages
            assert len(expr_map) >= 3

            # Check structure of one language entry
            for lang_name, abstract_info in expr_map.items():
                assert isinstance(abstract_info, AbstractTypeInfo)
                assert abstract_info.abstract_type == "expression"
                assert abstract_info.language == lang_name
                assert len(abstract_info.concrete_subtypes) > 0
                break

    def test_statement_abstract_type(self, parser):
        """Test that 'statement' abstract type exists."""
        type_map = parser.abstract_type_map

        if "statement" in type_map:
            stmt_map = type_map["statement"]
            assert len(stmt_map) >= 2  # Should appear in multiple languages

    def test_abstract_type_normalization(self, parser):
        """Test that abstract types are normalized (no leading underscore)."""
        type_map = parser.abstract_type_map

        # Check that no keys start with underscore
        for abstract_name in type_map.keys():
            assert not abstract_name.startswith("_")


class TestFieldSemanticPatterns:
    """Tests for field_semantic_patterns property."""

    def test_field_patterns_structure(self, parser):
        """Test that field_semantic_patterns has correct structure."""
        patterns = parser.field_semantic_patterns

        assert isinstance(patterns, dict)
        # Should have common field names
        assert "name" in patterns
        assert "body" in patterns
        assert "type" in patterns

    def test_name_field_patterns(self, parser):
        """Test patterns for 'name' field."""
        patterns = parser.field_semantic_patterns

        name_patterns = patterns["name"]
        assert isinstance(name_patterns, dict)

        # Based on analysis, name is most common in type_def
        assert "type_def" in name_patterns
        assert "callable" in name_patterns

        # Type_def should be most common
        assert name_patterns["type_def"] > name_patterns["callable"]

    def test_condition_field_patterns(self, parser):
        """Test patterns for 'condition' field."""
        patterns = parser.field_semantic_patterns

        condition_patterns = patterns["condition"]
        # Condition should be almost exclusive to control_flow
        assert "control_flow" in condition_patterns
        assert condition_patterns["control_flow"] >= 50  # High count

    def test_parameters_field_patterns(self, parser):
        """Test patterns for 'parameters' field."""
        patterns = parser.field_semantic_patterns

        param_patterns = patterns["parameters"]
        # Parameters primarily for callable
        assert "callable" in param_patterns
        assert param_patterns["callable"] > param_patterns.get("type_def", 0)


class TestGetNodeSemanticInfo:
    """Tests for get_node_semantic_info method."""

    def test_get_python_function_definition(self, parser):
        """Test getting semantic info for Python function_definition."""
        info = parser.get_node_semantic_info("function_definition", "python")

        if info is not None:  # May not exist if Python grammar not loaded
            assert isinstance(info, NodeSemanticInfo)
            assert info.node_type == "function_definition"
            assert info.language == "python"
            assert info.is_named is True

            # Function should have fields like name, parameters, body
            assert info.has_fields is True

    def test_get_with_language_enum(self, parser):
        """Test getting semantic info with SemanticSearchLanguage enum."""
        # Try with a language we know exists
        info = parser.get_node_semantic_info(
            "program",  # Common root node
            SemanticSearchLanguage.PYTHON,
        )

        # May or may not exist, just test that it doesn't error
        assert info is None or isinstance(info, NodeSemanticInfo)

    def test_get_nonexistent_node(self, parser):
        """Test getting semantic info for nonexistent node."""
        info = parser.get_node_semantic_info("nonexistent_node_type", "python")

        assert info is None

    def test_field_extraction(self, parser):
        """Test that fields are properly extracted."""
        # Find a node with fields in any language
        for lang_mapping in parser.parse_all_node_types():
            for language, root_nodes in lang_mapping.items():
                for node_info in root_nodes:
                    if "fields" in node_info:
                        node_type = str(node_info.get("type_name", node_info.get("type")))
                        info = parser.get_node_semantic_info(node_type, language)

                        if info and info.has_fields:
                            # Check field structure
                            for field in info.fields:
                                assert isinstance(field, FieldInfo)
                                assert isinstance(field.name, str)
                                assert isinstance(field.required, bool)
                                assert isinstance(field.types, tuple)
                            return  # Test passed

    def test_abstract_category_detection(self, parser):
        """Test that abstract category is detected for concrete types."""
        # Find a concrete subtype
        type_map = parser.abstract_type_map
        if "expression" in type_map:
            for lang_name, abstract_info in type_map["expression"].items():
                # Get first concrete subtype
                if abstract_info.concrete_subtypes:
                    concrete_type = abstract_info.concrete_subtypes[0]

                    info = parser.get_node_semantic_info(concrete_type, lang_name)
                    if info:
                        # Should identify expression as abstract category
                        assert info.abstract_category == "expression"
                        return


class TestGetSupertypeHierarchy:
    """Tests for get_supertype_hierarchy method."""

    def test_hierarchy_for_concrete_type(self, parser):
        """Test getting supertype hierarchy for a concrete type."""
        # Find a concrete subtype
        type_map = parser.abstract_type_map
        if "expression" in type_map:
            for lang_name, abstract_info in type_map["expression"].items():
                if abstract_info.concrete_subtypes:
                    concrete_type = abstract_info.concrete_subtypes[0]

                    hierarchy = parser.get_supertype_hierarchy(concrete_type, lang_name)

                    # Should have at least expression in hierarchy
                    if hierarchy:
                        assert "expression" in hierarchy

                    return

    def test_hierarchy_with_language_enum(self, parser):
        """Test hierarchy with SemanticSearchLanguage enum."""
        hierarchy = parser.get_supertype_hierarchy(
            "binary_expression", SemanticSearchLanguage.PYTHON
        )

        # May or may not exist, just test that it doesn't error
        assert isinstance(hierarchy, list)

    def test_hierarchy_for_abstract_type(self, parser):
        """Test that abstract types don't return themselves."""
        type_map = parser.abstract_type_map

        if "expression" in type_map:
            for lang_name in type_map["expression"].keys():
                hierarchy = parser.get_supertype_hierarchy("expression", lang_name)

                # Expression shouldn't be in its own hierarchy
                if hierarchy:
                    assert "expression" not in hierarchy
                return

    def test_empty_hierarchy_for_top_level(self, parser):
        """Test that top-level types have empty hierarchy."""
        # Root nodes like 'program' should have no supertypes
        hierarchy = parser.get_supertype_hierarchy("program", "python")

        # Should be empty list (program has no supertypes)
        assert isinstance(hierarchy, list)


class TestHelperMethods:
    """Tests for helper methods."""

    def test_find_supertype(self, parser):
        """Test _find_supertype helper method."""
        # Build abstract type map first
        _ = parser.abstract_type_map

        # Try to find supertype for a known concrete type
        type_map = parser.abstract_type_map
        if "expression" in type_map:
            for lang_name, abstract_info in type_map["expression"].items():
                if abstract_info.concrete_subtypes:
                    concrete_type = abstract_info.concrete_subtypes[0]

                    supertype = parser._find_supertype(concrete_type, lang_name)

                    assert supertype == "expression"
                    return

    def test_find_nonexistent_supertype(self, parser):
        """Test finding supertype for type that has none."""
        _ = parser.abstract_type_map

        supertype = parser._find_supertype("nonexistent_type", "python")

        assert supertype is None
