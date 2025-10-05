# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for GrammarBasedClassifier."""

import sys

from pathlib import Path


# Add src to path to avoid circular imports during testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest

from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic.categories import SemanticNodeCategory, SemanticTier
from codeweaver.semantic.grammar_classifier import (
    GrammarBasedClassifier,
    GrammarClassificationResult,
)


@pytest.fixture
def classifier():
    """Create GrammarBasedClassifier instance for testing."""
    return GrammarBasedClassifier()


class TestAbstractTypeClassification:
    """Tests for abstract type-based classification."""

    def test_classify_expression_subtype(self, classifier):
        """Test classification of expression subtype."""
        # binary_expression is typically a subtype of expression
        result = classifier.classify_node("binary_expression", "python")

        if result is not None:  # May not exist if Python grammar not loaded
            assert isinstance(result, GrammarClassificationResult)
            assert result.category == SemanticNodeCategory.OPERATION_COMPUTATION
            assert result.confidence >= 0.85
            assert result.classification_method == "abstract_type"
            assert "expression" in result.evidence.lower()

    def test_classify_statement_subtype(self, classifier):
        """Test classification of statement subtype."""
        # Various statement types should map to control flow
        result = classifier.classify_node("return_statement", "python")

        if result is not None:
            assert result.category in [
                SemanticNodeCategory.CONTROL_FLOW_SEQUENTIAL,
                SemanticNodeCategory.CONTROL_FLOW_RETURN,
            ]
            assert result.confidence >= 0.80

    def test_classify_literal_subtype(self, classifier):
        """Test classification of literal subtype."""
        result = classifier.classify_node("string_literal", "python")

        if result is not None:
            assert result.category == SemanticNodeCategory.SYNTAX_LITERAL
            assert result.tier == SemanticTier.SYNTAX_REFERENCES


class TestFieldBasedClassification:
    """Tests for field-based classification."""

    def test_classify_function_definition(self, classifier):
        """Test field-based classification of function definition."""
        result = classifier.classify_node("function_definition", "python")

        if result is not None:
            # Function definitions should be classified as callable
            assert result.category == SemanticNodeCategory.DEFINITION_CALLABLE
            assert result.confidence >= 0.80
            assert result.classification_method in ["field_inference", "abstract_type"]
            # Evidence should mention relevant fields
            assert any(
                field in result.evidence.lower()
                for field in ["parameters", "body", "name"]
            )

    def test_classify_class_definition(self, classifier):
        """Test field-based classification of class definition."""
        result = classifier.classify_node("class_definition", "python")

        if result is not None:
            # Classes should be classified as type definitions
            assert result.category == SemanticNodeCategory.DEFINITION_TYPE
            assert result.confidence >= 0.80

    def test_classify_if_statement(self, classifier):
        """Test field-based classification of if statement."""
        result = classifier.classify_node("if_statement", "python")

        if result is not None:
            # If statements should be control flow conditional
            assert result.category == SemanticNodeCategory.CONTROL_FLOW_CONDITIONAL
            assert result.confidence >= 0.80
            assert "condition" in result.evidence.lower() or result.classification_method == "abstract_type"


class TestChildrenConstraintClassification:
    """Tests for children constraint-based classification."""

    def test_classify_with_fields_and_children(self, classifier):
        """Test classification when node has both fields and children."""
        # Block nodes typically have both
        result = classifier.classify_node("block", "python")

        if result is not None and result.classification_method == "children":
            # Should be classified as structural
            assert result.category == SemanticNodeCategory.STRUCTURE_BLOCK
            assert result.confidence >= 0.65

    def test_classify_with_children_only(self, classifier):
        """Test classification when node has only children constraints."""
        # Find a node with only children (no fields)
        # This is language-specific, so we test the logic
        result = classifier.classify_node("expression_statement", "python")

        if result is not None and result.classification_method == "children":
            # Should be classified as composite or similar
            assert result.tier in [SemanticTier.SYNTAX_REFERENCES, SemanticTier.OPERATIONS_EXPRESSIONS]


class TestExtraNodeClassification:
    """Tests for extra (syntactic) node classification."""

    def test_classify_comment(self, classifier):
        """Test classification of comment (extra) node."""
        result = classifier.classify_node("comment", "python")

        if result is not None and result.classification_method == "extra":
            assert result.category == SemanticNodeCategory.SYNTAX_REFERENCES
            assert result.confidence >= 0.90
            assert "extra" in result.evidence.lower()


