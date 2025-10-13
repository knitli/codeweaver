# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Semantic scoring system for AST nodes with contextual adjustments."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from ast_grep_py import SgNode
from pydantic import Field, NonNegativeFloat, NonNegativeInt

from codeweaver._common import BasedModel


if TYPE_CHECKING:
    from codeweaver.semantic._ast_grep import AstThing
    from codeweaver.semantic.classifications import ImportanceScores, SemanticClass


class SemanticScorer(BasedModel):
    """Calculates importance scores for AST nodes using semantic categories and contextual factors."""

    # Configuration for contextual adjustments
    depth_penalty_factor: Annotated[
        NonNegativeFloat,
        Field(
            default=0.04,
            ge=0.0,
            le=0.1,
            description="""Penalty per depth level (0.04 = 4% per level)""",
        ),
    ]

    size_bonus_threshold: Annotated[
        NonNegativeInt,
        Field(default=50, description="""Character count threshold for size bonus"""),
    ]

    size_bonus_factor: Annotated[
        NonNegativeFloat,
        Field(default=0.1, ge=0.0, le=0.3, description="""Bonus factor for large nodes"""),
    ]

    root_bonus: Annotated[
        NonNegativeFloat,
        Field(default=0.05, ge=0.0, le=0.2, description="""Bonus for top-level definitions"""),
    ]

    def calculate_importance_score(
        self, semantic_category: SemanticClass, node: AstThing[SgNode]
    ) -> ImportanceScores:
        """Calculate the final importance score for a node.

        Args:
            semantic_category: The semantic category of the node
            node: The AST node to score

        Returns:
            Final importance score incorporating base score and contextual adjustments
        """
        # Start with base semantic score
        base_scores = semantic_category.category.importance_scores.dump_python()
        # get contextual adjustments
        adjustment = self._apply_contextual_adjustments(node)
        adjusted_scores = {k: v + adjustment for k, v in base_scores.items()}
        corrected_scores = {k: max(0.00, min(0.99, v)) for k, v in adjusted_scores.items()}
        # Average the adjusted scores

        # Clamp to valid range
        return ImportanceScores.validate_python(corrected_scores)

    def _apply_contextual_adjustments(self, node: AstThing[SgNode]) -> float:
        """Calculates an adjustment to apply to an importance score based on context.

        Adjustments include:
        - Depth penalty: Deeper nesting reduces importance
        - Size bonus: Larger nodes get slight boost
        - Root bonus: Top-level definitions get boost
        """
        adjusted_score = 1.0

        # Calculate depth from ancestors
        depth = len(list(node.ancestors()))

        # Apply depth penalty (deeper = less important)
        adjusted_score *= 1.0 - (depth * self.depth_penalty_factor)

        # Apply size bonus for substantial nodes
        text_length = len(node.text)
        if text_length > self.size_bonus_threshold:
            size_multiplier = min(2.0, text_length / self.size_bonus_threshold)
            adjusted_score += (size_multiplier - 1.0) * self.size_bonus_factor

        # Apply root bonus for top-level definitions
        if depth <= 1 and self._is_definition_node(node):
            adjusted_score += self.root_bonus

        return adjusted_score - 1.0

    def _is_definition_node(self, node: AstThing[SgNode]) -> bool:
        """Check if a node represents a definition (class, function, etc.)."""
        # This is a heuristic based on common node kinds
        # Could be enhanced with semantic category checking once integrated
        kind = node.kind.lower()
        definition_keywords = {
            "class",
            "function",
            "method",
            "interface",
            "trait",
            "enum",
            "struct",
            "type",
            "module",
            "namespace",
        }
        return any(keyword in kind for keyword in definition_keywords)


__all__ = ("SemanticScorer",)
