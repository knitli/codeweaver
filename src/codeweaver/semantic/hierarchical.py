# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Hierarchical classification mapper for semantic nodes."""

from __future__ import annotations

from dataclasses import dataclass

from codeweaver._common import BaseEnum, DataclassSerializationMixin
from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic.categories import SemanticNodeCategory, SemanticTier
from codeweaver.semantic.patterns import get_compiled_patterns, match_tier_patterns_cached
from codeweaver.semantic.syntactic import SyntacticClassifier


class ClassificationPhase(BaseEnum):
    """Phases of the hierarchical classification pipeline."""

    SYNTACTIC = "syntactic"
    TIER_MATCH = "tier_match"
    PATTERN_MATCH = "pattern_match"
    LANGUAGE_EXT = "language_extension"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class ClassificationResult(DataclassSerializationMixin):
    """Result of semantic node classification."""

    category: SemanticNodeCategory
    confidence: float
    phase: ClassificationPhase
    tier: SemanticTier
    node: str | None = None
    matched_pattern: str | None = None
    alternative_categories: list[SemanticNodeCategory] | None = None

    @property
    def is_high_confidence(self) -> bool:
        """Check if this is a high-confidence classification."""
        return self.confidence >= 0.80

    @property
    def is_syntactic_fast_path(self) -> bool:
        """Check if this was classified via the syntactic fast-path."""
        return self.phase == ClassificationPhase.SYNTACTIC


