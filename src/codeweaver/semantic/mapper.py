# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Node mapping system for converting language-specific node types to semantic categories."""

from __future__ import annotations

from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic.categories import ImportanceScoresDict, SemanticNodeCategory
from codeweaver.semantic.classifier import (
    CoverageReport,
    EnhancedClassificationResult,
    NodeClassificationReport,
    SemanticNodeClassifier,
    get_default_classifier,
)


class NodeMapper:
    """Maps language-specific AST node types to semantic categories using hierarchical classification."""

    def __init__(self, classifier: SemanticNodeClassifier | None = None) -> None:
        """Initialize the NodeMapper with an optional custom classifier."""
        self.classifier = classifier or get_default_classifier()

    def classify_node_type(
        self, node_type: str, language: SemanticSearchLanguage | str, context: str | None = None
    ) -> SemanticNodeCategory:
        """Classify a node type into a semantic category.

        Args:
            node_type: The tree-sitter node type name
            language: Language context for language-specific classifications
            context: Optional context information

        Returns:
            The semantic category for this node type
        """
        result = self.classifier.classify_node(node_type, language, context)
        return result.category

    def get_classification_confidence(
        self, node_type: str, language: SemanticSearchLanguage | str, context: str | None = None
    ) -> float:
        """Get confidence score for the classification of a node type.

        Args:
            node_type: The node type to assess
            language: Language context
            context: Optional context information

        Returns:
            Confidence score from 0.0 to 1.0
        """
        result = self.classifier.classify_node(node_type, language, context)
        return result.confidence

    def get_detailed_classification(
        self,
        node_type: str,
        language: SemanticSearchLanguage | str,
        context: str | None = None,
        context_weights: ImportanceScoresDict | None = None,
        parent_type: str | None = None,
        sibling_types: list[str] | None = None,
        file_path: str | None = None,
    ) -> EnhancedClassificationResult:
        """Get detailed classification result with confidence metrics and alternatives.

        Args:
            node_type: The tree-sitter node type name
            language: Language context
            context: Optional context information
            context_weights: Optional context weights for confidence scoring
            parent_type: Optional parent node type for context
            sibling_types: Optional sibling node types for context
            file_path: Optional file path for context

        Returns:
            Enhanced classification result with detailed metrics
        """
        return self.classifier.classify_node(
            node_type, language, context, context_weights, parent_type, sibling_types, file_path
        )

    def classify_batch(
        self,
        node_types: list[tuple[str, SemanticSearchLanguage | str]],
        context: str | None = None,
        context_weights: ImportanceScoresDict | None = None,
    ) -> list[EnhancedClassificationResult]:
        """Classify multiple node types efficiently.

        Args:
            node_types: List of (node_type, language) tuples
            context: Optional context information
            context_weights: Optional context weights for confidence scoring

        Returns:
            List of enhanced classification results
        """
        return self.classifier.classify_batch(node_types, context, context_weights)

    def get_classification_alternatives(
        self,
        node_type: str,
        language: SemanticSearchLanguage | str,
        threshold: float = 0.3,
        max_alternatives: int = 5,
    ) -> list[EnhancedClassificationResult]:
        """Get alternative classifications above confidence threshold.

        Args:
            node_type: The node type to classify
            language: Language context
            threshold: Minimum confidence threshold for alternatives
            max_alternatives: Maximum number of alternatives to return

        Returns:
            List of alternative classification results
        """
        return self.classifier.get_classification_alternatives(
            node_type, language, threshold, max_alternatives
        )

    def analyze_classification_quality(
        self, node_types: list[tuple[str, SemanticSearchLanguage | str]]
    ) -> NodeClassificationReport:
        """Analyze classification quality across a set of node types.

        Args:
            node_types: List of (node_type, language) tuples to analyze

        Returns:
            Dictionary with quality metrics
        """
        return self.classifier.analyze_classification_quality(node_types)

    def validate_language_coverage(
        self, language: SemanticSearchLanguage | str, sample_node_types: list[str]
    ) -> dict[str, CoverageReport]:
        """Validate classification coverage for a language.

        Args:
            language: Language to validate
            sample_node_types: Sample node types to test

        Returns:
            Dictionary mapping node types to their classification details
        """
        return self.classifier.validate_language_coverage(language, sample_node_types)


# Global instance for convenient access
_default_mapper: NodeMapper | None = None


def get_node_mapper() -> NodeMapper:
    """Get the default global NodeMapper instance."""
    global _default_mapper
    if _default_mapper is None:
        _default_mapper = NodeMapper()
    return _default_mapper


# Convenient functions that mirror the old API but use the new system
def classify_node_type(
    node_type: str, language: SemanticSearchLanguage | str, context: str | None = None
) -> SemanticNodeCategory:
    """Convenient function to classify a single node type."""
    return get_node_mapper().classify_node_type(node_type, language, context)


def get_classification_confidence(
    node_type: str, language: SemanticSearchLanguage | str, context: str | None = None
) -> float:
    """Convenient function to get classification confidence."""
    return get_node_mapper().get_classification_confidence(node_type, language, context)


def classify_batch(
    node_types: list[tuple[str, SemanticSearchLanguage | str]],
    context: str | None = None,
    context_weights: ImportanceScoresDict | None = None,
) -> list[EnhancedClassificationResult]:
    """Convenient function for batch classification."""
    return get_node_mapper().classify_batch(node_types, context, context_weights)


def analyze_classification_quality(
    node_types: list[tuple[str, SemanticSearchLanguage | str]],
) -> NodeClassificationReport:
    """Convenient function to analyze classification quality."""
    return get_node_mapper().analyze_classification_quality(node_types)
