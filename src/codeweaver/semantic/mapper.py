# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Node mapping system for converting language-specific node types to semantic categories."""

from __future__ import annotations

from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic._types import ThingName
from codeweaver.semantic.classifications import ImportanceScoresDict, SemanticClass
from codeweaver.semantic.classifier import (
    CoverageReport,
    EnhancedClassificationResult,
    SemanticThingClassifier,
    ThingClassificationReport,
    get_default_classifier,
)


class ThingMapper:
    """Maps language-specific AST node types to semantic categories using hierarchical classification."""

    def __init__(self, classifier: SemanticThingClassifier | None = None) -> None:
        """Initialize the ThingMapper with an optional custom classifier."""
        self.classifier = classifier or get_default_classifier()

    def classify_thing(
        self,
        thing_name: ThingName,
        language: SemanticSearchLanguage | str,
        context: str | None = None,
    ) -> SemanticClass:
        """Classify a thing into a semantic category.

        Args:
            thing_name: The name of the thing to classify
            language: Language context for language-specific classifications
            context: Optional context information

        Returns:
            The semantic category for this thing
        """
        result = self.classifier.classify_thing(thing_name, language, context)
        return result.classification

    def get_classification_confidence(
        self,
        thing_name: ThingName,
        language: SemanticSearchLanguage | str,
        context: str | None = None,
    ) -> float:
        """Get confidence score for the classification of a node type.

        Args:
            thing_name: The tree-sitter node type name
            language: Language context
            context: Optional context information

        Returns:
            Confidence score from 0.0 to 1.0
        """
        result = self.classifier.classify_thing(thing_name, language, context)
        return result.confidence

    def get_detailed_classification(
        self,
        thing_name: ThingName,
        language: SemanticSearchLanguage | str,
        context: str | None = None,
        context_weights: ImportanceScoresDict | None = None,
        parent_type: str | None = None,
        sibling_types: list[str] | None = None,
        file_path: str | None = None,
    ) -> EnhancedClassificationResult:
        """Get detailed classification result with confidence metrics and alternatives.

        Args:
            thing_name: The tree-sitter node type name
            language: Language context
            context: Optional context information
            context_weights: Optional context weights for confidence scoring
            parent_type: Optional parent node type for context
            sibling_types: Optional sibling node types for context
            file_path: Optional file path for context

        Returns:
            Enhanced classification result with detailed metrics
        """
        return self.classifier.classify_thing(
            thing_name, language, context, context_weights, parent_type, sibling_types, file_path
        )

    def classify_batch(
        self,
        thing_names: list[tuple[ThingName, SemanticSearchLanguage | str]],
        context: str | None = None,
        context_weights: ImportanceScoresDict | None = None,
    ) -> list[EnhancedClassificationResult]:
        """Classify multiple node types efficiently.

        Args:
            thing_names: List of (thing_name, language) tuples
            context: Optional context information
            context_weights: Optional context weights for confidence scoring

        Returns:
            List of enhanced classification results
        """
        return self.classifier.classify_batch(thing_names, context, context_weights)

    def get_classification_alternatives(
        self,
        thing_name: ThingName,
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
            thing_name, language, threshold, max_alternatives
        )

    def analyze_classification_quality(
        self, thing_names: list[tuple[ThingName, SemanticSearchLanguage | str]]
    ) -> ThingClassificationReport:
        """Analyze classification quality across a set of node types.

        Args:
            thing_names: List of (thing_name, language) tuples to analyze

        Returns:
            Dictionary with quality metrics
        """
        return self.classifier.analyze_classification_quality(thing_names)

    def validate_language_coverage(
        self, language: SemanticSearchLanguage | str, sample_thing_names: list[ThingName]
    ) -> dict[str, CoverageReport]:
        """Validate classification coverage for a language.

        Args:
            language: Language to validate
            sample_thing_names: Sample thing names to test

        Returns:
            Dictionary mapping thing names to their classification details
        """
        return self.classifier.validate_language_coverage(language, sample_thing_names)


# Global instance for convenient access
_default_mapper: ThingMapper | None = None


def get_thing_mapper() -> ThingMapper:
    """Get the default global ThingMapper instance."""
    global _default_mapper
    if _default_mapper is None:
        _default_mapper = ThingMapper()
    return _default_mapper


# Convenient functions that mirror the old API but use the new system
def classify_thing(
    thing_name: ThingName, language: SemanticSearchLanguage | str, context: str | None = None
) -> SemanticClass:
    """Convenient function to classify a single thing."""
    return get_thing_mapper().classify_thing(thing_name, language, context)


def get_classification_confidence(
    thing_name: ThingName, language: SemanticSearchLanguage | str, context: str | None = None
) -> float:
    """Convenient function to get classification confidence."""
    return get_thing_mapper().get_classification_confidence(thing_name, language, context)


def classify_batch(
    thing_names: list[tuple[ThingName, SemanticSearchLanguage | str]],
    context: str | None = None,
    context_weights: ImportanceScoresDict | None = None,
) -> list[EnhancedClassificationResult]:
    """Convenient function for batch classification."""
    return get_thing_mapper().classify_batch(thing_names, context, context_weights)


def analyze_classification_quality(
    thing_names: list[tuple[ThingName, SemanticSearchLanguage | str]],
) -> ThingClassificationReport:
    """Convenient function to analyze classification quality."""
    return get_thing_mapper().analyze_classification_quality(thing_names)
