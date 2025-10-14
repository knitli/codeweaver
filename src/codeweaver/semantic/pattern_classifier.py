# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Pattern-based classification fallback for semantic nodes.

This module provides pattern-based classification as a fallback when grammar-based
classification is not available. It uses regex patterns and heuristics to infer
semantic classifications for:
- Languages without abstract type information
- Nodes without fields or structural information
- Dynamically loaded grammars (future feature)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic.dataclasses import dataclass

from codeweaver._common import DATACLASS_CONFIG, BaseEnum, DataclassSerializationMixin
from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic.classifications import ImportanceRank, SemanticClass
from codeweaver.semantic.patterns import get_compiled_patterns, match_rank_patterns_cached
from codeweaver.semantic.syntactic import SyntacticClassifier


if TYPE_CHECKING:
    from codeweaver.semantic._types import ThingName


class ClassificationPhase(BaseEnum):
    """Phases of the hierarchical classification pipeline."""

    GRAMMAR = "grammar"  # pre-defined grammar patterns inferred from tree-sitter grammars

    SYNTACTIC = "syntactic"
    TIER_MATCH = "rank_match"
    PATTERN_MATCH = "pattern_match"
    LANGUAGE_EXT = "language_extension"
    FALLBACK = "fallback"


@dataclass(frozen=True, slots=True, config=DATACLASS_CONFIG)
class ClassificationResult(DataclassSerializationMixin):
    """Result of semantic node classification."""

    classification: SemanticClass
    confidence: float
    phase: ClassificationPhase
    rank: ImportanceRank
    thing: ThingName | None = None
    matched_pattern: str | None = None
    alternative_categories: list[SemanticClass] | None = None

    @property
    def is_high_confidence(self) -> bool:
        """Check if this is a high-confidence classification."""
        return self.confidence >= 0.80

    @property
    def is_syntactic_fast_path(self) -> bool:
        """Check if this was classified via the syntactic fast-path."""
        return self.phase == ClassificationPhase.SYNTACTIC


