# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration tests for full classification pipeline."""

import sys

from pathlib import Path


# Add src to path to avoid circular imports during testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest

from codeweaver.semantic.classifications import SemanticNodeCategory, SemanticTier
from codeweaver.semantic.classifier import SemanticNodeClassifier


@pytest.fixture
def classifier():
    """Create SemanticNodeClassifier instance for testing."""
    return SemanticNodeClassifier()


class TestGrammarFirstRouting:
    """Tests for grammar-first classification routing."""

    def test_grammar_classification_preferred(self, classifier):
        """Test that grammar-based classification is used when available."""
        # Function definitions should be classified via grammar
        result = classifier.classify_node("function_definition", "python")

        assert result.category == SemanticNodeCategory.DEFINITION_CALLABLE
        assert result.confidence >= 0.80
        # Should be from grammar or tier_1 phase, not pattern fallback
        assert result.extension_source in ["grammar", "language_extension"]

    def test_pattern_fallback_for_unknown(self, classifier):
        """Test that pattern-based classification is used as fallback."""
        # Made-up node type should fall back to pattern matching
        result = classifier.classify_node("unknown_custom_node", "python")

        # Should still get a classification (fallback)
        assert result.category is not None
        assert result.extension_source in ["hierarchical", "pattern_fallback", "grammar"]

    def test_language_extensions_highest_priority(self, classifier):
        """Test that language extensions have highest priority."""
        # Rust trait_impl should use language extension if available
        result = classifier.classify_node("trait_impl", "rust")

        if result.extension_source == "language_extension":
            # Language extensions should have high confidence
            assert result.confidence >= 0.85


class TestFullPipelineFlow:
    """Tests for complete classification pipeline flow."""

    def test_four_phase_pipeline(self, classifier):
        """Test that all four phases work correctly."""
        # Phase 1: Extensions
        # Phase 2: Grammar-based
        # Phase 3: Pattern-based fallback
        # Phase 4: Refinements

        result = classifier.classify_node("class_definition", "python")

        assert result.category == SemanticNodeCategory.DEFINITION_TYPE
        assert result.tier == SemanticTier.STRUCTURAL_DEFINITIONS
        assert result.confidence > 0

    @pytest.mark.parametrize(
        "node_type,expected_category",
        [
            ("function_definition", SemanticNodeCategory.DEFINITION_CALLABLE),
            ("class_definition", SemanticNodeCategory.DEFINITION_TYPE),
            ("if_statement", SemanticNodeCategory.CONTROL_FLOW_CONDITIONAL),
        ],
    )
    def test_common_nodes_classified_correctly(self, classifier, node_type, expected_category):
        """Test that common nodes are classified correctly."""
        result = classifier.classify_node(node_type, "python")

        assert result.category == expected_category
        assert result.confidence >= 0.70


class TestMultiLanguageIntegration:
    """Tests for multi-language classification integration."""

    @pytest.mark.parametrize("language", ["python", "javascript", "rust", "java"])
    def test_grammar_classification_across_languages(self, classifier, language):
        """Test that grammar-based classification works across languages."""
        # Different node type names per language
        node_type_map = {
            "python": "function_definition",
            "javascript": "function_declaration",
            "rust": "function_item",
            "java": "method_declaration",
        }

        node_type = node_type_map.get(language, "function_definition")
        result = classifier.classify_node(node_type, language)

        # All should classify as callable or method
        assert result.category in [
            SemanticNodeCategory.DEFINITION_CALLABLE,
            SemanticNodeCategory.DEFINITION_METHOD,
        ]
        assert result.confidence >= 0.70


