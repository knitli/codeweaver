# sourcery skip: no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unified semantic node classification system."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Literal, TypedDict, cast

from pydantic import NonNegativeFloat, computed_field

from codeweaver._common import DataclassSerializationMixin
from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic.categories import (
    CategoryRegistry,
    ImportanceScoresDict,
    SemanticNodeCategory,
    SemanticTier,
    create_default_registry,
)
from codeweaver.semantic.confidence import ConfidenceMetrics, ConfidenceScorer, ContextualScorer
from codeweaver.semantic.extensions import ContextualExtensionManager, LanguageExtensionManager
from codeweaver.semantic.grammar_classifier import GrammarBasedClassifier
from codeweaver.semantic.pattern_classifier import (
    ClassificationPhase,
    ClassificationResult,
    PatternBasedClassifier,
)


@dataclass(frozen=True)
class EnhancedClassificationResult(DataclassSerializationMixin):
    """Enhanced result with full classification details."""

    category: SemanticNodeCategory
    confidence: float
    phase: ClassificationPhase
    tier: SemanticTier
    matched_pattern: str | None = None
    alternative_categories: list[SemanticNodeCategory] | None = None
    confidence_metrics: ConfidenceMetrics | None = None
    extension_source: str | None = None

    @property
    def is_high_confidence(self) -> bool:
        """Check if this is a high-confidence classification."""
        return self.confidence >= 0.80

    @property
    def is_syntactic_fast_path(self) -> bool:
        """Check if this was classified via the syntactic fast-path."""
        return self.phase == ClassificationPhase.SYNTACTIC

    @property
    def is_language_specific(self) -> bool:
        """Check if this used language-specific classification."""
        return self.phase == ClassificationPhase.LANGUAGE_EXT

    @computed_field
    @cached_property
    def confidence_grade(self) -> Literal["A", "B", "C", "D", "F"]:
        """Get a letter grade for confidence level."""
        if self.confidence >= 0.90:
            return "A"
        if self.confidence >= 0.80:
            return "B"
        if self.confidence >= 0.70:
            return "C"
        return "D" if self.confidence >= 0.60 else "F"


class CoverageReport(TypedDict):
    """Report on classification coverage for a language."""

    category: SemanticNodeCategory
    confidence: NonNegativeFloat
    phase: ClassificationPhase
    grade: Literal["A", "B", "C", "D", "F"]


class NodeClassificationReport(TypedDict):
    """Report on classification quality metrics."""

    total_classifications: int
    high_confidence_percentage: NonNegativeFloat
    syntactic_fast_path_percentage: NonNegativeFloat
    language_specific_percentage: NonNegativeFloat
    average_confidence: NonNegativeFloat
    phase_distribution: dict[ClassificationPhase, NonNegativeFloat]


