# sourcery skip: lambdas-should-be-short
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Grammar-based semantic node classification using inherent tree-sitter structure.

This module provides primary classification by leveraging the explicit semantic
relationships encoded in node_types.json files:
- Categories → Abstract groupings (was: Subtypes/Abstract types)
- DirectConnections → Structural relationships with semantic Roles (was: Fields)
- PositionalConnections → Ordered relationships without Roles (was: Children)
- can_be_anywhere → Syntactic elements that can appear anywhere (was: Extra)
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Annotated, NamedTuple, cast

from ast_grep_py import SgNode
from pydantic import Field, NonNegativeFloat, NonNegativeInt, computed_field

from codeweaver._common import BaseEnum
from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic.classifications import ImportanceRank, SemanticClass


if TYPE_CHECKING:
    from codeweaver.semantic._ast_grep import AstThing
    from codeweaver.semantic.node_type_parser import (
        CategoryName,
        CompositeThing,
        NodeTypeParser,
        ThingName,
        Token,
    )


CONFIDENCE_THRESHOLD = 0.85


class ClassificationMethod(BaseEnum):
    """Enumeration of classification methods."""

    CATEGORY = "category"
    CONNECTION_INFERENCE = "connection_inference"
    POSITIONAL = "positional"
    TOKEN_PURPOSE = "token_purpose"  # noqa: S105  # definitely not a password
    ANYWHERE = "anywhere"
    SPECIFIC_THING = "specific_thing"


class EvidenceKind(int, BaseEnum):
    """Kinds of evidence used for classifying Things.

    An int-enum for easy comparison of evidence strength. Higher numbers indicate stronger evidence. The confidence score is estimated based on the combined strength of the evidence kinds used.
    """

    HEURISTIC = 10
    """Evidence based on a heuristic rule or pattern, e.g. that a Thing has both direct and positional connections."""
    SIMPLE_NAME_PATTERN = 20
    """Evidence based on a pattern in the Thing's name, e.g. that it contains 'comment'."""
    LANGUAGE = 30
    """Evidence based on the programming language context, e.g. that a specific thing is only in one language, or that the language has rules that make certain things more likely."""
    CONNECTIONS = 65
    """Evidence based on the CompositeThing's connections."""
    CATEGORIES = 80
    """Evidence based on the grammar categories the Thing belongs to."""
    ROLES = 85
    """Evidence based on the semantic roles of the Thing's connections."""
    SPECIFIC_THING = 90
    """Evidence based on a specific instance of a Thing. This is based on empirical knowledge of specific Things in specific languages."""
    PURPOSE = 95
    """Evidence based on a Token's purpose classification. CodeWeaver's token purpose classification is very robust and high-confidence, so this is a strong form of evidence."""

    @classmethod
    def confidence(cls, kinds: Sequence[EvidenceKind], adjustment: NonNegativeInt = 0) -> float:
        """Estimate confidence score based on the kinds of evidence used.

        Args:
            kinds: List of EvidenceKind values used in classification.

        Returns:
            Confidence score from 0.0 to 1.0
        """
        if not kinds and not adjustment:
            return 0.0
        if not kinds and adjustment:
            return min(max(adjustment / 100.0, 0.0), 1.0)
        # We get total adjusted strength by summing the evidence kinds and adding any adjustment
        # Note: This can exceed 100, so we clamp the final confidence to 1.0
        total_strength = sum(kinds) + adjustment
        return min(max(total_strength / 100.0, 0.0), 1.0)

    @property
    def statement(self) -> str:
        """Human-readable statement of the evidence kind."""
        return {
            EvidenceKind.HEURISTIC: "Matched a heuristic rule or pattern",
            EvidenceKind.SIMPLE_NAME_PATTERN: "Inferred from the Thing's name",
            EvidenceKind.LANGUAGE: "Inferred from the programming language context",
            EvidenceKind.CONNECTIONS: "Inferred from the Thing's connections",
            EvidenceKind.ROLES: "Inferred from the semantic roles of the Thing's connections",
            EvidenceKind.CATEGORIES: "Inferred from the grammar categories the Thing belongs to",
            EvidenceKind.SPECIFIC_THING: "Based on empirical knowledge of this specific Thing",
            EvidenceKind.PURPOSE: "Based on the Token's purpose classification",
        }[self]

    @classmethod
    def evidence_summary(cls, kinds: Sequence[EvidenceKind]) -> str:
        """Generate a human-readable summary of the evidence kinds used.

        Args:
            kinds: List of EvidenceKind values used in classification.

        Returns:
            Human-readable summary of the evidence kinds.
        """
        if not kinds:
            return "No evidence available for classification."

        summaries = (
            f"- {kind.as_title}: {kind.statement} ({kind.value})"
            for kind in sorted(kinds, reverse=True)
        )
        return "\n".join(summaries)


