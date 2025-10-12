# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Syntactic classification for semantic nodes."""

from __future__ import annotations

import re

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from codeweaver.semantic.categories import ImportanceRank, SemanticClass
from codeweaver.semantic.patterns import match_tier_patterns_cached


class SyntacticClassification(Enum):
    """Types of syntactic classification results."""

    DEFINITE_OPERATOR = "definite_operator"
    DEFINITE_PUNCTUATION = "definite_punctuation"
    HYBRID_CONTEXT_DEPENDENT = "hybrid_context_dependent"
    UNKNOWN_NON_LETTER = "unknown_non_letter"


@dataclass(frozen=True)
class SyntacticResult:
    """Result of syntactic node classification."""

    classification: SyntacticClassification
    category: SemanticClass
    confidence: float
    tier: ImportanceRank
    node: str | None = None
    matched_pattern: str | None = None

    @property
    def is_definitive(self) -> bool:
        """Check if this is a high-confidence definitive classification."""
        return self.confidence >= 0.85


class SyntacticClassifier:
    """Fast-path classification for non-letter node types."""

    _alpha_pattern: ClassVar[re.Pattern[str]] = re.compile(r"[a-z]", re.IGNORECASE)

    def classify_syntactic(self, node_type: str) -> SyntacticResult | None:
        """Classify node types with no letters using pre-compiled patterns."""
        # Use the cached utility function
        if self.is_syntactic_node(node_type):
            tier = ImportanceRank.SYNTAX_REFERENCES
            if result := match_tier_patterns_cached(node_type, tier, only_syntactic=True):
                category, confidence, text, _match_obj, _matched_pattern = result

                # Determine classification type based on confidence and category
                if confidence >= 0.90:
                    if category == SemanticClass.OPERATION_OPERATOR:
                        classification = SyntacticClassification.DEFINITE_OPERATOR
                    else:
                        classification = SyntacticClassification.DEFINITE_PUNCTUATION
                elif confidence >= 0.60:
                    classification = SyntacticClassification.HYBRID_CONTEXT_DEPENDENT
                else:
                    classification = SyntacticClassification.UNKNOWN_NON_LETTER

                return SyntacticResult(
                    classification=classification,
                    category=category,
                    confidence=confidence,
                    tier=category.tier,
                    matched_pattern=text,
                )
        return None

    def is_syntactic_node(self, node_type: str) -> bool:
        """Quick check if a node type is a syntax element (non-letter). For non-authoritative,fast-path filtering.

        Note: This only checks for the presence of letters. There *are* syntactic node types that contain letters (e.g. 'EOF' or 'bracket' -- not all grammars use the characters to represent the node and instead use plain names). **If it returns True, you can have high confidence it's either syntactic or an operator. If it returns False, it may still be syntactic.**
        """
        return not type(self)._alpha_pattern.search(node_type)


class ContextualClassifier:
    """Enhanced classifier that considers node context for disambiguation."""

    def __init__(self, syntactic_classifier: SyntacticClassifier | None = None) -> None:
        """Initialize with an optional syntactic classifier instance."""
        self.syntactic_classifier = syntactic_classifier or SyntacticClassifier()

    def classify_with_context(
        self, node_type: str, parent_type: str | None = None, sibling_types: list[str] | None = None
    ) -> SyntacticResult | None:
        """Classify using additional AST context when available."""
        base_result = self.syntactic_classifier.classify_syntactic(node_type)

        if (
            not base_result
            or base_result.classification != SyntacticClassification.HYBRID_CONTEXT_DEPENDENT
        ):
            return base_result

        # Apply context-specific refinements
        if parent_type and sibling_types:
            return self._refine_with_context(base_result, parent_type, sibling_types)

        return base_result

    def _refine_with_context(
        self, base_result: SyntacticResult, parent_type: str, sibling_types: list[str]
    ) -> SyntacticResult:
        """Refine classification using AST context."""
        # Example: '<' in comparison context vs generic context
        if base_result.matched_pattern == "<" and any(
            "comparison" in sibling or "expression" in sibling for sibling in sibling_types
        ):
            return SyntacticResult(
                classification=SyntacticClassification.DEFINITE_OPERATOR,
                category=SemanticClass.OPERATION_OPERATOR,
                confidence=0.85,  # Higher confidence with context
                tier=SemanticClass.OPERATION_OPERATOR.tier,
                matched_pattern=base_result.matched_pattern,
            )

        # Example: ':' in object literal context vs operator context
        if base_result.matched_pattern == ":" and any(
            "object" in sibling or "property" in sibling for sibling in sibling_types
        ):
            return SyntacticResult(
                classification=SyntacticClassification.DEFINITE_PUNCTUATION,
                category=SemanticClass.SYNTAX_PUNCTUATION,
                confidence=0.90,
                tier=SemanticClass.SYNTAX_PUNCTUATION.tier,
                matched_pattern=base_result.matched_pattern,
            )

        return base_result


# Global instances for convenient access
_syntactic_classifier = SyntacticClassifier()
_contextual_classifier = ContextualClassifier(_syntactic_classifier)


def classify_syntactic_node(node_type: str) -> SyntacticResult | None:
    """Convenient function for syntactic classification."""
    return _syntactic_classifier.classify_syntactic(node_type)


def classify_with_context(
    node_type: str, parent_type: str | None = None, sibling_types: list[str] | None = None
) -> SyntacticResult | None:
    """Convenient function for contextual classification."""
    return _contextual_classifier.classify_with_context(node_type, parent_type, sibling_types)


def is_syntactic_node(node_type: str) -> bool:
    """Check if a node type is syntactic (contains no letters)."""
    return _syntactic_classifier.is_syntactic_node(node_type)
