# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Confidence scoring system for semantic node classification."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, cast

from codeweaver.semantic.categories import (
    AgentTask,
    ImportanceScores,
    ImportanceScoresDict,
    SemanticNodeCategory,
)
from codeweaver.semantic.hierarchical import ClassificationPhase, ClassificationResult


@dataclass(frozen=True)
class ConfidenceMetrics:
    """Detailed confidence metrics for a classification."""

    base_confidence: float
    importance_multiplier: float
    pattern_multiplier: float
    context_multiplier: float
    final_confidence: float

    @property
    def is_high_confidence(self) -> bool:
        """Check if this represents high confidence classification."""
        return self.final_confidence >= 0.80

    @property
    def is_reliable(self) -> bool:
        """Check if this classification is reliable enough for use."""
        return self.final_confidence >= 0.60


def _calculate_importance_multiplier_cached(
    category: SemanticNodeCategory, scores: ImportanceScores
) -> float:
    """Cached version of importance multiplier calculation."""
    try:
        scores = category.category.importance_scores

        # Calculate weighted importance score
        weighted_importance = (
            scores.discovery * scores.discovery
            + scores.comprehension * scores.comprehension
            + scores.modification * scores.modification
            + scores.debugging * scores.debugging
            + scores.documentation * scores.documentation
        )

        # Scale from 0.8 to 1.1 based on importance
        return 0.8 + (weighted_importance * 0.3)

    except (ValueError, AttributeError):
        return 0.8  # Default fallback


@lru_cache(maxsize=256)
def _calculate_importance_multiplier(
    category: SemanticNodeCategory, context_weights: ImportanceScores
) -> float:
    """Use ImportanceScores to adjust confidence."""
    return _calculate_importance_multiplier_cached(category, context_weights)


class ConfidenceScorer:
    """Calculate classification confidence using importance scores."""

    def __init__(self) -> None:
        """Initialize with default context weights."""
        # Default context weights for general AI assistant usage
        self.default_context = AgentTask.DEFAULT.profile

    def calculate_confidence(
        self,
        result: ClassificationResult,
        context_weights: ImportanceScoresDict | None = None,
        pattern_specificity: float | None = None,
    ) -> ConfidenceMetrics:
        """Calculate detailed confidence metrics for a classification result."""
        if context_weights is None:
            context_weights = self.default_context

        # Base confidence from classification phase
        base_confidence = self._get_base_confidence(result.phase)

        # Importance multiplier based on category's importance scores
        importance_multiplier = _calculate_importance_multiplier(
            result.category, ImportanceScores.validate_python(cast(dict[str, Any], context_weights))
        )

        # Pattern specificity multiplier
        pattern_multiplier = self._calculate_pattern_multiplier(result, pattern_specificity)

        # Context multiplier (future extension for contextual information)
        context_multiplier = 1.0  # Default, could be enhanced with AST context

        # Final confidence calculation
        final_confidence = min(
            0.99, base_confidence * importance_multiplier * pattern_multiplier * context_multiplier
        )

        return ConfidenceMetrics(
            base_confidence=base_confidence,
            importance_multiplier=importance_multiplier,
            pattern_multiplier=pattern_multiplier,
            context_multiplier=context_multiplier,
            final_confidence=final_confidence,
        )

    def _get_base_confidence(self, phase: ClassificationPhase) -> float:
        """Get base confidence based on classification phase."""
        phase_confidence_map = {
            ClassificationPhase.SYNTACTIC: 0.95,  # Syntactic fast-path
            ClassificationPhase.TIER_MATCH: 0.75,  # Tier-level match
            ClassificationPhase.PATTERN_MATCH: 0.60,  # Category pattern match
            ClassificationPhase.LANGUAGE_EXT: 0.90,  # Language extension
            ClassificationPhase.FALLBACK: 0.30,  # Unknown fallback
        }
        return phase_confidence_map.get(phase, 0.30)

    def _calculate_pattern_multiplier(
        self, result: ClassificationResult, pattern_specificity: float | None
    ) -> float:
        """Calculate pattern specificity multiplier."""
        if pattern_specificity is not None:
            # Use provided specificity
            return min(1.0, 0.7 + (pattern_specificity * 0.3))

        # Estimate specificity from matched pattern
        if not result.matched_pattern:
            return 0.85  # Default for no pattern

        pattern = result.matched_pattern

        # Longer, more specific patterns get higher multiplier
        if len(pattern) > 20:
            return 1.0
        if len(pattern) > 10:
            return 0.95
        return 0.90 if len(pattern) > 5 else 0.85

    def enhance_result_confidence(
        self,
        result: ClassificationResult,
        context_weights: ImportanceScoresDict | None = None,
        pattern_specificity: float | None = None,
    ) -> ClassificationResult:
        """Create an enhanced result with updated confidence score."""
        metrics = self.calculate_confidence(result, context_weights, pattern_specificity)

        # Create new result with enhanced confidence
        return ClassificationResult(
            category=result.category,
            confidence=metrics.final_confidence,
            phase=result.phase,
            tier=result.tier,
            matched_pattern=result.matched_pattern,
            alternative_categories=result.alternative_categories,
        )