class SemanticNodeClassifier:
    """Unified semantic node classification system."""

    def __init__(
        self,
        registry: CategoryRegistry | None = None,
        *,
        enable_contextual_extensions: bool = True,
        enable_confidence_scoring: bool = True,
    ) -> None:
        """Initialize the semantic node classifier."""
        self.registry = registry or create_default_registry()

        # Core classification components
        self.grammar_classifier = GrammarBasedClassifier()  # NEW: Grammar-first
        self.pattern_fallback = PatternBasedClassifier()  # Pattern-based fallback

        # Extension management
        if enable_contextual_extensions:
            self.extension_manager = ContextualExtensionManager(self.registry)
        else:
            self.extension_manager = LanguageExtensionManager(self.registry)

        # Confidence scoring
        self.enable_confidence_scoring = enable_confidence_scoring
        if enable_confidence_scoring:
            self.confidence_scorer = ConfidenceScorer()
            self.contextual_scorer = ContextualScorer()

    def classify_node(
        self,
        node_type: str,
        language: SemanticSearchLanguage | str,
        context: str | None = None,
        context_weights: ImportanceScoresDict | None = None,
        parent_type: str | None = None,
        sibling_types: list[str] | None = None,
        file_path: str | None = None,
    ) -> EnhancedClassificationResult:
        """Main classification entry point."""
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)

        # Phase 1: Check language-specific extensions first
        if (
            ext_result := self.extension_manager.classify_with_context(  # type: ignore
                node_type, language, parent_type, sibling_types, file_path
            )
            if hasattr(self.extension_manager, "classify_with_context")
            else self.extension_manager.check_extensions_first(node_type, language)
        ):
            return self._enhance_result_with_confidence(
                cast(ClassificationResult, ext_result),
                context_weights,
                parent_type,
                sibling_types,
                file_path,
                "language_extension",
            )

        # Phase 2: Grammar-based classification (NEW - primary path)
        if grammar_result := self.grammar_classifier.classify_node(node_type, language):
            # Convert GrammarClassificationResult to ClassificationResult
            base_result = ClassificationResult(
                category=grammar_result.category,
                tier=grammar_result.tier,
                confidence=grammar_result.confidence,
                phase=ClassificationPhase.GRAMMAR,
                matched_pattern=f"grammar_{grammar_result.classification_method}",
                alternative_categories=None,
            )

            # Apply language-specific refinements
            refined_result = self.extension_manager.refine_classification(
                base_result, language, context
            )

            return self._enhance_result_with_confidence(
                refined_result, context_weights, parent_type, sibling_types, file_path, "grammar"
            )

        # Phase 3: Pattern-based classification (fallback)
        base_result = self.pattern_fallback.classify_node(node_type, language, context)

        # Phase 4: Apply language-specific refinements
        refined_result = self.extension_manager.refine_classification(
            base_result, language, context
        )

        return self._enhance_result_with_confidence(
            refined_result, context_weights, parent_type, sibling_types, file_path, "hierarchical"
        )

    def classify_batch(
        self,
        node_types: list[tuple[str, SemanticSearchLanguage | str]],
        context: str | None = None,
        context_weights: ImportanceScoresDict | None = None,
    ) -> list[EnhancedClassificationResult]:
        """Batch classification for performance."""
        return [
            self.classify_node(
                node_type,
                language
                if isinstance(language, SemanticSearchLanguage)
                else SemanticSearchLanguage.from_string(language),
                context,
                context_weights,
            )
            for node_type, language in node_types
        ]

    def get_classification_alternatives(
        self,
        node_type: str,
        language: SemanticSearchLanguage | str,
        threshold: float = 0.3,
        max_alternatives: int = 5,
    ) -> list[EnhancedClassificationResult]:
        """Get alternative classifications above confidence threshold."""
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)

        # Get primary classification
        primary = self.classify_node(node_type, language)
        alternatives = [primary]
        # Get alternatives from pattern-based classifier
        if hasattr(self.pattern_fallback, "get_classification_alternatives"):
            pattern_alternatives = self.pattern_fallback.get_classification_alternatives(
                node_type, language, threshold
            )

            for alt in pattern_alternatives:
                if alt.category != primary.category and alt.confidence >= threshold:
                    enhanced_alt = self._enhance_result_with_confidence(
                        alt, None, None, None, None, "alternative"
                    )
                    alternatives.append(enhanced_alt)

        # Sort by confidence and limit results
        alternatives.sort(key=lambda x: x.confidence, reverse=True)
        return alternatives[:max_alternatives]

    def _enhance_result_with_confidence(
        self,
        result: ClassificationResult,
        context_weights: ImportanceScoresDict | None,
        parent_type: str | None,
        sibling_types: list[str] | None,
        file_path: str | None,
        extension_source: str,
    ) -> EnhancedClassificationResult:
        """Enhance classification result with confidence metrics."""
        confidence_metrics = None
        final_confidence = result.confidence

        if self.enable_confidence_scoring:
            # Use contextual scorer if we have context information
            if parent_type or sibling_types or file_path:
                confidence_metrics = self.contextual_scorer.calculate_confidence_with_context(
                    result,
                    parent_type,
                    sibling_types,
                    None,  # ast_depth - could be added later
                    context_weights,
                )
            else:
                confidence_metrics = self.confidence_scorer.calculate_confidence(
                    result, context_weights
                )

            final_confidence = confidence_metrics.final_confidence

        return EnhancedClassificationResult(
            category=result.category,
            confidence=final_confidence,
            phase=result.phase,
            tier=result.category.tier,
            matched_pattern=result.matched_pattern,
            alternative_categories=result.alternative_categories,
            confidence_metrics=confidence_metrics,
            extension_source=extension_source,
        )

    def analyze_classification_quality(
        self, node_types: list[tuple[str, SemanticSearchLanguage | str]]
    ) -> NodeClassificationReport:
        """Analyze classification quality across a set of node types."""
        results = self.classify_batch(node_types)

        # Calculate quality metrics
        total_results = len(results)
        high_confidence = sum(bool(r.is_high_confidence) for r in results)
        syntactic_fast_path = sum(bool(r.is_syntactic_fast_path) for r in results)
        language_specific = sum(bool(r.is_language_specific) for r in results)

        avg_confidence = (
            sum(r.confidence for r in results) / total_results if total_results > 0 else 0
        )

        # Phase distribution
        phase_counts = Counter(result.phase for result in results)

        return NodeClassificationReport(
            total_classifications=total_results,
            high_confidence_percentage=(high_confidence / total_results) * 100
            if total_results > 0
            else 0,
            syntactic_fast_path_percentage=(syntactic_fast_path / total_results) * 100
            if total_results > 0
            else 0,
            language_specific_percentage=(language_specific / total_results) * 100
            if total_results > 0
            else 0,
            average_confidence=avg_confidence,
            phase_distribution={
                phase: (count / total_results) * 100 for phase, count in phase_counts.items()
            },
        )

    def get_supported_languages(self) -> list[SemanticSearchLanguage]:
        """Get list of languages with specific extension support."""
        supported: list[SemanticSearchLanguage] = []

        supported.extend(
            language
            for language in SemanticSearchLanguage
            if self.extension_manager.get_available_extensions(language)
        )
        return supported

    def validate_language_coverage(
        self, language: SemanticSearchLanguage | str, sample_node_types: list[str]
    ) -> dict[str, CoverageReport]:
        """Validate classification coverage for a language."""
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)

        coverage: dict[str, CoverageReport] = {}
        for node_type in sample_node_types:
            result = self.classify_node(node_type, language)
            coverage[node_type] = CoverageReport(
                category=result.category,
                confidence=result.confidence,
                phase=result.phase,
                grade=result.confidence_grade,
            )

        return coverage