class TestConfidenceScoring:
    """Tests for confidence scoring integration."""

    def test_high_confidence_grammar_classification(self, classifier):
        """Test that grammar-based classifications have high confidence."""
        result = classifier.classify_node("function_definition", "python")

        if result.extension_source == "grammar":
            assert result.is_high_confidence
            assert result.confidence >= 0.80

    def test_confidence_metrics_populated(self, classifier):
        """Test that confidence metrics are populated."""
        result = classifier.classify_node("function_definition", "python")

        if result.confidence_metrics:
            assert result.confidence_metrics.base_confidence > 0
            assert result.confidence_metrics.final_confidence > 0

    def test_confidence_grade_assignment(self, classifier):
        """Test that confidence grades are assigned correctly."""
        result = classifier.classify_node("function_definition", "python")

        assert result.confidence_grade in ["A", "B", "C", "D", "F"]
        if result.confidence >= 0.90:
            assert result.confidence_grade == "A"


class TestBatchProcessing:
    """Tests for batch classification integration."""

    def test_batch_classification(self, classifier):
        """Test batch classification with mixed node types."""
        node_types = [
            ("function_definition", "python"),
            ("class_definition", "python"),
            ("if_statement", "python"),
        ]

        results = classifier.classify_batch(node_types)

        assert len(results) == 3
        for result in results:
            assert result.category is not None
            assert result.confidence > 0

    def test_batch_with_multiple_languages(self, classifier):
        """Test batch classification across multiple languages."""
        node_types = [
            ("function_definition", "python"),
            ("function_declaration", "javascript"),
            ("function_item", "rust"),
        ]

        results = classifier.classify_batch(node_types)

        assert len(results) == 3
        # All should be callable
        for result in results:
            assert result.category in [
                SemanticNodeCategory.DEFINITION_CALLABLE,
                SemanticNodeCategory.DEFINITION_METHOD,
            ]


class TestClassificationAlternatives:
    """Tests for classification alternatives."""

    def test_get_alternatives(self, classifier):
        """Test getting classification alternatives."""
        alternatives = classifier.get_classification_alternatives(
            "function_definition", "python", threshold=0.3
        )

        assert len(alternatives) > 0
        # Primary classification should be first
        assert alternatives[0].category == SemanticNodeCategory.DEFINITION_CALLABLE
        # Should be sorted by confidence
        for i in range(len(alternatives) - 1):
            assert alternatives[i].confidence >= alternatives[i + 1].confidence


class TestQualityAnalysis:
    """Tests for classification quality analysis."""

    def test_quality_metrics(self, classifier):
        """Test quality metrics calculation."""
        node_types = [
            ("function_definition", "python"),
            ("class_definition", "python"),
            ("if_statement", "python"),
            ("for_statement", "python"),
        ]

        report = classifier.analyze_classification_quality(node_types)

        assert report["total_classifications"] == 4
        assert 0 <= report["high_confidence_percentage"] <= 100
        assert 0 <= report["average_confidence"] <= 1.0
        assert len(report["phase_distribution"]) > 0

    def test_language_coverage_validation(self, classifier):
        """Test language coverage validation."""
        sample_nodes = ["function_definition", "class_definition", "if_statement"]

        coverage = classifier.validate_language_coverage("python", sample_nodes)

        assert len(coverage) == 3
        for node_type, report in coverage.items():
            assert report["category"] is not None
            assert 0 <= report["confidence"] <= 1.0
            assert report["grade"] in ["A", "B", "C", "D", "F"]


class TestBackwardCompatibility:
    """Tests for backward compatibility."""

    def test_public_api_unchanged(self):
        """Test that public API is unchanged."""
        from codeweaver.semantic.classifier import classify_semantic_node

        result = classify_semantic_node("function_definition", "python")

        assert result.category == SemanticNodeCategory.DEFINITION_CALLABLE
        assert hasattr(result, "confidence")
        assert hasattr(result, "category")

    def test_classification_result_structure(self, classifier):
        """Test that classification result structure is preserved."""
        result = classifier.classify_node("function_definition", "python")

        # Required attributes
        assert hasattr(result, "category")
        assert hasattr(result, "confidence")
        assert hasattr(result, "phase")
        assert hasattr(result, "tier")

        # Optional attributes
        assert hasattr(result, "matched_pattern")
        assert hasattr(result, "alternative_categories")