class ContextualScorer(ConfidenceScorer):
    """Extended scorer that considers additional contextual factors."""

    def calculate_confidence_with_context(
        self,
        result: ClassificationResult,
        parent_type: str | None = None,
        sibling_types: list[str] | None = None,
        ast_depth: int | None = None,
        context_weights: ImportanceScoresDict | None = None,
    ) -> ConfidenceMetrics:
        """Calculate confidence with additional contextual factors."""
        # Get base confidence metrics
        base_metrics = self.calculate_confidence(result, context_weights)

        # Apply contextual adjustments
        context_multiplier = self._calculate_contextual_multiplier(
            result, parent_type, sibling_types, ast_depth
        )

        # Update final confidence with context
        final_confidence = min(0.99, base_metrics.final_confidence * context_multiplier)

        return ConfidenceMetrics(
            base_confidence=base_metrics.base_confidence,
            importance_multiplier=base_metrics.importance_multiplier,
            pattern_multiplier=base_metrics.pattern_multiplier,
            context_multiplier=context_multiplier,
            final_confidence=final_confidence,
        )

    def _calculate_contextual_multiplier(
        self,
        result: ClassificationResult,
        parent_type: str | None,
        sibling_types: list[str] | None,
        ast_depth: int | None,
    ) -> float:
        """Calculate multiplier based on contextual factors."""
        multiplier = 1.0

        # Parent context adjustments
        if parent_type:
            multiplier *= self._adjust_for_parent_context(result, parent_type)

        # Sibling context adjustments
        if sibling_types:
            multiplier *= self._adjust_for_sibling_context(result, sibling_types)

        # AST depth adjustments (deeper nodes might be more specific)
        if ast_depth is not None:
            if ast_depth > 5:  # Deep nesting often indicates specific constructs
                multiplier *= 1.05
            elif ast_depth < 2:  # Shallow might be more structural
                multiplier *= 1.02

        return min(1.15, multiplier)  # Cap the contextual boost

    def _adjust_for_parent_context(self, result: ClassificationResult, parent_type: str) -> float:
        """Adjust confidence based on parent node type."""
        # Example adjustments based on parent-child relationships
        if result.category == SemanticNodeCategory.OPERATION_COMPUTATION:
            if "expression" in parent_type.lower():
                return 1.1  # Operations in expressions are very likely
            if "statement" in parent_type.lower():
                return 0.95  # Less likely in statement context

        return 1.0  # No adjustment by default

    def _adjust_for_sibling_context(
        self, result: ClassificationResult, sibling_types: list[str]
    ) -> float:
        """Adjust confidence based on sibling node types."""
        # Example adjustments based on sibling patterns
        if result.category == SemanticNodeCategory.SYNTAX_SYNTACTIC:
            structural_siblings = sum(
                any(punct in s.lower() for punct in [",", ";", "(", ")", "[", "]"])
                for s in sibling_types
            )
            if structural_siblings > len(sibling_types) * 0.5:
                return 1.1  # High structural context

        return 1.0  # No adjustment by default


# Global instances
_confidence_scorer = ConfidenceScorer()
_contextual_scorer = ContextualScorer()


def calculate_classification_confidence(
    result: ClassificationResult,
    context_weights: ImportanceScoresDict | None = None,
    pattern_specificity: float | None = None,
) -> ConfidenceMetrics:
    """Convenient function for confidence calculation."""
    return _confidence_scorer.calculate_confidence(result, context_weights, pattern_specificity)


def enhance_classification_confidence(
    result: ClassificationResult,
    context_weights: ImportanceScoresDict | None = None,
    pattern_specificity: float | None = None,
) -> ClassificationResult:
    """Convenient function for enhancing result confidence."""
    return _confidence_scorer.enhance_result_confidence(
        result, context_weights, pattern_specificity
    )


def calculate_contextual_confidence(
    result: ClassificationResult,
    parent_type: str | None = None,
    sibling_types: list[str] | None = None,
    ast_depth: int | None = None,
    context_weights: ImportanceScoresDict | None = None,
) -> ConfidenceMetrics:
    """Convenient function for contextual confidence calculation."""
    return _contextual_scorer.calculate_confidence_with_context(
        result, parent_type, sibling_types, ast_depth, context_weights
    )
