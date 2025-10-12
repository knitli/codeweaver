# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Regression tests to ensure no behavior changes from refactor."""

import sys

from pathlib import Path


# Add src to path to avoid circular imports during testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest

from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic.categories import SemanticNodeCategory, SemanticTier
from codeweaver.semantic.classifier import (
    SemanticNodeClassifier,
    classify_semantic_node,
    get_default_classifier,
)
from codeweaver.semantic.pattern_classifier import ClassificationPhase, PatternBasedClassifier


class TestCoreClassifications:
    """Regression tests for core node type classifications."""

    @pytest.mark.parametrize(
        "node_type,language,expected_category,min_confidence",
        [
            # Python
            ("function_definition", "python", SemanticNodeCategory.DEFINITION_CALLABLE, 0.80),
            ("class_definition", "python", SemanticNodeCategory.DEFINITION_TYPE, 0.80),
            ("if_statement", "python", SemanticNodeCategory.CONTROL_FLOW_CONDITIONAL, 0.75),
            ("for_statement", "python", SemanticNodeCategory.CONTROL_FLOW_ITERATION, 0.75),
            ("while_statement", "python", SemanticNodeCategory.CONTROL_FLOW_ITERATION, 0.75),
            ("return_statement", "python", SemanticNodeCategory.CONTROL_FLOW_RETURN, 0.75),
            ("import_statement", "python", SemanticNodeCategory.DEFINITION_MODULE_IMPORT, 0.75),
            # JavaScript
            ("function_declaration", "javascript", SemanticNodeCategory.DEFINITION_CALLABLE, 0.75),
            ("class_declaration", "javascript", SemanticNodeCategory.DEFINITION_TYPE, 0.75),
            ("if_statement", "javascript", SemanticNodeCategory.CONTROL_FLOW_CONDITIONAL, 0.70),
            # Rust
            ("function_item", "rust", SemanticNodeCategory.DEFINITION_CALLABLE, 0.70),
            ("struct_item", "rust", SemanticNodeCategory.DEFINITION_TYPE, 0.70),
        ],
    )
    def test_classification_consistency(
        self, node_type, language, expected_category, min_confidence
    ):
        """Test that classifications remain consistent after refactor."""
        result = classify_semantic_node(node_type, language)

        assert result.category == expected_category, (
            f"Classification changed for {node_type} in {language}"
        )
        assert result.confidence >= min_confidence, (
            f"Confidence dropped below threshold for {node_type} in {language}"
        )


class TestAPIBackwardCompatibility:
    """Regression tests for public API compatibility."""

    def test_classify_semantic_node_signature(self):
        """Test that classify_semantic_node has same signature."""
        result = classify_semantic_node("function_definition", "python")

        # Should return EnhancedClassificationResult
        assert hasattr(result, "category")
        assert hasattr(result, "confidence")
        assert hasattr(result, "phase")
        assert hasattr(result, "tier")

    def test_get_default_classifier(self):
        """Test that get_default_classifier still works."""
        classifier = get_default_classifier()

        assert isinstance(classifier, SemanticNodeClassifier)
        assert hasattr(classifier, "classify_node")

    def test_classifier_initialization(self):
        """Test that classifier can be initialized with same arguments."""
        # Should work without arguments
        classifier1 = SemanticNodeClassifier()
        assert classifier1 is not None

        # Should work with enable_confidence_scoring
        classifier2 = SemanticNodeClassifier(enable_confidence_scoring=True)
        assert classifier2 is not None

        # Should work with enable_contextual_extensions
        classifier3 = SemanticNodeClassifier(enable_contextual_extensions=True)
        assert classifier3 is not None


class TestTierAssignments:
    """Regression tests for tier assignments."""

    @pytest.mark.parametrize(
        "node_type,language,expected_tier",
        [
            ("function_definition", "python", SemanticTier.STRUCTURAL_DEFINITIONS),
            ("class_definition", "python", SemanticTier.STRUCTURAL_DEFINITIONS),
            ("if_statement", "python", SemanticTier.CONTROL_FLOW_LOGIC),
            ("binary_expression", "python", SemanticTier.OPERATIONS_EXPRESSIONS),
        ],
    )
    def test_tier_consistency(self, node_type, language, expected_tier):
        """Test that tier assignments remain consistent."""
        result = classify_semantic_node(node_type, language)

        assert result.tier == expected_tier, (
            f"Tier assignment changed for {node_type} in {language}"
        )


class TestBatchOperations:
    """Regression tests for batch operations."""

    def test_batch_classification_results(self):
        """Test that batch classification produces same results as individual."""
        node_types = [
            ("function_definition", "python"),
            ("class_definition", "python"),
            ("if_statement", "python"),
        ]

        classifier = get_default_classifier()
        batch_results = classifier.classify_batch(node_types)
        individual_results = [classifier.classify_node(nt, lang) for nt, lang in node_types]

        assert len(batch_results) == len(individual_results)
        for batch_res, indiv_res in zip(batch_results, individual_results, strict=False):
            assert batch_res.category == indiv_res.category
            # Confidence might vary slightly, but should be close
            assert abs(batch_res.confidence - indiv_res.confidence) < 0.05