class BatchClassifier(SemanticNodeClassifier):
    """Optimized classifier for large-scale batch operations."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize batch classifier with caching."""
        super().__init__(*args, **kwargs)
        self._classification_cache: dict[
            tuple[str, str, str | None], EnhancedClassificationResult
        ] = {}

    def classify_batch_optimized(
        self,
        node_types: list[tuple[str, SemanticSearchLanguage | str]],
        *,
        use_cache: bool = True,
        context: str | None = None,
        context_weights: ImportanceScoresDict | None = None,
    ) -> list[EnhancedClassificationResult]:
        """Optimized batch classification with caching."""
        results: list[EnhancedClassificationResult] = []

        for node_type, language in node_types:
            if not isinstance(language, SemanticSearchLanguage):
                language = SemanticSearchLanguage.from_string(language)

            cache_key = (node_type, language.name, context) if use_cache else None

            if cache_key and cache_key in self._classification_cache:
                results.append(self._classification_cache[cache_key])
            else:
                result = self.classify_node(node_type, language, context, context_weights)
                results.append(result)

                if cache_key:
                    self._classification_cache[cache_key] = result

        return results

    def clear_cache(self) -> None:
        """Clear the classification cache."""
        self._classification_cache.clear()

    def get_cache_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._classification_cache),
            "cache_hits": getattr(self, "_cache_hits", 0),
            "cache_misses": getattr(self, "_cache_misses", 0),
        }


# Global instances for convenient access
_default_classifier = SemanticNodeClassifier()
_batch_classifier = BatchClassifier()


def classify_semantic_node(
    node_type: str,
    language: SemanticSearchLanguage | str,
    context: str | None = None,
    context_weights: ImportanceScoresDict | None = None,
) -> EnhancedClassificationResult:
    """Convenient function for semantic node classification."""
    return _default_classifier.classify_node(node_type, language, context, context_weights)


def classify_nodes_batch(
    node_types: list[tuple[str, SemanticSearchLanguage | str]],
    context: str | None = None,
    context_weights: ImportanceScoresDict | None = None,
    *,
    use_cache: bool = True,
) -> list[EnhancedClassificationResult]:
    """Convenient function for batch semantic node classification."""
    return _batch_classifier.classify_batch_optimized(
        node_types, use_cache=use_cache, context=context, context_weights=context_weights
    )


def get_classification_alternatives(
    node_type: str, language: SemanticSearchLanguage | str, threshold: float = 0.3
) -> list[EnhancedClassificationResult]:
    """Get alternative classifications for a node type."""
    return _default_classifier.get_classification_alternatives(node_type, language, threshold)


def analyze_classification_quality(
    node_types: list[tuple[str, SemanticSearchLanguage | str]],
) -> NodeClassificationReport:
    """Analyze classification quality metrics."""
    return _default_classifier.analyze_classification_quality(node_types)


def validate_language_coverage(
    language: SemanticSearchLanguage | str, sample_node_types: list[str]
) -> dict[str, CoverageReport]:
    """Validate classification coverage for a language."""
    return _default_classifier.validate_language_coverage(language, sample_node_types)


def get_default_classifier() -> SemanticNodeClassifier:
    """Get the default classifier instance."""
    return _default_classifier


def get_batch_classifier() -> BatchClassifier:
    """Get the batch classifier instance."""
    return _batch_classifier
