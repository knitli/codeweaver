# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Semantic scoring system for AST nodes with contextual adjustments."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from ast_grep_py import SgNode
from pydantic import Field, NonNegativeFloat, NonNegativeInt

from codeweaver._types import BasedModel


if TYPE_CHECKING:
    from codeweaver.semantic.ast_grep import AstThing
    from codeweaver.semantic.classifications import ImportanceScores


class SemanticScorer(BasedModel):
    """Calculates importance scores for AST nodes using semantic categories and contextual factors."""

    # Configuration for contextual adjustments
    depth_penalty_factor: Annotated[
        NonNegativeFloat,
        Field(ge=0.0, le=0.1, description="""Penalty per depth level (0.04 = 4% per level)"""),
    ] = 0.04

    size_bonus_threshold: Annotated[
        NonNegativeInt, Field(description="""Character count threshold for size bonus""")
    ] = 50

    size_bonus_factor: Annotated[
        NonNegativeFloat, Field(ge=0.0, le=0.3, description="""Bonus factor for large nodes""")
    ] = 0.1

    file_thing_bonus: Annotated[
        NonNegativeFloat, Field(ge=0.0, le=0.2, description="""Bonus for top-level definitions""")
    ] = 0.05

    def calculate_importance_score(self, thing: AstThing[SgNode]) -> ImportanceScores:
        """Calculate the final importance score for a thing.

        Args:
            semantic_category: The semantic category of the thing
            thing: The AST thing to score

        Returns:
            Final importance score incorporating base score and contextual adjustments
        """
        # Start with base semantic score
        base_scores = (
            thing.classification.importance_scores
            if thing.classification
            else ImportanceScores.default()
        ).dump_python()
        # get contextual adjustments
        adjustment = self._apply_contextual_adjustments(thing)
        adjusted_scores = {k: v + adjustment for k, v in base_scores.items()}
        corrected_scores = {k: max(0.00, min(0.99, v)) for k, v in adjusted_scores.items()}
        # Average the adjusted scores

        # Clamp to valid range
        return ImportanceScores.validate_python(corrected_scores)

    def _apply_contextual_adjustments(self, thing: AstThing[SgNode]) -> float:
        """Calculates an adjustment to apply to an importance score based on context.

        Adjustments include:
        - Depth penalty: Deeper nesting reduces importance
        - Size bonus: Larger things get slight boost
        - Root bonus: Top-level definitions get boost
        """
        adjusted_score = 1.0

        # Calculate depth from ancestors
        depth = len(list(thing.ancestors()))

        # Apply depth penalty (deeper = less important)
        adjusted_score *= 1.0 - (depth * self.depth_penalty_factor)

        # Apply size bonus for substantial things
        text_length = len(thing.text)
        if text_length > self.size_bonus_threshold:
            size_multiplier = min(2.0, text_length / self.size_bonus_threshold)
            adjusted_score += (size_multiplier - 1.0) * self.size_bonus_factor

        # Apply root bonus for top-level definitions
        if depth <= 1 and thing.is_composite and thing.is_file_thing:
            adjusted_score += self.file_thing_bonus

        return adjusted_score - 1.0


__all__ = ("SemanticScorer",)