class GrammarClassificationResult(NamedTuple):
    """Result of grammar-based classification.

    Attributes:
        classification: Semantic classification assigned to the thing
        rank: Semantic rank (importance level)
        classification_method: Method used for classification
        evidence: Kinds of evidence used for classification
        evidence_summary: Human-readable explanation of classification reasoning
        confidence: Confidence score (0.0-1.0)
    """

    classification: Annotated[
        SemanticClass, Field(description="Semantic classification assigned to the node")
    ]
    rank: Annotated[
        ImportanceRank,
        Field(
            description="Importance rank (1-5), lower is more important",
            default_factory=lambda data: ImportanceRank.from_classification(data["classification"]),
        ),
    ]
    classification_method: ClassificationMethod
    evidence: Annotated[
        tuple[EvidenceKind, ...],
        Field(description="Kinds of evidence used for classification", default_factory=tuple),
    ]
    adjustment: Annotated[
        int, Field(description="Manual adjustment to confidence. Any integer.")
    ] = 0

    alternate_classifications: (
        Annotated[
            dict[SemanticClass, tuple[EvidenceKind, ...]],
            Field(
                description="Alternate classifications for the node. Only used when there are multiple classifications and none above the confidence threshold."
            ),
        ]
        | None
    ) = None

    assessment_comment: Annotated[
        str | None,
        Field(
            description="Optional human-readable comment regarding the classification assessment."
        ),
    ] = None

    differentiator: Annotated[
        Callable[[AstThing[SgNode]], SemanticClass | None] | None,
        Field(
            description="Optional function to differentiate between alternate classifications based on AST node context. The function receives an AstThing and returns a SemanticClass or None."
        ),
    ] = None

    @computed_field(
        description="Confidence score (0.0-1.0) computed from evidence kinds and adjustment",
        repr=True,
    )
    @property
    def confidence(self) -> NonNegativeFloat:
        """Confidence score (0.0-1.0) computed from evidence kinds."""
        return EvidenceKind.confidence(self.evidence, self.adjustment or 0)

    @computed_field(description="Human-readable summary of the evidence kinds used", repr=False)
    def evidence_summary(self) -> str:
        """Human-readable summary of the evidence kinds used."""
        return EvidenceKind.evidence_summary(self.evidence)

    @staticmethod
    def _adjust_for_disparity(
        results: Sequence[GrammarClassificationResult],
        confident_result: GrammarClassificationResult,
    ) -> int:
        """Adjust confidence based on rank discrepancy.

        Args:
            results: List of GrammarClassificationResult instances to analyze.
            confident_result: The result with the highest confidence.

        Returns:
            Adjustment value to be added to confidence calculation.
        """
        if not results:
            return 0
        if all(result.rank == confident_result.rank for result in results):
            return 10  # all the same rank, boost confidence
        # more granular comparison using classification simple_rank
        discrepancy = int(
            sum(
                abs(result.classification.simple_rank - confident_result.classification.simple_rank)
                for result in results
            )
            / len(results)
        )
        if discrepancy >= 5:
            return -(
                5 * discrepancy - 5 if discrepancy > 5 else 5
            )  # large discrepancy, reduce confidence proportionally
        return 0

    @classmethod
    def from_results(
        cls, results: Sequence[GrammarClassificationResult]
    ) -> GrammarClassificationResult | None:
        """Combine multiple classification results into a single result.

        Args:
            results: List of GrammarClassificationResult instances to combine.

        Returns:
            Combined GrammarClassificationResult with highest confidence, or None if no results.
        """
        if not results:
            return None
        # Choose the result with the highest confidence
        max_confidence_result = max(results, key=lambda r: r.confidence)
        if any(
            result.classification
            for result in results
            if result.classification == max_confidence_result.classification
            and result != max_confidence_result
        ):
            results = [
                result
                for result in results
                if result.classification == max_confidence_result.classification
            ]
            evidence: tuple[EvidenceKind, ...] = tuple({
                evidence
                for result in results
                for evidence in result.evidence
                if result.classification == max_confidence_result.classification
            })
            adjustment = 0
            # we adjust confidence based on the disparity of classification simple_ranks -- wide disparity means less confidence
            # we first compare true ranks, then the classification's simple_rank (a 1 to n for each classification)
            adjustment += cls._adjust_for_disparity(results, max_confidence_result)
            return max_confidence_result._replace(
                evidence=evidence,
                adjustment=adjustment,
                alternate_classifications={
                    result.classification: result.evidence
                    for result in results
                    if result.classification != max_confidence_result.classification
                },
            )
        if len([result for result in results if result != max_confidence_result]) > 1:
            # we adjust confidence based on the disparity of classification simple_ranks -- wide disparity means less confidence
            # we first compare true ranks, then the classification's simple_rank (a 1 to n for each classification)
            adjustment = cls._adjust_for_disparity(results, max_confidence_result)
            results = [result for result in results if result != max_confidence_result]
            return max_confidence_result._replace(
                adjustment=adjustment,
                alternate_classifications={
                    result.classification: result.evidence
                    for result in results
                    if result.classification != max_confidence_result.classification
                },
            )
        return max_confidence_result