class TestPatternClassifierCompatibility:
    """Regression tests for PatternBasedClassifier (formerly HierarchicalMapper)."""

    def test_pattern_classifier_exists(self):
        """Test that PatternBasedClassifier can be imported and instantiated."""
        classifier = PatternBasedClassifier()
        assert classifier is not None

    def test_hierarchical_mapper_alias(self):
        """Test that HierarchicalMapper alias still works."""
        from codeweaver.semantic.pattern_classifier import HierarchicalMapper

        # Should be an alias for PatternBasedClassifier
        mapper = HierarchicalMapper()
        assert isinstance(mapper, PatternBasedClassifier)

    def test_pattern_classifier_classify_node(self):
        """Test that PatternBasedClassifier.classify_node still works."""
        classifier = PatternBasedClassifier()
        result = classifier.classify_node("function_definition", SemanticSearchLanguage.PYTHON)

        assert result.category is not None
        assert result.confidence > 0
        assert isinstance(result.phase, ClassificationPhase)


class TestConfidenceImprovements:
    """Tests to verify confidence improvements from grammar-based classification."""

    def test_grammar_classified_nodes_high_confidence(self):
        """Test that nodes classified via grammar have high confidence."""
        high_confidence_nodes = [
            ("function_definition", "python"),
            ("class_definition", "python"),
            ("if_statement", "python"),
        ]

        for node_type, language in high_confidence_nodes:
            result = classify_semantic_node(node_type, language)

            if result.extension_source == "grammar":
                assert result.confidence >= 0.80, (
                    f"Grammar-based classification should have high confidence for {node_type}"
                )

    def test_no_regression_in_confidence(self):
        """Test that confidence hasn't regressed for common nodes."""
        baseline_nodes = [
            ("function_definition", "python", 0.75),
            ("class_definition", "python", 0.75),
            ("if_statement", "python", 0.70),
        ]

        for node_type, language, min_confidence in baseline_nodes:
            result = classify_semantic_node(node_type, language)
            assert result.confidence >= min_confidence, (
                f"Confidence regressed for {node_type} in {language}"
            )


class TestEdgeCases:
    """Regression tests for edge cases."""

    def test_unknown_node_types(self):
        """Test that unknown node types still get classified."""
        result = classify_semantic_node("completely_unknown_node_type", "python")

        # Should still return a classification (fallback)
        assert result.category is not None
        assert result.confidence > 0

    def test_empty_node_type(self):
        """Test handling of empty node type."""
        result = classify_semantic_node("", "python")

        # Should handle gracefully
        assert result.category is not None

    def test_punctuation_nodes(self):
        """Test that punctuation nodes are still classified."""
        punctuation_nodes = ["(", ")", "{", "}", ";", ","]

        for node in punctuation_nodes:
            result = classify_semantic_node(node, "python")

            # Should be classified as syntactic
            assert result.tier == SemanticTier.SYNTAX_REFERENCES


class TestNoBreakingChanges:
    """Tests to ensure no breaking changes in the refactor."""

    def test_classification_result_attributes(self):
        """Test that ClassificationResult has all expected attributes."""
        result = classify_semantic_node("function_definition", "python")

        # Core attributes that must exist
        required_attrs = [
            "category",
            "confidence",
            "phase",
            "tier",
            "matched_pattern",
            "alternative_categories",
        ]

        for attr in required_attrs:
            assert hasattr(result, attr), f"Missing attribute: {attr}"

    def test_semantic_node_category_enum(self):
        """Test that SemanticNodeCategory enum is unchanged."""
        # Key categories that should exist
        expected_categories = [
            "DEFINITION_CALLABLE",
            "DEFINITION_TYPE",
            "CONTROL_FLOW_CONDITIONAL",
            "CONTROL_FLOW_ITERATION",
            "CONTROL_FLOW_RETURN",
            "OPERATION_COMPUTATION",
            "SYNTAX_REFERENCES",
        ]

        for category_name in expected_categories:
            assert hasattr(SemanticNodeCategory, category_name), (
                f"Missing category: {category_name}"
            )

    def test_semantic_tier_enum(self):
        """Test that SemanticTier enum is unchanged."""
        expected_tiers = [
            "STRUCTURAL_DEFINITIONS",
            "BEHAVIORAL_CONTRACTS",
            "CONTROL_FLOW_LOGIC",
            "OPERATIONS_EXPRESSIONS",
            "SYNTAX_REFERENCES",
        ]

        for tier_name in expected_tiers:
            assert hasattr(SemanticTier, tier_name), f"Missing tier: {tier_name}"