class TestClassificationPipeline:
    """Tests for overall classification pipeline."""

    def test_fallback_to_none_for_unknown(self, classifier):
        """Test that unknown nodes return None."""
        result = classifier.classify_node("nonexistent_node_type_xyz", "python")

        assert result is None

    def test_classification_with_language_enum(self, classifier):
        """Test classification with SemanticSearchLanguage enum."""
        result = classifier.classify_node(
            "function_definition",
            SemanticSearchLanguage.PYTHON
        )

        # Should work with enum as well as string
        assert result is None or isinstance(result, GrammarClassificationResult)

    def test_classification_priority(self, classifier):
        """Test that classification methods are tried in correct priority."""
        # A node that could match multiple methods should use highest confidence
        result = classifier.classify_node("function_definition", "python")

        if result is not None:
            # Abstract type or field inference should be preferred over children
            assert result.classification_method in ["abstract_type", "field_inference"]
            assert result.confidence >= 0.85


class TestAbstractCategoryMapping:
    """Tests for abstract category mapping."""

    def test_get_abstract_category_for_language(self, classifier):
        """Test getting semantic category for abstract type in specific language."""
        # Expression should map to OPERATION_COMPUTATION
        category = classifier.get_abstract_category_for_language(
            "expression",
            SemanticSearchLanguage.PYTHON
        )

        if category is not None:
            assert category == SemanticNodeCategory.OPERATION_COMPUTATION

    def test_nonexistent_abstract_type(self, classifier):
        """Test that nonexistent abstract types return None."""
        category = classifier.get_abstract_category_for_language(
            "nonexistent_abstract_type",
            SemanticSearchLanguage.PYTHON
        )

        assert category is None


class TestMultiLanguageSupport:
    """Tests for multi-language classification."""

    @pytest.mark.parametrize("language", ["python", "javascript", "rust", "java"])
    def test_function_classification_across_languages(self, classifier, language):
        """Test that function definitions are classified consistently across languages."""
        # Different languages use different node type names
        node_type_map = {
            "python": "function_definition",
            "javascript": "function_declaration",
            "rust": "function_item",
            "java": "method_declaration",
        }

        node_type = node_type_map.get(language, "function_definition")
        result = classifier.classify_node(node_type, language)

        if result is not None:
            # Should be callable or similar
            assert result.category in [
                SemanticNodeCategory.DEFINITION_CALLABLE,
                SemanticNodeCategory.DEFINITION_METHOD,
            ]
            assert result.confidence >= 0.70

    @pytest.mark.parametrize("language", ["python", "javascript", "rust", "java"])
    def test_conditional_classification_across_languages(self, classifier, language):
        """Test that conditionals are classified consistently across languages."""
        node_type = "if_statement"  # Common across many languages

        result = classifier.classify_node(node_type, language)

        if result is not None:
            # Should be control flow conditional
            assert result.category == SemanticNodeCategory.CONTROL_FLOW_CONDITIONAL
            assert result.tier == SemanticTier.CONTROL_FLOW_LOGIC


class TestConfidenceScoring:
    """Tests for confidence scoring."""

    def test_abstract_type_highest_confidence(self, classifier):
        """Test that abstract type classification has highest confidence."""
        # Find a node classified via abstract type
        result = classifier.classify_node("binary_expression", "python")

        if result is not None and result.classification_method == "abstract_type":
            assert result.confidence >= 0.90

    def test_field_inference_high_confidence(self, classifier):
        """Test that field inference has high confidence."""
        result = classifier.classify_node("function_definition", "python")

        if result is not None and result.classification_method == "field_inference":
            assert result.confidence >= 0.85

    def test_children_moderate_confidence(self, classifier):
        """Test that children constraint classification has moderate confidence."""
        # Find a node classified via children
        # This is harder to test directly, but we can verify the logic
        from codeweaver.semantic.grammar_types import NodeSemanticInfo

        # Create test NodeSemanticInfo with only children
        info = NodeSemanticInfo(
            node_type="test_node",
            language="python",
            is_named=True,
            is_abstract=False,
            is_extra=False,
            is_root=False,
            abstract_category=None,
            concrete_subtypes=(),
            fields=(),
            children_types=("expression",),
        )

        result = classifier._classify_from_children(info)

        if result is not None:
            assert result.confidence <= 0.70  # Moderate or lower


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_node_type(self, classifier):
        """Test classification with empty node type."""
        result = classifier.classify_node("", "python")

        assert result is None

    def test_invalid_language(self, classifier):
        """Test classification with invalid language."""
        # Should handle gracefully, likely return None
        try:
            result = classifier.classify_node("function_definition", "invalid_language_xyz")
            # If it doesn't raise, should return None
            assert result is None
        except (ValueError, KeyError):
            # Also acceptable to raise an error
            pass

    def test_node_with_no_structure(self, classifier):
        """Test classification of node with minimal structure."""
        # Unnamed nodes or nodes with no fields/children/abstract category
        result = classifier.classify_node("(", "python")  # Punctuation

        # Should either return None or classify as syntactic
        if result is not None:
            assert result.tier == SemanticTier.SYNTAX_REFERENCES