class GrammarBasedClassifier:
    """Primary classifier using grammar structure from node_types.json."""

    def __init__(self, parser: NodeTypeParser | None = None) -> None:
        """Initialize grammar-based classifier.

        Args:
            parser: NodeTypeParser instance. If None, creates a new one.
        """
        from codeweaver.semantic.node_type_parser import NodeTypeParser

        self.parser = parser or NodeTypeParser()

        # Build Category name → SemanticClass mapping
        self._classification_map = self._build_category_to_semantic_map()

    def _classify_by_can_be_anywhere(
        self, thing: CompositeThing | Token, language: SemanticSearchLanguage
    ) -> GrammarClassificationResult | None:
        """Classify a Thing based on can_be_anywhere flag.

        There's a small set of Things that can appear anywhere in the syntax tree, or are marked as such in the grammar. All but two are comments:

        - Since we're talking about comments that can be anywhere (unlike, for example, docstring comments that may be constrained for some languages), we know that these are either line comments or block comments (typically module-level comments).
        - Most grammars don't distinguish between line and block comments *within nodes that can be anywhere*. Swift is an exception, which has "comment" (line) and "multiline_comment" (block).
        - So for swift, we can have high confidence in distinguishing line vs block comments.
        - The two exceptions are:

            - Python's "line_continuation" (which is actually a syntax element, not a comment)
            - PHP's "text_interpolation" (which are string interpolation nodes for templated strings)

        - Others will need further disambiguation to more confidently classify as line vs block comments.

        Args:
            thing: The Thing instance
            language: The programming language
        """
        if not thing.can_be_anywhere:
            return None
        if language == SemanticSearchLanguage.SWIFT:
            if str(thing.name).lower() == "comment":
                return GrammarClassificationResult(
                    classification=SemanticClass.SYNTAX_ANNOTATION,
                    rank=ImportanceRank.SYNTAX_REFERENCES,
                    classification_method=ClassificationMethod.ANYWHERE,
                    evidence=(
                        EvidenceKind.SPECIFIC_THING,
                        EvidenceKind.LANGUAGE,
                        EvidenceKind.HEURISTIC,
                    ),
                    adjustment=100,  # we know exactly what this is
                )
            if str(thing.name).lower() == "multiline_comment":
                return GrammarClassificationResult(
                    classification=SemanticClass.DOCUMENTATION_STRUCTURED,
                    rank=ImportanceRank.PRIMARY_DEFINITIONS,
                    classification_method=ClassificationMethod.ANYWHERE,
                    evidence=(
                        EvidenceKind.SPECIFIC_THING,
                        EvidenceKind.LANGUAGE,
                        EvidenceKind.HEURISTIC,
                    ),
                    adjustment=100,  # we know exactly what this is
                )
        if (
            str(thing.name).lower() == "line_continuation"
            and language == SemanticSearchLanguage.PYTHON
        ):
            # Special case: line_continuation is SYNTAX_PUNCTUATION
            return GrammarClassificationResult(
                classification=SemanticClass.SYNTAX_PUNCTUATION,
                rank=ImportanceRank.SYNTAX_REFERENCES,
                classification_method=ClassificationMethod.ANYWHERE,
                evidence=(
                    EvidenceKind.SPECIFIC_THING,
                    EvidenceKind.LANGUAGE,
                    EvidenceKind.HEURISTIC,
                ),
                adjustment=100,  # we know exactly what this is
            )
        if str(thing.name).lower() == "text_interpolation":
            # Special case: text_interpolation is SYNTAX_IDENTIFIER
            return GrammarClassificationResult(
                classification=SemanticClass.SYNTAX_IDENTIFIER,
                rank=ImportanceRank.SYNTAX_REFERENCES,
                classification_method=ClassificationMethod.ANYWHERE,
                # We know the language is PHP based on deduction from the name, and knowledge of the small set of unique anywhere Things
                evidence=(
                    EvidenceKind.SPECIFIC_THING,
                    EvidenceKind.LANGUAGE,
                    EvidenceKind.HEURISTIC,
                ),
                adjustment=100,  # we know exactly what this is
            )
        return None

    def _handle_comment_cases(
        self, thing: CompositeThing | Token, language: SemanticSearchLanguage
    ) -> GrammarClassificationResult | None:
        """Handle special cases for comment Things."""
        if "comment" in str(thing.name).lower() and "line" in str(thing.name).lower():
            return GrammarClassificationResult(
                classification=SemanticClass.SYNTAX_ANNOTATION,
                rank=ImportanceRank.SYNTAX_REFERENCES,
                classification_method=ClassificationMethod.SPECIFIC_THING,
                evidence=(
                    EvidenceKind.SPECIFIC_THING,
                    EvidenceKind.LANGUAGE,
                    EvidenceKind.SIMPLE_NAME_PATTERN,
                ),
                adjustment=90,  # very high confidence
            )
        if language == SemanticSearchLanguage.RUST and str(thing.name).lower() in {
            "doc_comment",
            "block_comment",
        }:
            return GrammarClassificationResult(
                classification=SemanticClass.DOCUMENTATION_STRUCTURED,
                rank=ImportanceRank.PRIMARY_DEFINITIONS,
                classification_method=ClassificationMethod.SPECIFIC_THING,
                evidence=(
                    EvidenceKind.SPECIFIC_THING,
                    EvidenceKind.LANGUAGE,
                    EvidenceKind.SIMPLE_NAME_PATTERN,
                ),
                adjustment=90,  # very high confidence
                differentiator=lambda node: (
                    SemanticClass.DOCUMENTATION_STRUCTURED
                    if node.text.strip().startswith(("/**", "///", "//!", "#[doc", "#![doc"))  # type: ignore
                    else SemanticClass.SYNTAX_ANNOTATION
                ),  # type: ignore
            )
        if str(thing.name).lower() in {"block_comment", "multiline_comment"}:
            return GrammarClassificationResult(
                classification=SemanticClass.DOCUMENTATION_STRUCTURED,
                rank=ImportanceRank.PRIMARY_DEFINITIONS,
                classification_method=ClassificationMethod.SPECIFIC_THING,
                evidence=(
                    EvidenceKind.SPECIFIC_THING,
                    EvidenceKind.LANGUAGE,
                    EvidenceKind.SIMPLE_NAME_PATTERN,
                ),
                adjustment=-25,  # the evidence will be strong, but we need more context to be sure it's a docstring
            )
        return None

    def _classify_known_exceptions(
        self, thing: CompositeThing | Token, language: SemanticSearchLanguage
    ) -> GrammarClassificationResult | None:
        """Classify known exceptions that don't fit other patterns or that have very high confidence based on their specific characteristics."""
        if classification := self._handle_comment_cases(thing, language):
            return classification
        return None

    def classify_thing(
        self, thing_name: ThingName, language: SemanticSearchLanguage | str
    ) -> GrammarClassificationResult | None:
        """Classify a thing using grammar structure.

        Classification pipeline (highest to lowest confidence):
        1. Known exceptions (e.g., comments)
        2. can_be_anywhere Things (e.g., comments)
        3. Token purpose classification (very high confidence)
        4. Role-based inference from DirectConnections (high confidence)
        5. Category-based classification (high confidence)
        6. PositionalConnections-based inference (moderate confidence)
        7. Simple heuristics and name patterns (low confidence, not implemented yet)

        Args:
            thing_name: The Thing name (e.g., "function_definition")
            language: The programming language

        Returns:
            Classification result with confidence, or None if classification not possible
        """
        from codeweaver.semantic.node_type_parser import get_things

        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)

        # Get Thing from registry
        things = get_things(languages=[language])
        thing = next((t for t in things if t.name == thing_name), None)
        if thing is None:
            return None  # Thing not found for language
        if not isinstance(thing, CompositeThing | Token):
            return None  # Unsupported Thing type
        results: list[GrammarClassificationResult] = []
        for method in [
            self._classify_known_exceptions,
            self._classify_by_can_be_anywhere,
            self._classify_from_token_purpose,
            self._classify_from_category,
            self._classify_from_direct_connections,
            self._classify_from_positional_connections,
        ]:
            if classification := method(thing, language):
                if isinstance(classification, tuple):  # type: ignore
                    results.extend(classification)  # type: ignore
                    continue
                # if we have multiple classifications, we need to disambiguate
                # fast path: if we have a classification above the confidence threshold, and it's the first one, return it immediately
                if classification.confidence >= CONFIDENCE_THRESHOLD and not results:
                    return classification
                # If we have multiple classifications, we need to disambiguate
                # We collect all classifications and then choose the best one at the end
                # This method allows us to consider all evidence before making a final decision
                results.append(classification)
        return GrammarClassificationResult.from_results(results) if results else None

    def _build_category_to_semantic_map(self) -> dict[CategoryName, SemanticClass]:
        """Build mapping from grammar Category names to SemanticClass enum values.

        Based on empirical analysis of 25 languages, ~110 unique Categories.

        Returns:
            Mapping from CategoryName (from node_types.json) to SemanticClass enum
        """
        from codeweaver.semantic.node_type_parser import CategoryName

        category_map = {
            # Universal Categories (appear in most languages)
            CategoryName("expression"): SemanticClass.OPERATION_OPERATOR,
            CategoryName("primary_expression"): SemanticClass.OPERATION_OPERATOR,
            CategoryName("statement"): SemanticClass.FLOW_BRANCHING,
            CategoryName("type"): SemanticClass.DEFINITION_TYPE,
            CategoryName("declaration"): SemanticClass.DEFINITION_DATA,
            CategoryName("pattern"): SemanticClass.FLOW_BRANCHING,
            CategoryName("literal"): SemanticClass.SYNTAX_LITERAL,
            # C-family Categories
            CategoryName("declarator"): SemanticClass.DEFINITION_DATA,
            CategoryName("abstract_declarator"): SemanticClass.DEFINITION_DATA,
            CategoryName("field_declarator"): SemanticClass.DEFINITION_DATA,
            CategoryName("type_declarator"): SemanticClass.DEFINITION_DATA,
            CategoryName("type_specifier"): SemanticClass.DEFINITION_TYPE,
            # Language-specific Categories
            CategoryName("simple_statement"): SemanticClass.FLOW_CONTROL,
            CategoryName("simple_type"): SemanticClass.DEFINITION_TYPE,
            CategoryName("compound_statement"): SemanticClass.FLOW_BRANCHING,
            # Additional Categories from multi-language analysis
            CategoryName("parameter"): SemanticClass.DEFINITION_DATA,
            CategoryName("argument"): SemanticClass.SYNTAX_ANNOTATION,
            CategoryName("identifier"): SemanticClass.SYNTAX_IDENTIFIER,
        }
        # add keys with underscores in front of them
        return category_map | {CategoryName(f"_{k!s}"): v for k, v in category_map.items()}  # type: ignore

    def _classify_from_token_purpose(
        self, token: Token | CompositeThing, _language: SemanticSearchLanguage
    ) -> GrammarClassificationResult | None:
        """Classify a Token based on its purpose classification.

        Very high confidence classification method (0.95) using CodeWeaver's token purpose classification.

        Args:
            token: The Token to classify

        Returns:
            Classification result with very high confidence, or None if no purpose classification
        """
        if isinstance(token, CompositeThing):
            return None  # Only Tokens have purpose classifications
        classification = SemanticClass.from_token_purpose(token.purpose, token.name)
        rank = ImportanceRank.from_classification(classification)
        adjustment = 0
        if classification == SemanticClass.DOCUMENTATION_STRUCTURED:
            adjustment = -20  # We need more context to be sure it's a docstring
        return GrammarClassificationResult(
            classification=classification,
            rank=rank,
            classification_method=ClassificationMethod.TOKEN_PURPOSE,
            evidence=(EvidenceKind.PURPOSE, EvidenceKind.SPECIFIC_THING),
            adjustment=adjustment,  # We need more context to be sure it's a docstring
        )

    def _classify_from_category(
        self, thing: CompositeThing | Token, _language: SemanticSearchLanguage
    ) -> tuple[GrammarClassificationResult, ...] | None:
        """Classify a Thing based on its Category membership.

        Highest confidence classification method (0.90) using explicit grammar Categories.

        Args:
            thing: The Thing (CompositeThing or Token) to classify

        Returns:
            A tuple of classifications (one per unique Category mapping), or None.
        """
        if not thing.categories:
            return None

        # For Things with single Category, use it directly
        if thing.is_single_category:
            response = self._classify_from_primary_category(thing, _language)
            return (response,) if response else None
        # For multi-category Things (13.5% of Things), try all Categories
        if alternates := {
            self._classification_map.get(cat.name)
            for cat in thing.categories
            if self._classification_map.get(cat.name)
        }:
            if len(alternates) == 1:
                classification = cast(SemanticClass, alternates.pop())
                rank = ImportanceRank.from_classification(classification)
                return (
                    GrammarClassificationResult(
                        classification=classification,
                        rank=rank,
                        classification_method=ClassificationMethod.CATEGORY,
                        evidence=(EvidenceKind.CATEGORIES, EvidenceKind.HEURISTIC),
                        adjustment=5 * len(thing.categories),  # more categories = more confidence
                    ),
                )
            results: list[GrammarClassificationResult] = []
            for classification in alternates:
                if classification is None:
                    continue
                rank = ImportanceRank.from_classification(classification)
                results.append(
                    GrammarClassificationResult(
                        classification=classification,
                        rank=rank,
                        classification_method=ClassificationMethod.CATEGORY,
                        evidence=(EvidenceKind.CATEGORIES, EvidenceKind.HEURISTIC),
                        adjustment=-5 * len(alternates),
                    )
                )
            return tuple(results) if results else None
        return None

    def _classify_from_primary_category(
        self, thing: CompositeThing | Token, _language: SemanticSearchLanguage
    ) -> GrammarClassificationResult | None:
        """Classify a Thing based on its primary Category membership."""
        primary_category = thing.primary_category
        if primary_category is None:
            return None  # Shouldn't happen but be defensive

        semantic_classification = self._classification_map.get(primary_category.name)
        if not semantic_classification:
            return None

        rank = ImportanceRank.from_classification(semantic_classification)

        return GrammarClassificationResult(
            classification=semantic_classification,
            rank=rank,
            classification_method=ClassificationMethod.CATEGORY,
            evidence=(EvidenceKind.CATEGORIES,),
        )

    def _classify_from_direct_connections(
        self, thing: CompositeThing | Token, _language: SemanticSearchLanguage
    ) -> GrammarClassificationResult | None:
        """Classify based on DirectConnection Role patterns.

        High confidence classification method (0.85) using semantic Role analysis.

        Args:
            thing: CompositeThing to analyze (only CompositeThings have DirectConnections)

        Returns:
            Classification with high confidence, or None if no pattern match
        """
        if not isinstance(thing, CompositeThing) or not thing.direct_connections:
            return None  # Only CompositeThings have DirectConnections

        # Extract Roles from DirectConnections
        roles = frozenset(str(conn.role) for conn in thing.direct_connections)

        # Pattern matching on Role combinations
        classification: SemanticClass | None = None

        # Callable definitions: have 'body' and 'name' Roles
        if {"body", "name"}.issubset(roles):
            classification = SemanticClass.DEFINITION_CALLABLE

        # Branching control flow: have 'condition' Role
        elif {"condition", "consequence"}.issubset(roles) or {"condition", "body"}.issubset(roles):
            classification = SemanticClass.FLOW_BRANCHING

        # Binary operations: have 'left', 'right', 'operator' Roles
        elif {"left", "right", "operator"}.issubset(roles):
            classification = SemanticClass.OPERATION_OPERATOR

        # Type definitions: have 'name' and 'body' but also 'superclass' or 'interfaces'
        elif {"name", "body"}.issubset(roles) and (
            "superclass" in roles or "interfaces" in roles or "base" in roles
        ):
            classification = SemanticClass.DEFINITION_TYPE

        # Variable/data definitions: have 'type' and 'declarator' or 'value'
        elif {"type"}.issubset(roles) and (
            "declarator" in roles or "value" in roles or "default" in roles
        ):
            classification = SemanticClass.DEFINITION_DATA

        if classification is None:
            return None

        rank = ImportanceRank.from_classification(classification)

        return GrammarClassificationResult(
            classification=classification,
            rank=rank,
            classification_method=ClassificationMethod.CONNECTION_INFERENCE,
            evidence=(EvidenceKind.ROLES, EvidenceKind.CONNECTIONS),
        )

    def _classify_from_positional_connections(
        self, thing: CompositeThing | Token, _language: SemanticSearchLanguage
    ) -> GrammarClassificationResult | None:
        """Classify based on PositionalConnection patterns.

        Moderate confidence classification method (0.65-0.70) using structural patterns.

        Args:
            thing: CompositeThing to analyze

        Returns:
            Classification with moderate confidence, or None if no pattern match
        """
        if not isinstance(thing, CompositeThing) or not thing.positional_connections:
            return None

        # Heuristic: CompositeThings with both DirectConnections and
        # PositionalConnections are likely structural control flow nodes
        if thing.direct_connections:
            return GrammarClassificationResult(
                classification=SemanticClass.FLOW_BRANCHING,
                rank=ImportanceRank.CONTROL_FLOW_LOGIC,
                classification_method=ClassificationMethod.POSITIONAL,
                evidence=(EvidenceKind.HEURISTIC,),
            )

        # Just PositionalConnections, likely a container/expression/list node
        return GrammarClassificationResult(
            classification=SemanticClass.SYNTAX_IDENTIFIER,
            rank=ImportanceRank.SYNTAX_REFERENCES,
            classification_method=ClassificationMethod.POSITIONAL,
            evidence=(EvidenceKind.HEURISTIC,),
        )