class PatternBasedClassifier:
    """Pattern-based classification fallback for semantic nodes.

    This classifier serves as a fallback when grammar-based classification
    is not available. It uses:
    - Syntactic fast-path for punctuation and operators
    - Tier-based pattern matching
    - Regex pattern matching
    - Ultimate fallback to SYNTAX_REFERENCES
    """

    def __init__(self) -> None:
        """Initialize the pattern-based classifier with necessary components."""
        self.syntactic_classifier = SyntacticClassifier()
        self.compiled_patterns = get_compiled_patterns()

    def classify_thing(
        self, thing_name: ThingName, language: SemanticSearchLanguage, context: str | None = None
    ) -> ClassificationResult:
        """Main classification entry point using pattern-based pipeline.

        This is used as a fallback when grammar-based classification is not available.
        """
        # Phase 1: Syntactic fast-path classification
        if syntactic_result := self._classify_syntactic_phase(thing_name):
            return syntactic_result

        # Phase 2: Tier-based classification
        if rank_result := self._classify_rank_phase(thing_name, language):
            return rank_result

        # Phase 3: Pattern-based fallback
        if pattern_result := self._classify_pattern_phase(thing_name, context):
            return pattern_result

        # Phase 4: Ultimate fallback
        return self._classify_fallback_phase(thing_name)

    def _classify_syntactic_phase(self, thing_name: ThingName) -> ClassificationResult | None:
        """Phase 1: Fast syntactic classification for non-letter nodes."""
        if syntactic_result := self.syntactic_classifier.classify_syntactic(thing_name):
            return ClassificationResult(
                classification=syntactic_result.semantic_classification,
                confidence=syntactic_result.confidence,
                phase=ClassificationPhase.SYNTACTIC,
                rank=syntactic_result.rank,
                thing=syntactic_result.thing,
                matched_pattern=syntactic_result.matched_pattern,
            )
        return None

    def _classify_rank_phase(
        self, thing_name: ThingName, language: SemanticSearchLanguage
    ) -> ClassificationResult | None:
        """Phase 2: Tier-based classification using semantic patterns."""
        # Try each rank from highest to lowest priority
        for rank in ImportanceRank:
            rank_classifications = self._get_classifications_for_rank(rank)

            for classification in rank_classifications:
                if matched := match_rank_patterns_cached(thing_name, classification.name):
                    # Apply language-specific confidence adjustments
                    adjusted_confidence = self._apply_language_confidence_boost(
                        matched.confidence, classification, language, thing_name
                    )

                    return ClassificationResult(
                        classification=classification,
                        confidence=adjusted_confidence,
                        phase=ClassificationPhase.TIER_MATCH,
                        rank=rank,
                        matched_pattern=None,
                    )

        return None

    def _apply_language_confidence_boost(
        self,
        base_confidence: float,
        classification: SemanticClass,
        language: SemanticSearchLanguage,
        thing_name: str,
    ) -> float:
        """Apply language-specific confidence adjustments to improve accuracy."""
        # Language-specific node type patterns that increase confidence
        language_specific_boosts = {
            SemanticSearchLanguage.PYTHON: {
                "def": (SemanticClass.DEFINITION_CALLABLE, 0.15),
                "class": (SemanticClass.DEFINITION_TYPE, 0.15),
                "import": (SemanticClass.BOUNDARY_MODULE, 0.2),
                "lambda": (SemanticClass.EXPRESSION_ANONYMOUS, 0.1),
                "type": (SemanticClass.DEFINITION_TYPE, 0.1),
            },
            SemanticSearchLanguage.JAVASCRIPT: {
                "function": (SemanticClass.DEFINITION_CALLABLE, 0.15),
                "class": (SemanticClass.DEFINITION_TYPE, 0.15),
                "import": (SemanticClass.BOUNDARY_MODULE, 0.2),
                "arrow_function": (SemanticClass.EXPRESSION_ANONYMOUS, 0.1),
            },
            SemanticSearchLanguage.TYPESCRIPT: {
                "interface": (SemanticClass.DOCUMENTATION_STRUCTURED, 0.2),
                "type_alias": (SemanticClass.DEFINITION_TYPE, 0.15),
                "enum": (SemanticClass.DEFINITION_TYPE, 0.15),
            },
            SemanticSearchLanguage.RUST: {
                "fn": (SemanticClass.DEFINITION_CALLABLE, 0.15),
                "struct": (SemanticClass.DEFINITION_TYPE, 0.15),
                "enum": (SemanticClass.DEFINITION_TYPE, 0.15),
                "trait": (SemanticClass.DOCUMENTATION_STRUCTURED, 0.2),
                "mod": (SemanticClass.BOUNDARY_MODULE, 0.2),
            },
            SemanticSearchLanguage.GO: {
                "func": (SemanticClass.DEFINITION_CALLABLE, 0.15),
                "type": (SemanticClass.DEFINITION_TYPE, 0.15),
                "interface": (SemanticClass.DOCUMENTATION_STRUCTURED, 0.2),
                "package": (SemanticClass.BOUNDARY_MODULE, 0.2),
            },
        }

        node_lower = thing_name.lower()
        if language in language_specific_boosts:
            for pattern, (expected_classification, boost) in language_specific_boosts[
                language
            ].items():
                if pattern in node_lower and classification == expected_classification:
                    return min(0.95, base_confidence + boost)

        return base_confidence

    def _classify_pattern_phase(
        self, thing_name: str, context: str | None = None
    ) -> ClassificationResult | None:
        """Phase 3: Generic pattern matching as fallback."""
        # Try some basic heuristics
        node_lower = thing_name.lower()

        # Use context to improve classification accuracy
        context_hints = self._extract_context_hints(context) if context else {}

        # Common patterns that might not be caught by rank patterns
        if any(keyword in node_lower for keyword in ["statement", "expr", "expression"]):
            if "statement" in node_lower:
                # Context-aware statement classification
                classification = self._classify_statement_with_context(node_lower, context_hints)
                confidence = 0.40 + (0.1 if context_hints else 0.0)

                return ClassificationResult(
                    classification=classification,
                    confidence=confidence,
                    phase=ClassificationPhase.PATTERN_MATCH,
                    rank=classification.rank,
                    matched_pattern=f"statement_heuristic:{thing_name}",
                )

            # Context-aware expression classification
            classification = self._classify_expression_with_context(node_lower, context_hints)
            confidence = 0.40 + (0.1 if context_hints else 0.0)

            return ClassificationResult(
                classification=classification,
                confidence=confidence,
                phase=ClassificationPhase.PATTERN_MATCH,
                rank=classification.rank,
                matched_pattern=f"expression_heuristic:{thing_name}",
            )

        # Check for common identifier patterns
        if node_lower in {"identifier", "name", "id"}:
            return ClassificationResult(
                classification=SemanticClass.SYNTAX_IDENTIFIER,
                confidence=0.85,
                phase=ClassificationPhase.PATTERN_MATCH,
                rank=ImportanceRank.SYNTAX_REFERENCES,
                matched_pattern=f"identifier_heuristic:{thing_name}",
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
        self, _node_lower: str, context_hints: dict[str, bool]
    ) -> SemanticClass:
        """Classify statement nodes using context hints."""
        # Use context to make more informed decisions
        if context_hints.get("has_control_flow", False):
            return SemanticClass.FLOW_BRANCHING
        if context_hints.get("has_error_handling", False):
            return SemanticClass.BOUNDARY_ERROR
        if context_hints.get("has_assignment", False):
            return SemanticClass.OPERATION_DATA
        return SemanticClass.FLOW_CONTROL

    def _classify_expression_with_context(
        self, _node_lower: str, context_hints: dict[str, bool]
    ) -> SemanticClass:
        """Classify expression nodes using context hints."""
        # Use context to make more informed decisions
        if context_hints.get("has_arithmetic", False) or context_hints.get("has_comparison", False):
            return SemanticClass.OPERATION_OPERATOR
        if context_hints.get("has_assignment", False):
            return SemanticClass.OPERATION_DATA
        if context_hints.get("has_function_def", False):
            return SemanticClass.EXPRESSION_ANONYMOUS
        return SemanticClass.OPERATION_OPERATOR

    def _classify_fallback_phase(self, thing_name: str) -> ClassificationResult:
        """Phase 4: Final fallback classification."""
        # Default to most generic classification based on simple heuristics
        if any(char.isalpha() for char in thing_name):
            # Has letters, likely some form of identifier or reference
            fallback_classification = SemanticClass.SYNTAX_IDENTIFIER
        else:
            # No letters, likely punctuation
            fallback_classification = SemanticClass.SYNTAX_PUNCTUATION

        return ClassificationResult(
            classification=fallback_classification,
            confidence=0.30,  # Low confidence for fallback
            phase=ClassificationPhase.FALLBACK,
            rank=fallback_classification.rank,
            matched_pattern=f"fallback:{thing_name}",
        )

    def _get_classifications_for_rank(self, rank: ImportanceRank) -> tuple[SemanticClass, ...]:
        """Get all classifications belonging to a specific rank."""
        return rank.semantic_classifications

    def classify_batch(
        self,
        thing_names: list[tuple[ThingName, SemanticSearchLanguage]],
        context: str | None = None,
    ) -> list[ClassificationResult]:
        """Batch classification for performance."""
        return [
            self.classify_thing(thing_name, language, context)
            for thing_name, language in thing_names
        ]

    def get_classification_alternatives(
        self, thing_name: ThingName, language: SemanticSearchLanguage, threshold: float = 0.3
    ) -> list[ClassificationResult]:
        """Get alternative classifications above confidence threshold."""
        alternatives: list[ClassificationResult] = []

        # Get the primary classification
        primary = self.classify_thing(thing_name, language)
        alternatives.append(primary)

        # Try other potential classifications
        # This could be expanded to try multiple patterns/ranks
        if primary.confidence < 0.8:  # Only look for alternatives if not highly confident
            # Try each classification directly and see if any patterns match
            for classification in SemanticClass:
                if classification == primary.classification:
                    continue
                if result := match_rank_patterns_cached(thing_name, classification):
                    classification, confidence, matched, _match_obj, pattern = result

                    if matched and confidence >= threshold:
                        alternatives.append(
                            ClassificationResult(
                                classification=classification,
                                confidence=confidence,
                                phase=ClassificationPhase.PATTERN_MATCH,
                                rank=classification.rank,
                                thing=thing_name,
                                matched_pattern=pattern,
                            )
                        )

        # Sort by confidence descending
        alternatives.sort(key=lambda x: x.confidence, reverse=True)
        return alternatives


# Backward compatibility alias
HierarchicalMapper = PatternBasedClassifier

# Global instance for convenient access
_pattern_classifier = PatternBasedClassifier()
_hierarchical_mapper = _pattern_classifier  # Backward compatibility


def classify_thing_hierarchical(
    thing_name: ThingName, language: SemanticSearchLanguage, context: str | None = None
) -> ClassificationResult:
    """Convenient function for hierarchical classification.

    Note: This is a fallback classifier. Grammar-based classification is preferred.
    """
    return _pattern_classifier.classify_thing(thing_name, language, context)


def classify_batch_hierarchical(
    thing_names: list[tuple[ThingName, SemanticSearchLanguage]], context: str | None = None
) -> list[ClassificationResult]:
    """Convenient function for batch pattern-based classification.

    Note: This is a fallback classifier. Grammar-based classification is preferred.
    """
    return _pattern_classifier.classify_batch(thing_names, context)