class HierarchicalMapper:
    """Hierarchical semantic node classification system."""

    def __init__(self) -> None:
        """Initialize the hierarchical mapper with necessary components."""
        self.syntactic_classifier = SyntacticClassifier()
        self.compiled_patterns = get_compiled_patterns()

    def classify_node(
        self, node_type: str, language: SemanticSearchLanguage, context: str | None = None
    ) -> ClassificationResult:
        """Main classification entry point using hierarchical pipeline."""
        # Phase 1: Syntactic fast-path classification
        if syntactic_result := self._classify_syntactic_phase(node_type):
            return syntactic_result

        # Phase 2: Tier-based classification
        if tier_result := self._classify_tier_phase(node_type, language):
            return tier_result

        # Phase 3: Pattern-based fallback
        if pattern_result := self._classify_pattern_phase(node_type, context):
            return pattern_result

        # Phase 4: Ultimate fallback
        return self._classify_fallback_phase(node_type)

    def _classify_syntactic_phase(self, node_type: str) -> ClassificationResult | None:
        """Phase 1: Fast syntactic classification for non-letter nodes."""
        if syntactic_result := self.syntactic_classifier.classify_syntactic(node_type):
            return ClassificationResult(
                category=syntactic_result.category,
                confidence=syntactic_result.confidence,
                phase=ClassificationPhase.SYNTACTIC,
                tier=syntactic_result.tier,
                node=syntactic_result.node,
                matched_pattern=syntactic_result.matched_pattern,
            )
        return None

    def _classify_tier_phase(
        self, node_type: str, language: SemanticSearchLanguage
    ) -> ClassificationResult | None:
        """Phase 2: Tier-based classification using semantic patterns."""
        # Try each tier from highest to lowest priority
        for tier in SemanticTier:
            tier_categories = self._get_categories_for_tier(tier)

            for category in tier_categories:
                if matched := match_tier_patterns_cached(node_type, category.name):
                    # Apply language-specific confidence adjustments
                    adjusted_confidence = self._apply_language_confidence_boost(
                        matched.confidence, category, language, node_type
                    )

                    return ClassificationResult(
                        category=category,
                        confidence=adjusted_confidence,
                        phase=ClassificationPhase.TIER_MATCH,
                        tier=tier,
                        matched_pattern=None,
                    )

        return None

    def _apply_language_confidence_boost(
        self,
        base_confidence: float,
        category: SemanticNodeCategory,
        language: SemanticSearchLanguage,
        node_type: str,
    ) -> float:
        """Apply language-specific confidence adjustments to improve accuracy."""
        # Language-specific node type patterns that increase confidence
        language_specific_boosts = {
            SemanticSearchLanguage.PYTHON: {
                "def": (SemanticNodeCategory.DEFINITION_CALLABLE, 0.15),
                "class": (SemanticNodeCategory.DEFINITION_TYPE, 0.15),
                "import": (SemanticNodeCategory.BOUNDARY_MODULE, 0.2),
                "lambda": (SemanticNodeCategory.EXPRESSION_ANONYMOUS, 0.1),
                "type": (SemanticNodeCategory.DEFINITION_TYPE, 0.1),
            },
            SemanticSearchLanguage.JAVASCRIPT: {
                "function": (SemanticNodeCategory.DEFINITION_CALLABLE, 0.15),
                "class": (SemanticNodeCategory.DEFINITION_TYPE, 0.15),
                "import": (SemanticNodeCategory.BOUNDARY_MODULE, 0.2),
                "arrow_function": (SemanticNodeCategory.EXPRESSION_ANONYMOUS, 0.1),
            },
            SemanticSearchLanguage.TYPESCRIPT: {
                "interface": (SemanticNodeCategory.DOCUMENTATION_STRUCTURED, 0.2),
                "type_alias": (SemanticNodeCategory.DEFINITION_TYPE, 0.15),
                "enum": (SemanticNodeCategory.DEFINITION_TYPE, 0.15),
            },
            SemanticSearchLanguage.RUST: {
                "fn": (SemanticNodeCategory.DEFINITION_CALLABLE, 0.15),
                "struct": (SemanticNodeCategory.DEFINITION_TYPE, 0.15),
                "enum": (SemanticNodeCategory.DEFINITION_TYPE, 0.15),
                "trait": (SemanticNodeCategory.DOCUMENTATION_STRUCTURED, 0.2),
                "mod": (SemanticNodeCategory.BOUNDARY_MODULE, 0.2),
            },
            SemanticSearchLanguage.GO: {
                "func": (SemanticNodeCategory.DEFINITION_CALLABLE, 0.15),
                "type": (SemanticNodeCategory.DEFINITION_TYPE, 0.15),
                "interface": (SemanticNodeCategory.DOCUMENTATION_STRUCTURED, 0.2),
                "package": (SemanticNodeCategory.BOUNDARY_MODULE, 0.2),
            },
        }

        node_lower = node_type.lower()
        if language in language_specific_boosts:
            for pattern, (expected_category, boost) in language_specific_boosts[language].items():
                if pattern in node_lower and category == expected_category:
                    return min(0.95, base_confidence + boost)

        return base_confidence

    def _classify_pattern_phase(
        self, node_type: str, context: str | None = None
    ) -> ClassificationResult | None:
        """Phase 3: Generic pattern matching as fallback."""
        # Try some basic heuristics
        node_lower = node_type.lower()

        # Use context to improve classification accuracy
        context_hints = self._extract_context_hints(context) if context else {}

        # Common patterns that might not be caught by tier patterns
        if any(keyword in node_lower for keyword in ["statement", "expr", "expression"]):
            if "statement" in node_lower:
                # Context-aware statement classification
                category = self._classify_statement_with_context(node_lower, context_hints)
                confidence = 0.40 + (0.1 if context_hints else 0.0)

                return ClassificationResult(
                    category=category,
                    confidence=confidence,
                    phase=ClassificationPhase.PATTERN_MATCH,
                    tier=category.tier,
                    matched_pattern=f"statement_heuristic:{node_type}",
                )

            # Context-aware expression classification
            category = self._classify_expression_with_context(node_lower, context_hints)
            confidence = 0.40 + (0.1 if context_hints else 0.0)

            return ClassificationResult(
                category=category,
                confidence=confidence,
                phase=ClassificationPhase.PATTERN_MATCH,
                tier=category.tier,
                matched_pattern=f"expression_heuristic:{node_type}",
            )

        # Check for common identifier patterns
        if node_lower in {"identifier", "name", "id"}:
            return ClassificationResult(
                category=SemanticNodeCategory.REFERENCE_IDENTIFIER,
                confidence=0.85,
                phase=ClassificationPhase.PATTERN_MATCH,
                tier=SemanticTier.SYNTAX_REFERENCES,
                matched_pattern=f"identifier_heuristic:{node_type}",
            )

        return None

    def _extract_context_hints(self, context: str) -> dict[str, bool]:
        """Extract classification hints from surrounding context."""
        if not context:
            return {}

        context_lower = context.lower()
        return {
            "has_control_flow": any(
                kw in context_lower for kw in ["if", "for", "while", "switch", "case"]
            ),
            "has_error_handling": any(
                kw in context_lower for kw in ["try", "catch", "except", "throw", "raise"]
            ),
            "has_function_def": any(
                kw in context_lower for kw in ["function", "def", "fn", "func"]
            ),
            "has_class_def": any(
                kw in context_lower for kw in ["class", "struct", "interface", "trait"]
            ),
            "has_assignment": any(
                kw in context_lower for kw in ["=", "assign", "let", "var", "const"]
            ),
            "has_arithmetic": any(kw in context_lower for kw in ["+", "-", "*", "/", "%", "math"]),
            "has_comparison": any(
                kw in context_lower for kw in ["==", "!=", "<", ">", "<=", ">=", "compare"]
            ),
        }

    def _classify_statement_with_context(
        self, node_lower: str, context_hints: dict[str, bool]
    ) -> SemanticNodeCategory:
        """Classify statement nodes using context hints."""
        # Use context to make more informed decisions
        if context_hints.get("has_control_flow", False):
            return SemanticNodeCategory.FLOW_BRANCHING
        if context_hints.get("has_error_handling", False):
            return SemanticNodeCategory.BOUNDARY_ERROR
        if context_hints.get("has_assignment", False):
            return SemanticNodeCategory.OPERATION_DATA
        return SemanticNodeCategory.FLOW_CONTROL

    def _classify_expression_with_context(
        self, node_lower: str, context_hints: dict[str, bool]
    ) -> SemanticNodeCategory:
        """Classify expression nodes using context hints."""
        # Use context to make more informed decisions
        if context_hints.get("has_arithmetic", False) or context_hints.get("has_comparison", False):
            return SemanticNodeCategory.OPERATION_COMPUTATION
        if context_hints.get("has_assignment", False):
            return SemanticNodeCategory.OPERATION_DATA
        if context_hints.get("has_function_def", False):
            return SemanticNodeCategory.EXPRESSION_ANONYMOUS
        return SemanticNodeCategory.OPERATION_COMPUTATION

    def _classify_fallback_phase(self, node_type: str) -> ClassificationResult:
        """Phase 4: Final fallback classification."""
        # Default to most generic category based on simple heuristics
        if any(char.isalpha() for char in node_type):
            # Has letters, likely some form of identifier or reference
            fallback_category = SemanticNodeCategory.REFERENCE_IDENTIFIER
        else:
            # No letters, likely punctuation
            fallback_category = SemanticNodeCategory.SYNTAX_STRUCTURAL

        return ClassificationResult(
            category=fallback_category,
            confidence=0.30,  # Low confidence for fallback
            phase=ClassificationPhase.FALLBACK,
            tier=fallback_category.tier,
            matched_pattern=f"fallback:{node_type}",
        )

    def _get_categories_for_tier(self, tier: SemanticTier) -> tuple[SemanticNodeCategory, ...]:
        """Get all categories belonging to a specific tier."""
        return tier.semantic_categories

    def classify_batch(
        self, node_types: list[tuple[str, SemanticSearchLanguage]], context: str | None = None
    ) -> list[ClassificationResult]:
        """Batch classification for performance."""
        return [
            self.classify_node(node_type, language, context) for node_type, language in node_types
        ]

    def get_classification_alternatives(
        self, node_type: str, language: SemanticSearchLanguage, threshold: float = 0.3
    ) -> list[ClassificationResult]:
        """Get alternative classifications above confidence threshold."""
        alternatives: list[ClassificationResult] = []

        # Get the primary classification
        primary = self.classify_node(node_type, language)
        alternatives.append(primary)

        # Try other potential classifications
        # This could be expanded to try multiple patterns/tiers
        if primary.confidence < 0.8:  # Only look for alternatives if not highly confident
            # Try each category directly and see if any patterns match
            for category in SemanticNodeCategory:
                if category == primary.category:
                    continue
                if result := match_tier_patterns_cached(node_type, category):
                    category, confidence, matched, _match_obj, pattern = result

                    if matched and confidence >= threshold:
                        alternatives.append(
                            ClassificationResult(
                                category=category,
                                confidence=confidence,
                                phase=ClassificationPhase.PATTERN_MATCH,
                                tier=category.tier,
                                node=node_type,
                                matched_pattern=pattern,
                            )
                        )

        # Sort by confidence descending
        alternatives.sort(key=lambda x: x.confidence, reverse=True)
        return alternatives


# Global instance for convenient access
_hierarchical_mapper = HierarchicalMapper()


def classify_node_hierarchical(
    node_type: str, language: SemanticSearchLanguage, context: str | None = None
) -> ClassificationResult:
    """Convenient function for hierarchical classification."""
    return _hierarchical_mapper.classify_node(node_type, language, context)


def classify_batch_hierarchical(
    node_types: list[tuple[str, SemanticSearchLanguage]], context: str | None = None
) -> list[ClassificationResult]:
    """Convenient function for batch hierarchical classification."""
    return _hierarchical_mapper.classify_batch(node_types, context)
